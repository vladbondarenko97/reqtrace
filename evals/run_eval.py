#!/usr/bin/env python3
"""Score out/findings.md + out/summary.json against data/ground_truth.json.

Match rule: a finding catches a planted defect if the types are equal and the cited IDs overlap the defect's IDs.
Extra findings that match a defect are not false positives; every other finding is.
Exit 1 if recall < all defects or false positives > 0 (the CI gate).
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEAD = re.compile(r"^### (F-\d+) · (\w+) · (\w+)\n- \*\*Cited:\*\* (.+)$", re.MULTILINE)


def parse_findings(md: str) -> list[dict]:
    return [{"id": i, "type": t, "source": s, "cited": {c.strip() for c in c.split(",")}} for i, t, s, c in HEAD.findall(md)]


def score(findings: list[dict], truth: dict) -> dict:
    caught, matched = {}, set()
    for d in truth["defects"]:
        for f in findings:
            if f["type"] == d["type"] and f["cited"] & set(d["req_ids"]):
                caught.setdefault(d["id"], f)
                matched.add(f["id"])
    return {"caught": caught, "false_positives": [f for f in findings if f["id"] not in matched]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=ROOT / "out")
    ap.add_argument("--truth", type=Path, default=ROOT / "data/ground_truth.json")
    ap.add_argument("--mock", action="store_true", help="label only: evaluating a --mock run (the eval itself never calls a model)")
    ap.add_argument("--note", help="append this run to evals/history.md with this note")
    a = ap.parse_args()

    truth, summary = json.loads(a.truth.read_text()), json.loads((a.out / "summary.json").read_text())
    findings = parse_findings((a.out / "findings.md").read_text())
    if len(findings) != len(summary["findings"]):
        sys.exit(f"findings.md ({len(findings)}) and summary.json ({len(summary['findings'])}) disagree")
    s = score(findings, truth)
    n, got, fps = len(truth["defects"]), len(s["caught"]), s["false_positives"]
    ok = got == n and not fps

    nodeps = truth["legacy_steps_that_must_not_be_reused"]["steps"]
    retired = set(summary["trace"]["legacy_retired"])
    wrongly_reused = [x for x in nodeps if x not in retired]
    c, l = summary["counts"], summary["llm"]
    rows = [
        ("Planted defects caught", f"**{got} / {n}**"),
        ("False positives (findings not in the answer key)", f"**{len(fps)}**"),
        ("Hallucinated citations rejected by the guardrail", f"{summary['rejected_findings']}"),
        ("Findings from deterministic checks / from the LLM", f"{c.get('deterministic', 0)} / {c.get('llm', 0)}"),
        ("Obsolete legacy test steps correctly retired", f"{len(nodeps) - len(wrongly_reused)} / {len(nodeps)}"),
        ("Requirements with at least one test step", f"{summary['trace']['requirements_covered']} / {summary['trace']['requirements_total']}"),
        ("Tokens (in / out)", f"{l['input_tokens']:,} / {l['output_tokens']:,}"),
        ("Model time" + (" (as recorded)" if a.mock else ""), f"{l['latency_s']} s"),
    ]
    lines = ["# ReqTrace eval report\n", f"Run: {summary['mode']} · result: **{'PASS' if ok else 'FAIL'}**\n",
             "| What we measured | Result |", "|---|---|", *[f"| {k} | {v} |" for k, v in rows],
             "\n| Planted defect | Type | Requirements | Caught by |", "|---|---|---|---|"]
    for d in truth["defects"]:
        f = s["caught"].get(d["id"])
        lines.append(f"| {d['id']} | {d['type']} | {', '.join(d['req_ids'])} | {f['id'] + ' (' + f['source'] + ')' if f else '**MISSED**'} |")
    if fps:
        lines += ["\nFalse positives:"] + [f"- {f['id']} {f['type']} {sorted(f['cited'])} ({f['source']})" for f in fps]
    if wrongly_reused:
        lines.append(f"\nObsolete legacy steps wrongly reused: {', '.join(wrongly_reused)}")
    report = "\n".join(lines) + "\n"
    (ROOT / "evals/latest_report.md").write_text(report)
    print(report)

    if a.note:
        h = ROOT / "evals/history.md"
        if not h.exists():
            h.write_text("# Eval history\n\nAppended by `evals/run_eval.py --note`; never edited by hand.\n\n"
                         "| When (UTC) | Run | Caught | FP | Rejected | Det/LLM | Legacy retired ok | Tokens in/out | Note |\n|---|---|---|---|---|---|---|---|---|\n")
        with h.open("a") as f:
            f.write(f"| {datetime.datetime.now(datetime.UTC):%Y-%m-%d %H:%M} | {summary['mode']} | {got}/{n} | {len(fps)} | "
                    f"{summary['rejected_findings']} | {c.get('deterministic', 0)}/{c.get('llm', 0)} | {len(nodeps) - len(wrongly_reused)}/{len(nodeps)} | "
                    f"{l['input_tokens']}/{l['output_tokens']} | {a.note} |\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
