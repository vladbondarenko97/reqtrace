"""Decide which model answers which task.

The idea: not every step needs the most expensive model. Transcribing a document into JSON is
high-volume, mechanical and fully checkable (we know which IDs must come back), so it can run on a
small model on this machine. Judgement work (finding contradictions, deciding which old test steps
still make sense) stays on the frontier model. The routing is a policy, and the eval decides whether
the policy is allowed: see docs/DECISIONS.md D-16.

If the local model's answer still fails validation after its retry, the task is escalated to the
strong model instead of failing the run. The escalation is written to the log, so it shows up in
the cost numbers instead of hiding.
"""
from pathlib import Path

from pydantic import BaseModel

from .llm import LLM, LLMError


class Router:
    """Same `.ask()` as LLM, so the rest of the pipeline can't tell the difference."""

    def __init__(self, strong: LLM, local: LLM, local_tasks: set[str]):
        self.strong, self.local, self.local_tasks = strong, local, set(local_tasks)
        self.backend = "hybrid"
        self.log_path = strong.log_path
        self.escalations = 0

    @property
    def model(self) -> str:
        return f"{self.strong.model} + {self.local.model} (local: {', '.join(sorted(self.local_tasks))})"

    @property
    def tokens(self) -> int:
        return self.strong.tokens  # only the paid model has a budget; local tokens are free

    def ask(self, task: str, user: str, model_cls: type[BaseModel], check=None, tag=None):
        if task not in self.local_tasks:
            return self.strong.ask(task, user, model_cls, check, tag)
        try:
            return self.local.ask(task, user, model_cls, check, tag)
        except LLMError as e:
            self.escalations += 1
            note = {**(tag or {}), "escalated_from": self.local.backend, "escalation_reason": str(e)[:200]}
            return self.strong.ask(task, user, model_cls, check, note)


def build_llm(*, mock: bool, backend: str, out_dir: Path, model: str | None, max_tokens: int, record: bool,
              local_tasks: set[str]):
    """One client for a normal run, or a Router when some tasks are sent to the local model."""
    if mock:
        return LLM("mock", out_dir, None, max_tokens)  # the recordings already know who answered what
    strong = LLM(backend, out_dir, model, max_tokens, record)
    if not local_tasks:
        return strong
    local = LLM("omlx", out_dir, None, 10**12, record, reset_log=False)
    return Router(strong, local, local_tasks)
