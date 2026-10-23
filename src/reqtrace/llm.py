"""The one place in ReqTrace that talks to a language model.

Every other module just calls `llm.ask(task, text, SomeSchema)` and gets back a validated object. What
happens in between is the same no matter which model answers:

    pinned system prompt -> model -> JSON -> Pydantic schema -> (optional extra check)
                                        \\__ invalid? one retry with the error fed back, then give up

Four backends sit behind that one method:

    claude-code  default. Shells out to `claude -p`, so it runs on your Claude Code login (no API key).
    anthropic    the Anthropic SDK (optional extra, needs ANTHROPIC_API_KEY).
    omlx         a model running on this machine through oMLX's OpenAI-compatible server. Free per token.
    mock         replays responses recorded earlier (`--record`). No model, no key. Used by CI.

Every call is logged to `llm_log.jsonl` (tokens, latency, validity, backend), which is what the cost
model and the dashboard are built from.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

from pydantic import BaseModel, ValidationError

from . import telemetry

PROMPTS = Path(__file__).parent / "prompts"
FIXTURES = Path(__file__).parent / "fixtures"

OMLX_URL = os.environ.get("OMLX_URL", "http://127.0.0.1:8000/v1")
OMLX_SETTINGS = Path.home() / ".omlx" / "settings.json"

DEFAULT_MODEL = {
    "claude-code": "sonnet",
    "anthropic": "claude-sonnet-5-5",
    "omlx": os.environ.get("REQTRACE_OMLX_MODEL", "Qwen3.5-9B-MLX-8bit"),
    "mock": "recorded",
}


class LLMError(RuntimeError):
    """A model call failed or kept returning output that did not validate."""


class BudgetExceeded(LLMError):
    """The run used more tokens than --max-tokens allows."""


# ---------------------------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------------------------
def _digest(system: str, user: str) -> str:
    """Fingerprint of a prompt. Recorded fixtures are looked up by this, so any change to the
    system prompt OR the input makes the old recording 'not found' instead of silently stale."""
    return hashlib.sha256(f"{system}\n---\n{user}".encode()).hexdigest()


def extract_json(text: str) -> str:
    """Models like to wrap JSON in ```json fences or add a sentence around it. Keep just the object."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    start, end = text.find("{"), text.rfind("}")
    return text[start : end + 1] if start != -1 and end > start else text


def have_claude_cli() -> bool:
    return any((Path(d) / "claude").exists() for d in os.environ.get("PATH", "").split(os.pathsep))


def omlx_api_key() -> str:
    """oMLX protects its local server with a key. Take it from the environment, or fall back to the
    oMLX settings file on this machine. It is never written into this repo."""
    if os.environ.get("OMLX_API_KEY"):
        return os.environ["OMLX_API_KEY"]
    try:
        return json.loads(OMLX_SETTINGS.read_text())["auth"]["api_key"]
    except (OSError, KeyError, ValueError):
        raise LLMError("No oMLX API key. Set OMLX_API_KEY, or start oMLX so ~/.omlx/settings.json exists.") from None


# ---------------------------------------------------------------------------------------------
# The client
# ---------------------------------------------------------------------------------------------
class LLM:
    def __init__(self, backend: str, out_dir: Path, model: str | None = None, max_tokens: int = 400_000,
                 record: bool = False, reset_log: bool = True):
        self.backend = backend
        self.model = model or DEFAULT_MODEL[backend]
        self.out_dir = Path(out_dir)
        self.max_tokens = max_tokens  # a safety stop on total tokens, checked before every attempt
        self.record = record          # save validated responses as fixtures for --mock
        self.tokens = 0
        self._lock = threading.Lock()  # parse sends several chunks at once; the counter and log need a lock
        self.log_path = self.out_dir / "llm_log.jsonl"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if reset_log:  # a Router shares one log between its clients, so only the first one clears it
            self.log_path.write_text("")

    def ask(self, task: str, user: str, model_cls: type[BaseModel], check=None, tag: dict | None = None):
        """Run one task and return a validated `model_cls`.

        `check(obj)` may raise ValueError for rules a schema can't express (e.g. "the model must
        return exactly the IDs that were in the document"). `tag` is extra data for the log row.
        """
        system = (PROMPTS / f"{task}.md").read_text()
        prompt, first_hash = user, _digest(system, user)

        for attempt in (1, 2):
            if self.tokens > self.max_tokens:
                raise BudgetExceeded(f"token budget {self.max_tokens} exceeded ({self.tokens} used)")

            started = time.time()
            text, tokens_in, tokens_out, extra = self._call(task, system, prompt, first_hash)
            with self._lock:
                self.tokens += tokens_in + tokens_out

            error = None
            try:
                result = model_cls.model_validate_json(extract_json(text))
                if check:
                    check(result)
            except (ValidationError, ValueError) as e:
                error = str(e)

            elapsed = time.time() - started
            sizes = {"system_chars": len(system), "user_chars": len(user)}  # lets cost.py split content from overhead
            self._log(task, attempt, tokens_in, tokens_out, elapsed, error, {**extra, **sizes, **(tag or {})})
            if error is None:
                if self.record and self.backend != "mock":
                    self._save_fixture(task, first_hash, text, tokens_in, tokens_out, elapsed, extra)
                return result

            # Second chance: show the model exactly what was wrong with its answer.
            prompt = f"{user}\n\nYour previous response was rejected:\n{error}\nReturn corrected JSON only."

        raise LLMError(f"{task}: output failed validation twice: {error}")

    def _log(self, task, attempt, tokens_in, tokens_out, latency, error, extra):
        row = {"task": task, "backend": self.backend, "model": self.model, "attempt": attempt,
               "input_tokens": tokens_in, "output_tokens": tokens_out, "latency_s": round(latency, 2),
               "valid": error is None, "error": error, **extra}
        with self._lock, self.log_path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        telemetry.emit(row, time.time() - latency, time.time())

    def _call(self, task, system, prompt, first_hash):
        if self.backend == "mock":
            return self._mock(task, system, prompt, first_hash)
        return {"claude-code": self._claude_code, "omlx": self._omlx, "anthropic": self._anthropic}[self.backend](system, prompt)

    # -- backends -------------------------------------------------------------------------------
    def _claude_code(self, system, prompt):
        """`claude -p` with every tool, MCP server and skill switched off, run from an empty temp
        folder: the model sees our prompt and nothing else (same isolation idea as take-the-wheel)."""
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
        # Cache reads and writes are real input the model processed, so count them.
        tokens_in = u["input_tokens"] + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
        # The CLI reports what this call would cost at list price: a measured number, not an estimate.
        return r["result"], tokens_in, u["output_tokens"], {"cost_usd_list": r.get("total_cost_usd")}

    def _omlx(self, system, prompt):
        """A model on this machine, via oMLX's OpenAI-compatible endpoint (plain urllib, no extra
        dependency). Local models accept temperature 0, so unlike the hosted models these runs repeat."""
        body = {
            "model": self.model, "max_tokens": 16000, "temperature": 0,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "chat_template_kwargs": {"enable_thinking": False},  # we want the JSON, not a monologue first
        }
        req = urllib.request.Request(
            f"{OMLX_URL}/chat/completions", json.dumps(body).encode(),
            {"Authorization": f"Bearer {omlx_api_key()}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=1800) as resp:
                r = json.load(resp)
        except urllib.error.HTTPError as e:
            raise LLMError(f"oMLX returned HTTP {e.code}: {e.read()[:300].decode(errors='replace')}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError(f"oMLX is not reachable at {OMLX_URL} ({e}). Start oMLX, or use --backend claude-code.") from None
        u = r["usage"]
        return (r["choices"][0]["message"]["content"], u["prompt_tokens"], u["completion_tokens"],
                {"tokens_per_s": u.get("generation_tokens_per_second")})

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

    # -- recorded fixtures ----------------------------------------------------------------------
    @staticmethod
    def _fixture_path(task: str, digest: str) -> Path:
        return FIXTURES / f"{task}-{digest[:12]}.json"

    def _mock(self, task, system, prompt, first_hash):
        path = self._fixture_path(task, first_hash)
        if not path.exists():
            raise LLMError(
                f"no recorded fixture for '{task}' with this exact prompt ({first_hash[:12]}). The inputs or the "
                f"prompt changed since recording. Re-record with: reqtrace run --record")
        fx = json.loads(path.read_text())
        if _digest(system, prompt) != first_hash:  # replay only ever answers the first attempt
            raise LLMError(f"fixture for '{task}' cannot answer a retry prompt; re-record it")
        self.model = fx["model"]
        extra = {**fx.get("extra", {}), "replayed": True, "recorded_backend": fx["backend"],
                 "recorded_model": fx["model"], "recorded_latency_s": fx["latency_s"]}
        return fx["response"], fx["input_tokens"], fx["output_tokens"], extra

    def _save_fixture(self, task, digest, text, tokens_in, tokens_out, latency, extra):
        FIXTURES.mkdir(exist_ok=True)
        self._fixture_path(task, digest).write_text(json.dumps({
            "task": task, "backend": self.backend, "model": self.model, "prompt_sha256": digest,
            "input_tokens": tokens_in, "output_tokens": tokens_out, "latency_s": round(latency, 2),
            "extra": extra, "recorded_by": "reqtrace run --record", "response": text}, indent=1) + "\n")
