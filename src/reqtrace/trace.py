"""Merge reused legacy steps and new steps into the requirement <-> test matrix."""
import csv
from pathlib import Path

from .models import DraftOut, LegacyStep, Requirement, Step


def load_legacy(path: Path) -> list[LegacyStep]:
    with open(path, newline="") as f:
        return [LegacyStep(**row) for row in csv.DictReader(f)]


def build(reqs: list[Requirement], legacy: list[LegacyStep], d: DraftOut) -> tuple[list[Step], list[tuple[LegacyStep, str]]]:
    by_id, feat = {s.step: s for s in legacy}, {r.id: r.feature for r in reqs}
    order = {r.id: n for n, r in enumerate(reqs)}
    steps = []
    for s in d.steps:
        leg = by_id.get(s.legacy_step) if s.legacy_step else None
        # Reused steps take their text verbatim from the legacy CSV: the model cannot quietly rewrite them.
        action, expected = (leg.action, leg.expected_result) if leg else (s.action, s.expected_result)
        known = [i for i in s.traces_to if i in feat]
        steps.append(Step(id="", feature=feat[known[0]] if known else "Unmapped", action=action, expected_result=expected,
                          traces_to=s.traces_to, origin="reused" if leg else "new", legacy_step=leg.step if leg else None))
    first = lambda s: min((order[i] for i in s.traces_to if i in order), default=10**6)
    steps.sort(key=first)  # stable: keeps model order within a requirement
    for n, s in enumerate(steps, 1):
        s.id = f"TC-{n:03d}"
    retired = [(by_id[r.legacy_step], r.reason) for r in d.retired if r.legacy_step in by_id]
    seen = {s.legacy_step for s in steps} | {l.step for l, _ in retired}
    retired += [(l, "Not classified by the model; engineer must decide.") for l in legacy if l.step not in seen]
    return steps, retired


def write_matrix(path: Path, reqs: list[Requirement], steps: list[Step]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["requirement_id", "requirement_title", "step_id", "origin", "legacy_step", "action"])
        for r in reqs:
            rows = [s for s in steps if r.id in s.traces_to]
            for s in rows:
                w.writerow([r.id, r.title, s.id, s.origin, s.legacy_step or "", s.action])
            if not rows:
                w.writerow([r.id, r.title, "", "NO TEST", "", ""])
