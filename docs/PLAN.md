# ReqTrace — Plan

Written and committed **before any code**. Deviations are recorded in `DECISIONS.md`.

## Goal
SRS in → structured requirements → deterministic checks + cited LLM findings → trace matrix → draft verification protocol (human-approved) → scored against planted ground truth, gated in CI.

## Data flow
```
novapump_srs.md ──► parse (LLM) ──► [Requirement]
                                     │
novapump_system_reqs.md ─────────────┼─► checks.static  (no AI)   ─┐
                                     ├─► analyze (LLM + citation guardrail) ─┤
legacy_protocol_v1.csv ──► draft (LLM) ──► trace.build ──► checks.coverage (no AI) ─┤
                                     │                               │
                                     └──► draft_protocol.md, trace_matrix.csv   ▼
                                                              report → findings.md, summary.json
                                                              evals/run_eval.py → latest_report.md (CI gate)
```

## Modules (`src/reqtrace/`)
| file | responsibility |
|---|---|
| `models.py` | Pydantic contracts: `Requirement`, `SysReq`, `LegacyStep`, `Finding`, `DraftStep`, `DraftResult` |
| `llm.py` | One `LLM` class, three backends: `claude-code` (default; shells out to `claude -p`), `anthropic` (SDK, optional), `mock` (recorded fixtures). Handles pinned prompts, JSON→Pydantic, 2 attempts, `llm_log.jsonl`, token budget, `--record` |
| `parse.py` | SRS markdown → `list[Requirement]` (LLM) |
| `checks.py` | Deterministic checks: static (parent exists, enum values, unmeasurable flag) and coverage (req has ≥1 test, test traces to real req, enum values in tests) |
| `analyze.py` | LLM review → `Finding`s; citation guardrail drops findings citing unknown IDs and counts them |
| `draft.py` | LLM classifies legacy steps (reused / retired) and writes new steps; renders `draft_protocol.md` |
| `trace.py` | Merges reused + new steps into the matrix; reused steps take text verbatim from the legacy CSV; writes `trace_matrix.csv` |
| `report.py` | `findings.md` (grouped by severity) + `summary.json` |
| `cli.py` | `reqtrace run …` |
| `prompts/*.md` | Pinned system prompts, one per LLM task |

Everything else: `evals/run_eval.py`, `tests/`, `Makefile`, `.github/workflows/ci.yml`, `data/`.

## Data contracts
- `Requirement`: id (`NP-REQ-\d{3}`), title, text, feature, modes[], profiles[], traces_to (`NP-SYS-\d{3}` or null), measurable.
- `Finding`: id, source (`deterministic`|`llm`), type, severity (`high|medium|low`), cited_ids (≥1), rationale.
  Types: `contradiction`, `missing_requirement`, `incomplete_enumeration`, `untestable`, `orphan_trace`, `invalid_enum_value`, `no_test`, `test_unknown_req`.
  The LLM may only emit the first four.
- `llm_log.jsonl` row: task, backend, model, attempt, input/output tokens, latency_s, valid, error.
- `summary.json`: counts, `rejected_findings`, `findings[]`, tokens, wall time, trace coverage.

## Backends (decision D-01)
`claude-code` is the default so no API key is needed: each call is `claude -p` from an empty temp cwd, no tools, no MCP, no skills, JSON output. `anthropic` is a one-flag alternative. `--mock` replays fixtures that were **recorded from a real `claude-code` run** (`--record`), keyed to a hash of the prompt so stale fixtures fail loudly.

## Evals
Match rule: an emitted finding matches a planted defect if `type` equal and `cited_ids ∩ defect.ids ≠ ∅`. Matching extra findings do not count as false positives; anything else does. Gate: recall 5/5, FP 0. Each real run appended to `evals/history.md` by the script itself.

## Delegation plan
The session running this build is Sonnet-class (no Opus available), so "orchestrator" work and the delegated work run on the same model family; the split is still followed.
| Task | Owner | Acceptance |
|---|---|---|
| Phase 1 data, architecture, prompts, eval design, iterating prompts | orchestrator (judgment, defines ground truth) | PLAN/DECISIONS honest; 5 defects match the brief |
| Pipeline modules (`llm`, `parse`, `checks`, `analyze`, `draft`, `trace`, `report`, `cli`) | orchestrator (interacting contracts) | `reqtrace run --mock` succeeds |
| **Phase 4 tests** (`tests/`) | **Sonnet subagent** — bounded, objective | `pytest` green; covers every check positive+negative, the NP-REQ-999 guardrail, trace completeness, full mock run; no changes to `src/` without reporting |
| CI workflow, Makefile | orchestrator (small, tied to eval gate) | CI < 2 min |
| README, GIF | orchestrator | all 8 sections present |

Every delegated result is verified by re-running `pytest` and the eval before acceptance.
