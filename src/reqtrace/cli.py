import json
import time
from collections import Counter
from pathlib import Path

import click

from . import analyze as analyze_mod
from . import checks, parse, report, trace
from . import draft as draft_mod
from .llm import LLM, LLMError, have_claude_cli


@click.group()
def main():
    """ReqTrace: guardrailed SRS analysis (fictional Novapump NP-200)."""


@main.command()
@click.option("--srs", default="data/novapump_srs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--sys", "sys_path", default="data/novapump_system_reqs.md", type=click.Path(exists=True, path_type=Path))
@click.option("--legacy", default="data/legacy_protocol_v1.csv", type=click.Path(exists=True, path_type=Path))
@click.option("--out", default="out", type=click.Path(path_type=Path))
@click.option("--mock", is_flag=True, help="Replay recorded fixtures; no model, no key.")
@click.option("--backend", type=click.Choice(["claude-code", "anthropic"]), default="claude-code", show_default=True,
              help="claude-code uses your Claude Code login (no API key). anthropic needs ANTHROPIC_API_KEY.")
@click.option("--model", default=None, help="Default: sonnet (claude-code) or claude-sonnet-5-5 (anthropic).")
@click.option("--max-tokens", default=400_000, show_default=True, help="Abort if total tokens exceed this.")
@click.option("--record", is_flag=True, help="Save validated responses as mock fixtures (src/reqtrace/fixtures).")
def run(srs, sys_path, legacy, out, mock, backend, model, max_tokens, record):
    """Run the full pipeline and write findings, trace matrix, draft protocol and summary to --out."""
    if mock and record:
        raise click.UsageError("--record needs a real backend")
    if not mock and backend == "claude-code" and not have_claude_cli():
        raise click.ClickException("`claude` CLI not found. Install Claude Code, or use --mock / --backend anthropic.")
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    llm = LLM("mock" if mock else backend, out, model, max_tokens, record)
    try:
        click.echo(f"[1/5] parse SRS ({llm.backend})")
        reqs = parse.parse_srs(llm, srs)
        sys_ids = parse.parse_sys_ids(sys_path)
        (out / "requirements.json").write_text(json.dumps([r.model_dump() for r in reqs], indent=2) + "\n")
        click.echo(f"      {len(reqs)} requirements, {len(sys_ids)} system requirements")
        click.echo("[2/5] deterministic checks + LLM analysis")
        det = checks.static_checks(reqs, sys_ids)
        llm_findings, rejected = analyze_mod.analyze(llm, reqs)
        click.echo("[3/5] draft protocol, reuse legacy steps")
        legacy_steps = trace.load_legacy(legacy)
        steps, retired = trace.build(reqs, legacy_steps, draft_mod.draft(llm, reqs, legacy_steps))
        click.echo("[4/5] trace matrix + coverage checks")
        det += checks.coverage_checks(reqs, steps)
        trace.write_matrix(out / "trace_matrix.csv", reqs, steps)
        (out / "draft_protocol.md").write_text(draft_mod.render(steps, retired))
    except LLMError as e:
        raise click.ClickException(str(e)) from e
    click.echo("[5/5] report")
    findings, dup = report.merge(det + llm_findings)
    log = [json.loads(line) for line in (out / "llm_log.jsonl").read_text().splitlines()]
    covered = {i for s in steps for i in s.traces_to}
    summary = {
        "mode": "mock (recorded fixtures)" if mock else f"live ({llm.backend}, {llm.model})",
        "model": llm.model,
        "requirements": len(reqs),
        "counts": {"total": len(findings), **Counter(f.source for f in findings), **{s: sum(f.severity == s for f in findings) for s in report.ORDER}},
        "rejected_findings": rejected,
        "deduplicated_findings": dup,
        "trace": {"requirements_covered": sum(r.id in covered for r in reqs), "requirements_total": len(reqs),
                  "steps_reused": sum(s.origin == "reused" for s in steps), "steps_new": sum(s.origin == "new" for s in steps),
                  "legacy_retired": [l.step for l, _ in retired]},
        "llm": {"calls": len(log), "retries": sum(r["attempt"] > 1 for r in log),
                "input_tokens": sum(r["input_tokens"] for r in log), "output_tokens": sum(r["output_tokens"] for r in log),
                "latency_s": round(sum(r.get("recorded_latency_s", r["latency_s"]) for r in log), 1)},
        "wall_time_s": round(time.time() - t0, 1),
    }
    report.write(out, findings, summary)
    c = summary["counts"]
    click.echo(f"done: {c['total']} findings ({c.get('deterministic', 0)} deterministic, {c.get('llm', 0)} llm), "
               f"{rejected} rejected citations -> {out}/")
