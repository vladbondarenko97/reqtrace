import csv
import io
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from reqtrace import analyze, checks, cost, integrity, parse, trace
from reqtrace.cli import main
from reqtrace.llm import LLM, BudgetExceeded, LLMError, extract_json
from reqtrace.models import (
    AnalyzeOut,
    DraftOut,
    DraftStepOut,
    LLMFinding,
    ParseOut,
    Requirement,
    RetiredOut,
    Step,
)
from reqtrace.router import Router

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def req(id="NP-REQ-001", **kw):
    d = dict(id=id, title="t", text="The pump shall do X within 5 s.", feature="F", modes=["Basal"],
             profiles=["Adult"], traces_to="NP-SYS-001", measurable=True)
    return Requirement(**{**d, **kw})


def step(id, traces, **kw):
    return Step(**{**dict(id=id, feature="F", action="a", expected_result="e", traces_to=traces, origin="new"), **kw})


# 1. schema
@pytest.mark.parametrize("kw", [{"id": "REQ-1"}, {"traces_to": "SYS-1"}, {"text": ""}])
def test_requirement_rejects(kw):
    with pytest.raises(ValidationError):
        req(**kw)


def test_measurable_defaults_true_until_the_measure_step_decides():
    assert Requirement(id="NP-REQ-001", title="t", text="x", feature="F").measurable is True


def test_llmfinding_rejects():
    ok = dict(type="contradiction", severity="high", cited_ids=["NP-REQ-001"], rationale="r")
    LLMFinding(**ok)
    with pytest.raises(ValidationError):
        LLMFinding(**{**ok, "cited_ids": []})
    with pytest.raises(ValidationError):
        LLMFinding(**{**ok, "type": "no_test"})


# 2. static checks
def one(fs, type_, ids):
    assert len(fs) == 1 and fs[0].source == "deterministic" and fs[0].type == type_ and fs[0].cited_ids == ids


def test_static_clean():
    assert checks.static_checks([req()], {"NP-SYS-001"}) == []


def test_orphan_trace():
    one(checks.static_checks([req()], {"NP-SYS-002"}), "orphan_trace", ["NP-REQ-001"])


@pytest.mark.parametrize("kw", [{"modes": ["Turbo"]}, {"profiles": ["Elderly"]}])
def test_invalid_enum(kw):
    one(checks.static_checks([req(**kw)], {"NP-SYS-001"}), "invalid_enum_value", ["NP-REQ-001"])


def test_untestable():
    one(checks.static_checks([req(measurable=False)], {"NP-SYS-001"}), "untestable", ["NP-REQ-001"])


# 3. coverage checks
def test_no_test():
    one(checks.coverage_checks([req()], []), "no_test", ["NP-REQ-001"])
    assert checks.coverage_checks([req()], [step("TC-001", ["NP-REQ-001"])]) == []


def test_test_unknown_req():
    one(checks.coverage_checks([req()], [step("TC-001", ["NP-REQ-001", "NP-REQ-099"])]), "test_unknown_req", ["TC-001"])


# 4. guardrail
def lf(ids):
    return LLMFinding(type="contradiction", severity="high", cited_ids=ids, rationale="r")


def test_guardrail():
    known = {"NP-REQ-001"}
    kept, rej = analyze.apply_guardrail(AnalyzeOut(findings=[lf(["NP-REQ-999"])]), known)
    assert (kept, rej) == ([], 1)
    kept, rej = analyze.apply_guardrail(AnalyzeOut(findings=[lf(["NP-REQ-001", "NP-REQ-999"])]), known)
    assert (kept, rej) == ([], 1)
    kept, rej = analyze.apply_guardrail(AnalyzeOut(findings=[lf(["NP-REQ-001"])]), known)
    assert rej == 0 and len(kept) == 1 and kept[0].source == "llm"


# 5. LLM layer
def rows(llm):
    return [json.loads(x) for x in llm.log_path.read_text().splitlines()]


def test_extract_json_fence():
    assert json.loads(extract_json('```json\n{"a": 1}\n```')) == {"a": 1}


def test_mock_stale_fixture(tmp_path):
    with pytest.raises(LLMError, match="no recorded fixture"):
        LLM("mock", tmp_path).ask("parse", "changed input", ParseOut)


def test_budget_and_log(tmp_path):
    llm = LLM("mock", tmp_path, max_tokens=1)
    llm.ask("parse", parse.split_srs((DATA / "novapump_srs.md").read_text())[0], ParseOut)
    with pytest.raises(BudgetExceeded):
        llm.ask("analyze", "x", AnalyzeOut)
    r = rows(llm)
    assert len(r) == 1
    assert {"task", "model", "input_tokens", "output_tokens", "latency_s", "valid"} <= r[0].keys()


# 6. retry
def fake(tmp_path, *texts):
    llm = LLM("claude-code", tmp_path)
    it = iter(texts)
    llm._call = lambda task, system, prompt, h: (next(it), 1, 1, {})
    return llm


def test_retry_succeeds(tmp_path):
    llm = fake(tmp_path, "not json", '{"findings": []}')
    assert llm.ask("analyze", "x", AnalyzeOut).findings == []
    assert [r["valid"] for r in rows(llm)] == [False, True]


def test_retry_fails(tmp_path):
    llm = fake(tmp_path, "nope", "still nope")
    with pytest.raises(LLMError):
        llm.ask("analyze", "x", AnalyzeOut)
    assert len(rows(llm)) == 2


# 7. trace
def test_trace_build_and_matrix(tmp_path):
    legacy = trace.load_legacy(DATA / "legacy_protocol_v1.csv")
    l1, l2, l3 = legacy[:3]
    reqs = [req("NP-REQ-001"), req("NP-REQ-002"), req("NP-REQ-003")]
    d = DraftOut(
        steps=[
            DraftStepOut(action="REWRITTEN", expected_result="REWRITTEN", traces_to=["NP-REQ-001"], legacy_step=l1.step),
            DraftStepOut(action="new act", expected_result="new exp", traces_to=["NP-REQ-001", "NP-REQ-002"]),
        ],
        retired=[RetiredOut(legacy_step=l2.step, reason="obsolete")],
    )
    steps, retired = trace.build(reqs, legacy, d)
    assert [s.id for s in steps] == ["TC-001", "TC-002"]
    assert steps[0].origin == "reused"
    assert (steps[0].action, steps[0].expected_result) == (l1.action, l1.expected_result)
    assert steps[1].action == "new act"
    ids = [l.step for l, _ in retired]
    assert l2.step in ids and l3.step in ids and l1.step not in ids
    assert len(ids) == len(legacy) - 1

    p = tmp_path / "m.csv"
    trace.write_matrix(p, reqs, steps)
    out = list(csv.DictReader(p.open()))
    assert [(r["requirement_id"], r["step_id"]) for r in out] == [
        ("NP-REQ-001", "TC-001"), ("NP-REQ-001", "TC-002"), ("NP-REQ-002", "TC-002"), ("NP-REQ-003", "")]
    assert out[-1]["origin"] == "NO TEST"


# 8. full mock pipeline
def test_sys_ids():
    ids = parse.parse_sys_ids(DATA / "novapump_system_reqs.md")
    assert len(ids) == 8 and "NP-SYS-007" not in ids


def test_full_mock_run(tmp_path):
    res = CliRunner().invoke(main, [
        "run", "--mock", "--out", str(tmp_path),
        "--srs", str(DATA / "novapump_srs.md"), "--sys", str(DATA / "novapump_system_reqs.md"),
        "--legacy", str(DATA / "legacy_protocol_v1.csv")])
    assert res.exit_code == 0, res.output
    for f in ["findings.md", "summary.json", "trace_matrix.csv", "draft_protocol.md", "llm_log.jsonl"]:
        assert (tmp_path / f).exists(), f
    assert "DRAFT — requires engineer review. Not for execution." in (tmp_path / "draft_protocol.md").read_text()
    s = json.loads((tmp_path / "summary.json").read_text())
    assert s["requirements"] == 25 and s["trace"]["requirements_covered"] == 25
    # the edited legacy steps are flagged by the baseline check and refused by the AI draft step
    assert {d["id"] for d in s["drift"]} == {"L-16", "L-19"} and all(d["retired_by_draft"] for d in s["drift"])

    report = ROOT / "evals/latest_report.md"
    backup = report.read_bytes() if report.exists() else None
    try:
        p = subprocess.run([sys.executable, str(ROOT / "evals/run_eval.py"), "--out", str(tmp_path), "--mock"],
                           cwd=ROOT, capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr
    finally:
        if backup is None:
            report.unlink(missing_ok=True)
        else:
            report.write_bytes(backup)


# 9. chunked parse
SRS = (DATA / "novapump_srs.md").read_text()


def test_split_srs_keeps_every_requirement_once():
    pieces = parse.split_srs(SRS, size=7)
    ids = [i for p in pieces for i in parse.REQ_HEADING.findall(p)]
    assert len(pieces) == 4 and ids == parse.REQ_HEADING.findall(SRS) and len(set(ids)) == 25


# 10. router: local first, escalate to the strong model, log it
def routed(tmp_path, local_texts, strong_texts):
    strong, local = LLM("claude-code", tmp_path), LLM("omlx", tmp_path, reset_log=False)
    for llm, texts in ((strong, strong_texts), (local, local_texts)):
        it = iter(texts)
        llm._call = lambda task, system, prompt, h, it=it: (next(it), 1, 1, {})
    return Router(strong, local, {"analyze"}), strong


def test_router_sends_each_task_to_its_backend(tmp_path):
    r, strong = routed(tmp_path, ['{"findings": []}'], ['{"findings": []}'])
    r.ask("analyze", "x", AnalyzeOut)
    assert [x["backend"] for x in rows(strong)] == ["omlx"]  # shared log: only the local model answered
    assert r.escalations == 0


def test_router_escalates_when_local_fails_twice(tmp_path):
    r, strong = routed(tmp_path, ["junk", "junk"], ['{"findings": []}'])
    assert r.ask("analyze", "x", AnalyzeOut).findings == []
    log = rows(strong)
    assert [x["backend"] for x in log] == ["omlx", "omlx", "claude-code"]
    assert log[-1]["escalated_from"] == "omlx" and r.escalations == 1


def test_non_local_task_never_touches_local(tmp_path):
    r, strong = routed(tmp_path, [], ['{"findings": []}'])
    r.local_tasks = set()
    r.ask("analyze", "x", AnalyzeOut)
    assert [x["backend"] for x in rows(strong)] == ["claude-code"]


def test_omlx_request_shape(tmp_path, monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"], seen["auth"] = json.loads(req.data), req.get_header("Authorization")
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": '{"findings": []}'}}],
                                      "usage": {"prompt_tokens": 7, "completion_tokens": 3}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("OMLX_API_KEY", "test-key")
    assert LLM("omlx", tmp_path).ask("analyze", "x", AnalyzeOut).findings == []
    assert seen["auth"] == "Bearer test-key" and seen["body"]["temperature"] == 0
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert rows(LLM("omlx", tmp_path, reset_log=False))[0]["input_tokens"] == 7


# 11. baseline integrity
def make_docs(tmp_path, legacy_csv=None):
    (tmp_path / "srs.md").write_text(SRS)
    (tmp_path / "sys.md").write_text((DATA / "novapump_system_reqs.md").read_text())
    (tmp_path / "legacy.csv").write_text(legacy_csv or (DATA / "legacy_protocol_v1.csv").read_text())
    return [tmp_path / n for n in ("srs.md", "sys.md", "legacy.csv")]


def test_drift_finds_exact_edits_and_ignores_line_endings(tmp_path):
    base = tmp_path / "base.json"
    integrity.write_baseline(base, integrity.snapshot(*make_docs(tmp_path)))
    approved = (tmp_path / "legacy.csv").read_text()
    assert integrity.find_drift(base, integrity.snapshot(*make_docs(tmp_path, approved.replace("\n", "\r\n")))) == []
    d = integrity.find_drift(base, integrity.snapshot(*make_docs(tmp_path, approved.replace("to 25%", "to 30%"))))
    assert [(x.id, x.kind, x.change) for x in d] == [("L-16", "changed", '"25%" -> "30%"')]
    f = integrity.drift_findings(d)[0]
    assert f.type == "baseline_drift" and f.cited_ids == ["L-16"] and f.severity == "high"


def test_committed_baseline_flags_the_drill_edits():
    d = integrity.find_drift(DATA / "baseline.json", integrity.snapshot(
        DATA / "novapump_srs.md", DATA / "novapump_system_reqs.md", DATA / "legacy_protocol_v1.csv"))
    assert sorted(x.id for x in d) == ["L-16", "L-19"]


# 12. cost model
ROW = dict(valid=True, backend="omlx", latency_s=1, attempt=1)


def log_rows():
    mk = lambda task, tin, out, user: {**ROW, "task": task, "input_tokens": tin, "output_tokens": out,
                                       "system_chars": 1000, "user_chars": user}
    return [mk("parse", 1000, 1400, 3000), mk("parse", 1000, 1400, 3000), mk("measure", 800, 20, 2500),
            mk("analyze", 2000, 300, 7000), mk("draft", 3000, 1500, 9000)]


def test_profile_splits_content_from_prompt_overhead():
    p = cost.profile(log_rows())
    assert p["parse"]["calls"] == 2 and p["parse"]["content_in"] == 1500.0 and p["parse"]["sys_in"] == 250.0


def test_projection_grows_with_size_and_hybrid_is_cheaper():
    prof = cost.profile(log_rows())
    small, big = cost.scenarios(prof, 50), cost.scenarios(prof, 200)
    for name in cost.SCENARIOS:
        assert big[name]["usd"] > small[name]["usd"] > 0
    assert big["Hybrid (parse on local model)"]["usd"] < big["All frontier"]["usd"]
    assert big["Hybrid (parse on local model)"]["tasks"]["parse"]["usd"] == 0


def test_by_backend_uses_recorded_backend_for_replays():
    r = {**log_rows()[0], "backend": "mock", "recorded_backend": "omlx"}
    assert list(cost.by_backend([r])) == ["omlx"]


def test_measurability_is_a_separate_judgement(tmp_path):
    reqs = [req("NP-REQ-001"), req("NP-REQ-002")]
    llm = fake(tmp_path, '{"not_measurable": ["NP-REQ-002"]}')
    out = parse.judge_measurability(llm, reqs)
    assert [(r.id, r.measurable) for r in out] == [("NP-REQ-001", True), ("NP-REQ-002", False)]
    # an ID the model invented is rejected by the check, like every other answer
    bad = fake(tmp_path, '{"not_measurable": ["NP-REQ-099"]}', '{"not_measurable": []}')
    assert all(r.measurable for r in parse.judge_measurability(bad, reqs))
    assert [r["valid"] for r in rows(bad)] == [False, True]


# 13. dashboard
def test_dashboard_builds_from_the_committed_ledger():
    from reqtrace.dashboard import build

    page = build(ROOT / "evals/ledger.jsonl")
    assert page.startswith("<!doctype html>") and "__DATA__" not in page and "Hybrid" in page
    assert "api_key" not in page.lower()  # nothing secret can reach the page


# 14. the CI gate itself: prove it fails when it should
def run_gate(out_dir):
    """Run evals/run_eval.py on an output folder; restore the committed report afterwards."""
    report = ROOT / "evals/latest_report.md"
    backup = report.read_bytes()
    try:
        return subprocess.run([sys.executable, str(ROOT / "evals/run_eval.py"), "--out", str(out_dir), "--mock"],
                              cwd=ROOT, capture_output=True, text=True)
    finally:
        report.write_bytes(backup)


def mock_run(out_dir):
    res = CliRunner().invoke(main, ["run", "--mock", "--out", str(out_dir)])
    assert res.exit_code == 0, res.output
    return json.loads((out_dir / "summary.json").read_text())


def rewrite(out_dir, summary, findings_md):
    (out_dir / "summary.json").write_text(json.dumps(summary))
    (out_dir / "findings.md").write_text(findings_md)


def test_gate_passes_on_the_clean_run(tmp_path):
    mock_run(tmp_path)
    assert run_gate(tmp_path).returncode == 0


def test_gate_fails_when_a_planted_defect_is_missed(tmp_path):
    summary = mock_run(tmp_path)
    d2 = next(f for f in summary["findings"] if f["type"] == "missing_requirement")  # the catch for planted defect D2
    summary["findings"] = [f for f in summary["findings"] if f["id"] != d2["id"]]
    md = (tmp_path / "findings.md").read_text()
    start = md.index(f"### {d2['id']}")
    nxt = md.find("\n### ", start + 1)
    rewrite(tmp_path, summary, md[:start] + (md[nxt + 1 :] if nxt != -1 else ""))
    p = run_gate(tmp_path)
    assert p.returncode == 1 and "MISSED" in p.stdout


def test_gate_fails_on_a_false_positive(tmp_path):
    summary = mock_run(tmp_path)
    extra = {"id": "F-099", "source": "llm", "type": "contradiction", "severity": "low",
             "cited_ids": ["NP-REQ-003"], "rationale": "not in the answer key"}
    summary["findings"].append(extra)
    md = (tmp_path / "findings.md").read_text() + "\n### F-099 · contradiction · llm\n- **Cited:** NP-REQ-003\n- **Rationale:** x\n"
    rewrite(tmp_path, summary, md)
    p = run_gate(tmp_path)
    assert p.returncode == 1 and "False positives" in p.stdout
