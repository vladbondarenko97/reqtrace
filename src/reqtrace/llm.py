"""The single place that talks to a model.

Backends: claude-code (default, `claude -p`, no API key), anthropic (SDK), mock (recorded fixtures).
Every call: pinned system prompt, JSON -> Pydantic, max 2 attempts, logged, token-budgeted.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from pydantic import BaseModel, ValidationError

PROMPTS = Path(__file__).parent / "prompts"
FIXTURES = Path(__file__).parent / "fixtures"
DEFAULT_MODEL = {"claude-code": "sonnet", "anthropic": "claude-sonnet-5-5", "mock": "recorded"}


class LLMError(RuntimeError):
    pass


class BudgetExceeded(LLMError):
    pass


def _digest(system: str, user: str) -> str:
    return hashlib.sha256(f"{system}\n---\n{user}".encode()).hexdigest()


def extract_json(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    a, b = text.find("{"), text.rfind("}")
    return text[a : b + 1] if a != -1 and b > a else text


class LLM:
    def __init__(self, backend: str, out_dir: Path, model: str | None = None, max_tokens: int = 400_000,
                 record: bool = False):
        self.backend, self.out_dir, self.max_tokens, self.record = backend, Path(out_dir), max_tokens, record
        self.model = model or DEFAULT_MODEL[backend]
        self.tokens = 0
        self.log_path = self.out_dir / "llm_log.jsonl"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text("")

    def ask(self, task: str, user: str, model_cls: type[BaseModel], check=None):
        system = (PROMPTS / f"{task}.md").read_text()
        prompt, first_hash = user, _digest(system, user)
        for attempt in (1, 2):
            if self.tokens > self.max_tokens:
                raise BudgetExceeded(f"token budget {self.max_tokens} exceeded ({self.tokens} used)")
            t0 = time.time()
            text, tin, tout, extra = self._call(task, system, prompt, first_hash)
            self.tokens += tin + tout
            err = None
            try:
                obj = model_cls.model_validate_json(extract_json(text))
                if check:
                    check(obj)
            except (ValidationError, ValueError) as e:
                err = str(e)
            self._log(task, attempt, tin, tout, time.time() - t0, err, extra)
            if err is None:
                if self.record and self.backend != "mock":
                    self._save_fixture(task, first_hash, text, tin, tout, time.time() - t0)
                return obj
            prompt = f"{user}\n\nYour previous response was rejected:\n{err}\nReturn corrected JSON only."
        raise LLMError(f"{task}: output failed validation twice: {err}")

    def _log(self, task, attempt, tin, tout, latency, err, extra):
        row = {"task": task, "backend": self.backend, "model": self.model, "attempt": attempt,
               "input_tokens": tin, "output_tokens": tout, "latency_s": round(latency, 2),
               "valid": err is None, "error": err, **extra}
        with self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")

    def _call(self, task, system, prompt, first_hash):
        if self.backend == "mock":
            return self._mock(task, system, prompt, first_hash)
        if self.backend == "claude-code":
            return self._claude_code(system, prompt)
        return self._anthropic(system, prompt)

    # -- backends -----------------------------------------------------------------------------
    def _claude_code(self, system, prompt):
        # Empty cwd + no tools/MCP/skills: the model only sees our prompt (same isolation idea as take-the-wheel).
        with tempfile.TemporaryDirectory() as cwd:
            p = subprocess.run(
                ["claude", "-p", "--model", self.model, "--system-prompt", system, "--tools", "",
                 "--output-format", "json", "--max-turns", "1", "--strict-mcp-config",
                 "--disable-slash-commands", "--no-session-persistence"],
                check=False, input=prompt, capture_output=True, text=True, cwd=cwd, timeout=900)
        try:
            r = json.loads(p.stdout)
        except json.JSONDecodeError:
            raise LLMError(f"claude CLI failed (exit {p.returncode}): {(p.stderr or p.stdout)[:400]}") from None
        if r.get("is_error"):
            raise LLMError(f"claude CLI error: {str(r.get('result'))[:400]}")
        u = r["usage"]
        tin = u["input_tokens"] + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        return r["result"], tin, u["output_tokens"], {"cost_usd_list": r.get("total_cost_usd")}

    def _anthropic(self, system, prompt):
        # ponytail: untested in this repo (no API key was available when it was built). No temperature:
        # current models reject sampling params, see docs/DECISIONS.md D-03.
        import anthropic  # optional extra

        kw = {"temperature": 0} if self.model.startswith("claude-haiku") else {}
        r = anthropic.Anthropic().messages.create(
            model=self.model, max_tokens=16000, system=system,
            messages=[{"role": "user", "content": prompt}], **kw)
        text = "".join(b.text for b in r.content if b.type == "text")
        return text, r.usage.input_tokens, r.usage.output_tokens, {}

    def _mock(self, task, system, prompt, first_hash):
        path = FIXTURES / f"{task}.json"
        if not path.exists():
            raise LLMError(f"no fixture for '{task}'; record with: reqtrace run --record")
        fx = json.loads(path.read_text())
        if fx["prompt_sha256"] != first_hash or _digest(system, prompt) != first_hash:
            raise LLMError(f"fixture for '{task}' is stale (inputs or retry prompt changed); re-record it")
        self.model = fx["model"]
        return fx["response"], fx["input_tokens"], fx["output_tokens"], {"replayed": True, "recorded_latency_s": fx["latency_s"]}

    def _save_fixture(self, task, first_hash, text, tin, tout, latency):
        FIXTURES.mkdir(exist_ok=True)
        (FIXTURES / f"{task}.json").write_text(json.dumps({
            "task": task, "backend": self.backend, "model": self.model, "prompt_sha256": first_hash,
            "input_tokens": tin, "output_tokens": tout, "latency_s": round(latency, 2),
            "recorded_by": "reqtrace run --record", "response": text}, indent=1) + "\n")


def have_claude_cli() -> bool:
    return any((Path(d) / "claude").exists() for d in os.environ.get("PATH", "").split(os.pathsep))
