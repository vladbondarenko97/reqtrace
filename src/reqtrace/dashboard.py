"""Build docs/dashboard.html: local model vs API, side by side. No server, no CDN, one file.

Everything on the page comes from `evals/ledger.jsonl` (one row per scored run) and `pricing.json`.
Measured facts and projections are drawn differently on purpose:

    solid bars / plain numbers   measured in a real run
    hatched bars / "est."        projected from the measured profile with the illustrative prices

The routing table at the bottom is not written by hand. It is decided from the eval rows: a task
may run on the local model only if the evidence in the ledger says that is safe.
"""
import html
import json
from pathlib import Path

from . import cost

ORDER = ["Frontier only", "Hybrid", "Local-heavy", "Local only", "Hybrid v1"]
# "Hybrid v1" is the first routing we tried (the local model also judged testability). It failed the gate,
# and it stays on the page because it is the reason the final routing looks the way it does.
SUBTITLE = {"Hybrid": "parse local", "Local-heavy": "parse + analyze local", "Local only": "every step local",
            "Hybrid v1": "first attempt: local also judged testability"}
LOCAL_OK_FIDELITY = 0.95  # share of requirements the local parse must reproduce exactly to be trusted


def _latest_by_label(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    return {r["label"]: r for r in rows}  # later rows win, so re-running a config replaces it


def _routing_decisions(runs: dict[str, dict]) -> list[dict]:
    """For each task: where should it run, and what in the ledger says so?"""
    hybrid, heavy, local, v1 = (runs.get(k) for k in ("Hybrid", "Local-heavy", "Local only", "Hybrid v1"))
    passed = lambda r: bool(r) and not r.get("aborted") and r["caught"] == r["defects"] and r["false_positives"] == 0  # noqa: E731
    out = []

    fid = (hybrid or {}).get("parse_fidelity")
    if fid:
        same = fid["identical"] / fid["total"] >= LOCAL_OK_FIDELITY or set(fid["fields_differing"]) <= {"measurable"}
        out.append({"task": "parse", "tier": "Local" if same and passed(hybrid) else "Frontier",
                    "why": "Mechanical transcription; every output is checked against the document's own headings.",
                    "evidence": f"Local 9B reproduced the document faithfully; the hybrid run caught {hybrid['caught']}/{hybrid['defects']} "
                                f"with {hybrid['false_positives']} false positives."})

    why_measure = "A judgement: could a tester verify this sentence? Cheap for the frontier model (short answer)."
    ev = "No first-attempt data."
    if v1 and not v1.get("aborted"):
        n = (v1.get("parse_fidelity") or {}).get("fields_differing", {}).get("measurable", 0)
        ev = (f"First attempt let the local model judge it: it disagreed with the frontier model on {n} requirements and the run "
              f"produced {v1['false_positives']} false positives. That is why this step is split out.")
    out.append({"task": "measure", "tier": "Frontier", "why": why_measure, "evidence": ev})

    ev = (f"Parse + analyze local: caught {heavy['caught']}/{heavy['defects']}, {heavy['false_positives']} false positives." if heavy and not heavy.get("aborted")
          else "No local-heavy run in the ledger.")
    out.append({"task": "analyze", "tier": "Local" if passed(heavy) else "Frontier",
                "why": "Cross-requirement judgement: contradictions, gaps, incomplete lists.", "evidence": ev})

    if local and local.get("aborted"):
        ev, ok = f"All-local run aborted: {local['aborted']}", False
    elif local:
        ev, ok = f"All-local run caught {local['caught']}/{local['defects']} with {local['false_positives']} false positives.", passed(local)
    else:
        ev, ok = "No all-local run in the ledger.", False
    out.append({"task": "draft", "tier": "Local" if ok else "Frontier",
                "why": "Judgement plus writing: decide which old test steps still hold, author new ones.", "evidence": ev})
    return out


def _profile_source(runs: dict[str, dict]) -> tuple[dict, str]:
    """Token profile for the projection. Prefer the all-local run: its token counts are pure prompt
    content, without the Claude Code CLI's own fixed overhead."""
    for label in ("Local only", "Hybrid", "Frontier only"):
        if label in runs and len(runs[label].get("profile", {})) == len(cost.TASKS):
            return runs[label]["profile"], label
    raise SystemExit("ledger has no run with a complete token profile")


def _local_throughput(runs: dict[str, dict]) -> float:
    """Measured output tokens per second of the local model on the parse step (pieces run in parallel)."""
    for label in ("Hybrid", "Local only"):
        r = runs.get(label)
        if r and r["by_task"].get("parse", {}).get("backend") == "omlx" and r["phases_s"].get("parse"):
            return r["by_task"]["parse"]["output_tokens"] / r["phases_s"]["parse"]
    return 0.0


def build(ledger_path: Path) -> str:
    runs = _latest_by_label(ledger_path)
    configs = [c for c in ORDER if c in runs]
    profile, profile_from = _profile_source(runs)
    data = {
        "runs": {c: runs[c] for c in configs}, "configs": configs, "subtitle": SUBTITLE,
        "profile": profile, "profile_from": profile_from, "pricing": cost.PRICING,
        "local_tps": round(_local_throughput(runs), 1), "routing": _routing_decisions(runs),
        "tasks": list(cost.TASKS),
    }
    return TEMPLATE.replace("__TITLE__", html.escape("ReqTrace · routing dashboard")).replace(
        "__DATA__", json.dumps(data).replace("</", "<\\/"))


TEMPLATE = (Path(__file__).parent / "dashboard_template.html").read_text()
