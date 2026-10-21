# Changelog

Releases are tagged `vX.Y.Z`. Every tag re-runs the full gate (ruff, pytest, the replayed pipeline and the eval at 5/5 with 0 false positives) before anything is published. Newest first.

## 0.2.0 — 2026-10-21

### Added
- Local-model backend (`omlx`, OpenAI-compatible, temperature 0) and a router that sends each step to the backend its policy names, escalating a failed local answer to Claude.
- Parse in parallel pieces; a separate `measure` step for testability after the first hybrid attempt failed the gate (D-17).
- Baseline check for the input documents: `reqtrace baseline`, `baseline_drift` findings.
- Cost model (measured vs projected) and a single-file dashboard (`reqtrace dashboard`, published on GitHub Pages).
- Eval ledger (`evals/ledger.jsonl`), per-run parse fidelity, aborted runs recorded as evidence.
- Release workflow: gate, wheel build and smoke test, GitHub Release, Pages deploy.
- Tests proving the CI gate fails on a missed defect and on a false positive.

### Changed
- Fixtures are one file per call, keyed by a hash of system prompt and input.
- Readability pass over every module.

### Removed
- Two filler tests (a self-equality assertion and an empty-list check) that did not guard a real risk.

## 0.1.0 — 2026-10-20
- First version: parse, deterministic checks, LLM analysis with the citation guardrail, trace matrix, draft protocol, evals and CI.
