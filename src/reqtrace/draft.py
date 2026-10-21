"""Draft the verification protocol for the new device.

The model gets the parsed requirements and the old protocol. For each old test step it decides: still
valid for the new device (reuse as is) or obsolete (retire, with a reason). Then it writes new steps for
whatever the old steps do not cover. Rendering is plain code.
"""
import json

from .llm import LLM
from .models import DraftOut, LegacyStep, Requirement, Step

STAMP = "DRAFT — requires engineer review. Not for execution."


def draft(llm: LLM, reqs: list[Requirement], legacy: list[LegacyStep]) -> DraftOut:
    legacy_ids = {s.step for s in legacy}

    def known_legacy(out: DraftOut):  # every old step must be accounted for exactly once, and only real ones
        used = [s.legacy_step for s in out.steps if s.legacy_step] + [r.legacy_step for r in out.retired]
        bad = [i for i in used if i not in legacy_ids]
        dup = sorted({i for i in used if used.count(i) > 1})
        if bad or dup:
            raise ValueError(f"unknown legacy steps {bad}; legacy steps used more than once {dup}")

    payload = json.dumps({"requirements": [r.model_dump() for r in reqs],
                          "legacy_protocol": [s.model_dump() for s in legacy]}, indent=1)
    return llm.ask("draft", payload, DraftOut, check=known_legacy)


def render(steps: list[Step], retired: list[tuple[LegacyStep, str]]) -> str:
    out = ["# Draft Verification Protocol — Novapump NP-200 (synthetic)\n", f"> **{STAMP}**\n",
           "Origin tags: **NEW** = drafted for NP-200; **REUSED (L-nn)** = legacy step carried over verbatim, "
           "still traces cleanly; **RETIRED** steps are listed at the end with the reason.\n"]
    for feature in dict.fromkeys(s.feature for s in steps):
        out += [f"\n## {feature}\n", "| Step | Action | Expected Result | Traces To |", "|---|---|---|---|"]
        for s in (s for s in steps if s.feature == feature):
            tag = f"REUSED ({s.legacy_step})" if s.origin == "reused" else "NEW"
            out.append(f"| {s.id} · {tag} | {_c(s.action)} | {_c(s.expected_result)} | {', '.join(s.traces_to)} |")
    out += ["\n## Retired from legacy protocol (NP-100)\n", "| Legacy Step | Action | Why it was not reused |", "|---|---|---|"]
    out += [f"| {l.step} | {_c(l.action)} | {_c(why)} |" for l, why in retired]
    return "\n".join(out) + "\n"


def _c(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")
