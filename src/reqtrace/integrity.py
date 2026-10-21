"""Change control for the input documents. No AI.

A verification protocol is only trustworthy if the documents it was built from are the approved ones.
`reqtrace baseline` freezes a copy of every requirement and legacy test step at the moment someone
signs them off. Every later run compares the documents on disk against that copy and reports each
unit (one requirement, one test step) that was edited, added or removed.

This is separate from the AI review on purpose. A hash comparison cannot be talked out of an answer
and it also catches edits that look perfectly reasonable, which is the dangerous kind.
"""
import csv
import difflib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .models import Finding

ROLES = ("srs", "system", "legacy")


@dataclass
class Drift:
    role: str     # srs | system | legacy
    id: str       # NP-REQ-005, NP-SYS-003, L-16 ...
    kind: str     # changed | added | removed
    change: str   # human-readable: what is different


def _norm(text: str) -> str:
    """Ignore what editors change behind your back: line endings, trailing spaces, blank lines."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n")).strip()


def _units(role: str, path: Path) -> dict[str, str]:
    """Split a document into {unit id: normalised text}."""
    raw = Path(path).read_text()
    if role == "legacy":
        rows = csv.DictReader(raw.splitlines())
        return {r["step"]: " | ".join(_norm(r[k]) for k in ("description", "action", "expected_result", "traces_to"))
                for r in rows}
    if role == "srs":
        parts = re.split(r"^(?=### NP-REQ-\d{3})", raw, flags=re.MULTILINE)[1:]
        return {re.match(r"### (NP-REQ-\d{3})", p).group(1): _norm(p) for p in parts}
    return {m.group(1): _norm(m.group(0)) for m in re.finditer(r"^- \*\*(NP-SYS-\d{3})\*\*.*$", raw, re.MULTILINE)}


def snapshot(srs: Path, system: Path, legacy: Path) -> dict[str, dict[str, str]]:
    return {role: _units(role, p) for role, p in zip(ROLES, (srs, system, legacy), strict=True)}


def write_baseline(path: Path, snap: dict) -> None:
    """Sign-off: freeze the current documents. Review the resulting file in a pull request."""
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    path.write_text(json.dumps({"approved_on": date.today().isoformat(), "git_commit": commit, "units": snap}, indent=1) + "\n")


def _same_field(words: list[str]) -> list[str]:
    """Words since the last field separator, so a diff's context never spills into the previous column."""
    return words[len(words) - words[::-1].index("|"):] if "|" in words else words


def _word_diff(before: str, after: str) -> str:
    """Say what changed in a few words ("20%" -> "25%"), with enough context to find it in the row."""
    a, b = before.split(), after.split()
    parts = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        old, new, where = " ".join(a[i1:i2]), " ".join(b[j1:j2]), " ".join(_same_field(a[:i1])[-3:])
        if tag == "replace":
            parts.append(f'"{old}" -> "{new}"')
        elif tag == "delete":
            parts.append(f'removed "{old}" after "{where}"')
        elif tag == "insert":
            parts.append(f'added "{new}" after "{where}"')
    return "; ".join(parts)


def find_drift(baseline_path: Path, current: dict[str, dict[str, str]]) -> list[Drift]:
    approved = json.loads(Path(baseline_path).read_text())["units"]
    out = []
    for role in ROLES:
        old, new = approved.get(role, {}), current[role]
        for uid in sorted(old.keys() | new.keys()):
            if uid not in new:
                out.append(Drift(role, uid, "removed", "no longer in the document"))
            elif uid not in old:
                out.append(Drift(role, uid, "added", "not in the approved baseline"))
            elif old[uid] != new[uid]:
                out.append(Drift(role, uid, "changed", _word_diff(old[uid], new[uid])))
    return out


def drift_findings(drifts: list[Drift]) -> list[Finding]:
    return [Finding(source="deterministic", type="baseline_drift", severity="high", cited_ids=[d.id],
                    rationale=f"{d.id} ({d.role}) was {d.kind} after sign-off: {d.change}. "
                              f"Check that this went through change control.") for d in drifts]
