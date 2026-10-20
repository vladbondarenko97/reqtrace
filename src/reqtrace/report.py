"""findings.md (grouped by severity) and summary.json."""
import json
from pathlib import Path

from .draft import STAMP
from .models import Finding

ORDER = ["high", "medium", "low"]


def merge(findings: list[Finding]) -> tuple[list[Finding], int]:
    """Drop an LLM finding that repeats a deterministic one (same type, same cited IDs)."""
    seen, out, dup = {}, [], 0
    for f in sorted(findings, key=lambda f: f.source != "deterministic"):
        key = (f.type, frozenset(f.cited_ids))
        if key in seen:
            dup += 1
            continue
        seen[key] = f
        out.append(f)
    out.sort(key=lambda f: ORDER.index(f.severity))
    return out, dup


def write(out_dir: Path, findings: list[Finding], summary: dict) -> None:
    lines = ["# Findings — Novapump NP-200 SRS (synthetic)\n", f"> **{STAMP}** Findings are suggestions for the reviewing engineer.\n"]
    n = 0
    for sev in ORDER:
        group = [f for f in findings if f.severity == sev]
        if not group:
            continue
        lines.append(f"\n## {sev.capitalize()} ({len(group)})\n")
        for f in group:
            n += 1
            lines += [f"### F-{n:03d} · {f.type} · {f.source}", f"- **Cited:** {', '.join(f.cited_ids)}", f"- **Rationale:** {f.rationale}\n"]
    if not findings:
        lines.append("\nNo findings.\n")
    (out_dir / "findings.md").write_text("\n".join(lines))
    summary["findings"] = [{"id": f"F-{i:03d}", **f.model_dump()} for i, f in enumerate(findings, 1)]
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
