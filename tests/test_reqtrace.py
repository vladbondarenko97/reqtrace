import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from reqtrace import analyze, checks, parse, trace
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

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def req(id="NP-REQ-001", **kw):
    d = dict(id=id, title="t", text="The pump shall do X within 5 s.", feature="F", modes=["Basal"],
             profiles=["Adult"], traces_to="NP-SYS-001", measurable=True)
    return Requirement(**{**d, **kw})


def step(id, traces, **kw):
    return Step(**{**dict(id=id, feature="F", action="a", expected_result="e", traces_to=traces, origin="new"), **kw})


# 1. schema
def test_requirement_valid():
    assert req().id == "NP-REQ-001"


@pytest.mark.parametrize("kw", [{"id": "REQ-1"}, {"traces_to": "SYS-1"}, {"text": ""}])
def test_requirement_rejects(kw):
    with pytest.raises(ValidationError):
        req(**kw)


def test_requirement_missing_measurable():
    with pytest.raises(ValidationError):
        Requirement(id="NP-REQ-001", title="t", text="x", feature="F")


def test_parseout_empty():
    with pytest.raises(ValidationError):
        ParseOut(requirements=[])


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
    with pytest.raises(LLMError, match="stale"):
        LLM("mock", tmp_path).ask("parse", "changed input", ParseOut)


def test_budget_and_log(tmp_path):
    llm = LLM("mock", tmp_path, max_tokens=1)
    llm.ask("parse", (DATA / "novapump_srs.md").read_text(), ParseOut)
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
