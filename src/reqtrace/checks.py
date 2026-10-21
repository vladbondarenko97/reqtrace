"""Deterministic checks. No AI: every rule here is plain code over the parsed data.

These run next to the AI review, not instead of it. A rule that can be written as code should be code:
it is free, instant, identical on every run, and a reviewer can read exactly why it fired.
"""
from .models import Finding, Requirement, Step

# The only values the SRS is allowed to use. Anything else is a typo or an undefined term.
MODES = {"Basal", "Bolus", "Extended Bolus", "Suspend"}
PROFILES = {"Adult", "Pediatric"}


def _finding(type_, severity, ids, why):
    return Finding(source="deterministic", type=type_, severity=severity, cited_ids=ids, rationale=why)


def static_checks(reqs: list[Requirement], sys_ids: set[str]) -> list[Finding]:
    """Rules that need only the requirements themselves."""
    out = []
    for r in reqs:
        # Every requirement should trace up to a system requirement that actually exists.
        if r.traces_to and r.traces_to not in sys_ids:
            out.append(_finding("orphan_trace", "high", [r.id],
                                f"{r.id} traces to {r.traces_to}, which does not exist in the system requirements."))

        # Modes and profiles must come from the defined vocabulary.
        for kind, values, allowed in (("mode", r.modes, MODES), ("profile", r.profiles, PROFILES)):
            for v in values:
                if v not in allowed:
                    out.append(_finding("invalid_enum_value", "medium", [r.id],
                                        f"{r.id} names {kind} '{v}', which is not one of {sorted(allowed)}."))

        # `measurable` is a judgement the parse step makes (is there a number, a message, a named control a
        # tester could check?). Acting on it is not a judgement: if it is false, the requirement is untestable.
        if not r.measurable:
            out.append(_finding("untestable", "medium", [r.id], f"{r.id} is not measurable: \"{r.text}\""))
    return out


def coverage_checks(reqs: list[Requirement], steps: list[Step]) -> list[Finding]:
    """Rules over the finished trace: every requirement has a test, every test points at a real requirement."""
    known = {r.id for r in reqs}
    covered = {i for s in steps for i in s.traces_to}
    out = [_finding("no_test", "high", [r.id], f"{r.id} has no test step in the draft protocol.")
           for r in reqs if r.id not in covered]
    for s in steps:
        for i in s.traces_to:
            if i not in known:
                out.append(_finding("test_unknown_req", "medium", [s.id], f"{s.id} traces to {i}, which is not a requirement in the SRS."))
    return out
