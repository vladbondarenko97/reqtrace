"""Command line: `reqtrace run`, `reqtrace baseline`, `reqtrace dashboard`."""
import json
import time
from collections import Counter
from pathlib import Path

import click

from . import analyze as analyze_mod
from . import checks, cost, integrity, parse, report, telemetry, trace
from . import draft as draft_mod
from .llm import LLMError, have_claude_cli
from .router import build_llm

DATA = "data"


@click.group()
def main():
    """ReqTrace: guardrailed SRS analysis (fictional Novapump NP-200)."""


@main.command()
@click.option("--srs", default=f"{DATA}/novapump_srs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--sys", "sys_path", default=f"{DATA}/novapump_system_reqs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--legacy", default=f"{DATA}/legacy_protocol_v1.csv", type=click.Path(exists=True, path_type=Path))
@click.option("--baseline", default=f"{DATA}/baseline.json", type=click.Path(path_type=Path),
              help="Approved copy of the input documents. Any difference is reported as baseline_drift.")
@click.option("--out", default="out", type=click.Path(path_type=Path))
@click.option("--mock", is_flag=True, help="Replay recorded fixtures; no model, no key.")
@click.option("--backend", type=click.Choice(["claude-code", "anthropic", "omlx"]), default="claude-code", show_default=True,
              help="claude-code: your Claude Code login, no API key. anthropic: needs ANTHROPIC_API_KEY. "
                   "omlx: a model on this machine (every task runs locally).")
@click.option("--model", default=None, help="Default: sonnet (claude-code), claude-sonnet-5-5 (anthropic), Qwen3.5-9B-MLX-8bit (omlx).")
@click.option("--local-tasks", default="", metavar="TASKS",
              help="Comma list of tasks to send to the local oMLX model while the rest use --backend, e.g. parse. "
                   "A local answer that fails validation twice is escalated to --backend.")
@click.option("--hybrid", is_flag=True, help="Shortcut for --local-tasks parse.")
@click.option("--max-tokens", default=400_000, show_default=True, help="Abort if total paid tokens exceed this.")
@click.option("--record", is_flag=True, help="Save validated responses as mock fixtures (src/reqtrace/fixtures).")
@telemetry.traced
def run(srs, sys_path, legacy, baseline, out, mock, backend, model, local_tasks, hybrid, max_tokens, record):
    """Run the full pipeline and write findings, trace matrix, draft protocol and summary to --out."""
    if mock and record:
        raise click.UsageError("--record needs a real backend")
    tasks = {t for t in ("parse," * hybrid + local_tasks).split(",") if t}
    if tasks - set(cost.TASKS):
        raise click.UsageError(f"--local-tasks must be from {', '.join(cost.TASKS)}")
    if not mock and backend == "claude-code" and not have_claude_cli():
        raise click.ClickException("`claude` CLI not found. Install Claude Code, or use --mock / --backend omlx.")

    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    llm = build_llm(mock=mock, backend=backend, out_dir=out, model=model, max_tokens=max_tokens, record=record,
                    local_tasks=tasks if backend != "omlx" else set())
    phases: dict[str, float] = {}

    def step(name, label):
        click.echo(label)
        phases[name] = time.time()

    def done(name):
        phases[name] = round(time.time() - phases[name], 1)

    try:
        # 0. Are these the documents somebody signed off? (hash comparison, no AI)
        step("integrity", "[1/7] check documents against the approved baseline")
        drifts = []
        if Path(baseline).exists():
            drifts = integrity.find_drift(baseline, integrity.snapshot(srs, sys_path, legacy))
            click.echo(f"      {len(drifts)} unit(s) differ from the baseline" + (": " + ", ".join(d.id for d in drifts) if drifts else ""))
        else:
            click.echo(f"      no baseline at {baseline}; skipped (create one with: reqtrace baseline)")
        done("integrity")

        # 1. Document -> structured requirements
        step("parse", f"[2/7] parse SRS ({llm.backend})")
        reqs = parse.parse_srs(llm, srs)
        sys_ids = parse.parse_sys_ids(sys_path)
        (out / "requirements.json").write_text(json.dumps([r.model_dump() for r in reqs], indent=2) + "\n")
        click.echo(f"      {len(reqs)} requirements, {len(sys_ids)} system requirements")
        done("parse")

        step("measure", f"[3/7] judge which requirements are testable ({llm.backend})")
        reqs = parse.judge_measurability(llm, reqs)
        (out / "requirements.json").write_text(json.dumps([r.model_dump() for r in reqs], indent=2) + "\n")
        done("measure")

        # 2. Rules we can check with code, then the review that needs judgement
        step("analyze", "[4/7] deterministic checks + LLM analysis")
        det = checks.static_checks(reqs, sys_ids) + integrity.drift_findings(drifts)
        llm_findings, rejected = analyze_mod.analyze(llm, reqs)
        done("analyze")

        # 3. Old test steps -> reused or retired, new steps drafted
        step("draft", "[5/7] draft protocol, reuse legacy steps")
        legacy_steps = trace.load_legacy(legacy)
        steps, retired = trace.build(reqs, legacy_steps, draft_mod.draft(llm, reqs, legacy_steps))
        done("draft")

        step("trace", "[6/7] trace matrix + coverage checks")
        det += checks.coverage_checks(reqs, steps)
        trace.write_matrix(out / "trace_matrix.csv", reqs, steps)
        (out / "draft_protocol.md").write_text(draft_mod.render(steps, retired))
        done("trace")
    except LLMError as e:
        # Keep the evidence: which step died and why. The eval can still record this run in the ledger.
        (out / "failure.json").write_text(json.dumps({"error": str(e), "phases_s": phases, "backend": llm.backend, "model": llm.model}, indent=1) + "\n")
        raise click.ClickException(str(e)) from e

    click.echo("[7/7] report")
    findings, dup = report.merge(det + llm_findings)
    summary = build_summary(llm, mock, reqs, findings, rejected, dup, steps, retired, drifts, phases, time.time() - started, out)
    report.write(out, findings, summary)
    c = summary["counts"]
    click.echo(f"done: {c['total']} findings ({c.get('deterministic', 0)} deterministic, {c.get('llm', 0)} llm), "
               f"{rejected} rejected citations -> {out}/")


def build_summary(llm, mock, reqs, findings, rejected, dup, steps, retired, drifts, phases, wall_time, out):
    log = [json.loads(line) for line in (out / "llm_log.jsonl").read_text().splitlines()]
    covered = {i for s in steps for i in s.traces_to}
    retired_ids = {legacy.step for legacy, _ in retired}
    return {
        "mode": "mock (recorded fixtures)" if mock else f"live ({llm.backend}, {llm.model})",
        "model": llm.model,
        "requirements": len(reqs),
        "counts": {"total": len(findings), **Counter(f.source for f in findings),
                   **{s: sum(f.severity == s for f in findings) for s in report.ORDER}},
        "rejected_findings": rejected,
        "deduplicated_findings": dup,
        "trace": {"requirements_covered": sum(r.id in covered for r in reqs), "requirements_total": len(reqs),
                  "steps_reused": sum(s.origin == "reused" for s in steps), "steps_new": sum(s.origin == "new" for s in steps),
                  "legacy_retired": sorted(retired_ids)},
        # Out-of-process edits, plus whether the AI draft step independently refused to reuse the edited step.
        "drift": [{"id": d.id, "role": d.role, "kind": d.kind, "change": d.change,
                   "retired_by_draft": d.id in retired_ids} for d in drifts],
        "llm": {"calls": len(log), "retries": sum(r["attempt"] > 1 for r in log),
                "escalations": sum("escalated_from" in r for r in log),
                "input_tokens": sum(r["input_tokens"] for r in log), "output_tokens": sum(r["output_tokens"] for r in log),
                "latency_s": round(sum(r.get("recorded_latency_s", r["latency_s"]) for r in log), 1),
                "by_backend": cost.by_backend(log), "by_task": cost.by_task(log),
                "cost_usd_list": cost.list_cost(log), "profile": cost.profile(log)},
        "phases_s": phases,
        "wall_time_s": round(wall_time, 1),
    }


@main.command()
@click.option("--srs", default=f"{DATA}/novapump_srs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--sys", "sys_path", default=f"{DATA}/novapump_system_reqs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--legacy", default=f"{DATA}/legacy_protocol_v1.csv", type=click.Path(exists=True, path_type=Path))
@click.option("--baseline", default=f"{DATA}/baseline.json", type=click.Path(path_type=Path))
def baseline(srs, sys_path, legacy, baseline):
    """Sign off the current documents as the approved baseline (review the resulting file in a pull request)."""
    integrity.write_baseline(baseline, integrity.snapshot(srs, sys_path, legacy))
    click.echo(f"baseline written to {baseline}")


@main.command()
@click.option("--ledger", default="evals/ledger.jsonl", type=click.Path(exists=True, path_type=Path))
@click.option("--out", default="docs/dashboard.html", type=click.Path(path_type=Path))
def dashboard(ledger, out):
    """Build the single-file dashboard (local vs API: quality, cost, time, projection) from the eval ledger."""
    from .dashboard import build  # imported here: it is only needed for this command

    out.write_text(build(ledger))
    click.echo(f"dashboard written to {out}")
