"""The judgement part of the review, with the citation guardrail.

The model reads every requirement and reports contradictions, gaps, incomplete lists and untestable
wording. It is allowed to be wrong, but it is not allowed to point at something that isn't there:
every finding must cite requirement IDs that exist in the parsed SRS, or it is dropped and counted.
That turns "the model invented a requirement" from a silent error into a number on the dashboard.
"""
import json

from .llm import LLM
from .models import AnalyzeOut, Finding, Requirement


def analyze(llm: LLM, reqs: list[Requirement]) -> tuple[list[Finding], int]:
    payload = json.dumps([r.model_dump() for r in reqs], indent=1)
    return apply_guardrail(llm.ask("analyze", payload, AnalyzeOut), {r.id for r in reqs})


def apply_guardrail(out: AnalyzeOut, known_ids: set[str]) -> tuple[list[Finding], int]:
    """Keep findings whose every cited ID exists; drop the rest and return how many were dropped."""
    kept, rejected = [], 0
    for f in out.findings:
        if f.cited_ids and all(i in known_ids for i in f.cited_ids):
            kept.append(Finding(source="llm", **f.model_dump()))
        else:
            rejected += 1
    return kept, rejected
