# ReqTrace

[![ci](https://github.com/vladbondarenko97/reqtrace/actions/workflows/ci.yml/badge.svg)](https://github.com/vladbondarenko97/reqtrace/actions/workflows/ci.yml)

**An AI pipeline for regulated engineering that is built to be audited: it finds the gaps in a requirements specification, drafts the verification protocol, catches unapproved edits to controlled documents, and uses evidence, not preference, to decide which model is allowed to do which step.**

> The Novapump NP-200 insulin pump, its requirements and its legacy protocol are **fictional and synthetic**. Nothing here comes from a real product or document.

**[Live dashboard: local model vs API](https://vladbondarenko97.github.io/reqtrace/)** · [Decisions](docs/DECISIONS.md) · [Eval history](evals/history.md)

![make demo, end to end](docs/demo.gif)

## The result in 30 seconds

| | Result | Evidence |
|---|---|---|
| **Quality** | Caught **5 of 5** planted defects with **0 false positives**, on live runs | [`evals/latest_report.md`](evals/latest_report.md), [`evals/history.md`](evals/history.md) |
| **Cost** | Moving one step to a local 9B model cut the measured model cost **55%** on the demo ($0.195 → $0.088 per run) with no loss in quality | [`evals/ledger.jsonl`](evals/ledger.jsonl) |
| **Cost at scale** *(projection)* | About **44% lower** per run on a 100-200 page SRS; $1.80-$3.60 saved per run at illustrative prices | [Dashboard](docs/dashboard.html), calculator included |
| **Governance** | A cheaper model is only allowed to take a step if it passes the same quality gate. **Three of the four local routings we tested failed the gate and were rejected or redesigned.** | [Scorecard below](#which-model-should-do-which-step) |
| **Control** | Two unapproved edits to a controlled test protocol were flagged on **every run**, by two independent mechanisms | [Change-control drill](#change-control-drill) |
| **Reproducibility** | 35 tests plus a CI gate on every push (ruff, pytest, full replayed pipeline, eval at 5/5 with 0 false positives) | [CI](.github/workflows/ci.yml) |

A human engineer reviews and approves everything. Every output is stamped *DRAFT — requires engineer review. Not for execution.*

## The problem

In regulated device development, engineers cross-reference redlined requirements against legacy test protocols and trace matrices by hand. It is slow, and the gaps that slip through (a contradiction between two requirements, a behavior nobody wrote a requirement for, a test that traces to nothing) are found late, during physical testing. Two things make AI hard to adopt here: the output has to be defensible to an auditor, and the documents are often too sensitive, and too long, to send through a frontier model on every revision.

## What the pipeline does

```mermaid
flowchart LR
  SRS[/"SRS (markdown)"/] --> I
  SYS[/"System requirements"/] --> I
  LEG[/"Legacy protocol (CSV)"/] --> I
  BASE[/"Approved baseline"/] --> I["Baseline check<br/>hash compare, no AI"]
  I --> R0
  SRS --> P["parse in pieces<br/>local model, parallel"]
  P --> M["measure<br/>is it testable? (Claude)"]
  M --> REQ[("Requirements<br/>Pydantic")]
  REQ --> C1["Deterministic checks<br/>parents, enums, testable"]
  REQ --> A["analyze<br/>LLM review (Claude)"]
  A --> G{"Citation guardrail<br/>unknown ID: drop and count"}
  REQ --> D["draft<br/>reuse or retire legacy steps (Claude)"]
  D --> T["trace<br/>reused steps copied verbatim"]
  T --> C2["Deterministic checks<br/>every req has a test"]
  C1 --> R0["report"]
  G --> R0
  C2 --> R0
  I --> R0
  T --> MX[/"trace_matrix.csv<br/>draft_protocol.md"/]
  R0 --> F[/"findings.md<br/>summary.json"/]
  F --> E["Eval vs. answer key<br/>CI gate: 5/5, 0 false positives"]
  E --> L[("ledger.jsonl")] --> DB["Dashboard<br/>local vs API"]
  F --> H(["Engineer review<br/>and approval"])
  MX --> H
```

From a 25-requirement SRS it produces cited findings, a requirement-to-test trace matrix (every requirement has a test; every test traces to a real requirement) and a draft verification protocol that reuses the legacy steps that still apply and retires the ones that do not, with a reason for each.

## Which model should do which step?

Reading a 100-200 page SRS and a legacy protocol through a frontier model on every revision adds up, and some organizations cannot send those documents off-site at all. ReqTrace can run steps on a model on the same machine (oMLX, a 9B model here) and lets the eval decide what is allowed to move. Same documents, same prompts, same answer key; only the routing changes.

| Configuration | Defects | False pos. | Measured cost\* | Verdict |
|---|---|---|---|---|
| All steps on Claude | 5 / 5 | 0 | $0.195 | Reference |
| **Parse on the local 9B, rest on Claude** | **5 / 5** | **0** | **$0.088** | **Adopted** |
| Parse + analyze on the local 9B | 4 / 5 | 4 | $0.073 | Rejected: missed a defect, invented four |
| Everything on the local 9B | aborted at drafting | n/a | n/a | Rejected: could not produce valid output |
| *First hybrid attempt (local also judged testability)* | *5 / 5* | *2* | *$0.126* | *Rejected, then redesigned* |

\*Per-call list cost as reported by the Claude Code CLI itself, including a fixed per-call overhead the raw API would not have. The local model's electricity is about a cent.

![routing dashboard](docs/dashboard.png)

What this taught us, and the rule it justifies:
- **Transcribing a document is safe to hand to a small local model.** It reproduced Claude's parse on 25 of 25 requirements, field by field.
- **Judgement is not.** In the first hybrid attempt the local model also decided which requirements are testable, disagreed with Claude on two, and created two false positives. The gate caught it. Testability became its own small step that stays on Claude (decision D-17).
- **Analysis and drafting stay on Claude.** On the 9B model, analysis missed one planted defect and invented four; drafting failed validation (it reused one old test step twice), identically on both attempts to run it. At temperature 0 local failures are repeatable, which makes them debuggable.
- **A local answer that fails validation is escalated to Claude** instead of failing the run, and the escalation is logged.

Open the [live dashboard](https://vladbondarenko97.github.io/reqtrace/) (source: [`docs/dashboard.html`](docs/dashboard.html)) for the scorecard, the per-defect grid, the calculator (sliders for pages, price and runs per year), the drill table and the routing policy with the evidence behind each choice. It is a single file with no server and no external requests.

## Cost at scale

The demo's measured token profile, scaled to a larger document. This is a **projection**: 650 tokens per page, the fixed system prompt charged per call, long steps split across calls, and illustrative rates of $3 / $15 per million tokens in / out (change them in `src/reqtrace/pricing.json` or in the dashboard).

| SRS size | All on Claude, per run | Parse local, per run | Saved per run | Local model time\*\* |
|---|---|---|---|---|
| 100 pages | $4.07 | $2.27 | $1.80 (44%) | about 36 min |
| 150 pages | $6.10 | $3.40 | $2.70 (44%) | about 54 min |
| 200 pages | $8.13 | $4.53 | $3.60 (44%) | about 72 min |

\*\*At the 47 tokens per second the local model sustained across four parallel pieces on the test machine.

The honest reading: per-run savings are real but modest. The case gets stronger with many documents and many revision cycles (at 50 runs a year, 150 pages: about $135), and the larger argument is data residency: the bulk of the text, the transcription, never leaves the machine. The trade is time, which suits an overnight batch and not a live review. Not modeled: prompt caching, batch discounts and negotiated rates.

## Controls: how it earns trust

| Risk | Control | Where it is proven |
|---|---|---|
| Model returns malformed output | Every response is validated against a Pydantic schema; one retry with the error fed back, then the run fails loudly | `tests/` (retry succeeds, retry fails) |
| Model invents a requirement | **Citation or reject:** a finding must cite IDs that exist; anything else is dropped and counted | `tests/` (guardrail); 0 fired on live runs |
| Model rewrites a test step | Reused legacy steps are copied verbatim from the source file, never from model output | `trace.py`, D-08 |
| Model misses or invents on a judgement | Rules that can be code are code (parents exist, enums valid, every requirement has a test); the model only does what needs judgement | `checks.py`, D-06 |
| A cheaper model degrades quality | **Eval-gated routing:** a step runs locally only if the ledger shows the configuration passing 5/5 with 0 false positives | Scorecard above, D-18 |
| Local model fails mid-run | Escalated to the strong model, written to the log | `router.py`, tests |
| Controlled documents are edited without approval | **Baseline check:** hash comparison against the approved copy, plus an independent AI review | [Drill](#change-control-drill) |
| Runaway spend | `--max-tokens` aborts the run (checked before every call) | `llm.py`, tests |
| Nobody can reconstruct what happened | Every call is logged: model, backend, tokens, seconds, validation result, escalations | `out/llm_log.jsonl` |
| Pipeline regresses silently | CI replays recorded model responses through the full pipeline and fails on any miss or false positive | `.github/workflows/ci.yml` |
| Output is mistaken for approved | Every artifact is stamped as a draft that requires engineer review | `draft.py` |

## Change-control drill

A verification protocol is only as trustworthy as the documents it was built from. As a drill, two values in the legacy protocol were edited after sign-off, the way a well-meaning engineer might do it without knowing the process: **L-16** (low-battery alarm threshold 20% → 25%) and **L-19** (set date **and time** → date only, plus a typo). Nothing else changed.

Two independent layers caught it on every live run:

1. **Baseline check (deterministic).** `reqtrace baseline` freezes the approved documents; every run diffs against that copy and emits a high-severity `baseline_drift` finding per edited unit, with the changed words. Editor noise (line endings, trailing newline) is ignored: git shows the whole CSV as changed, only two rows actually differ.
2. **The AI draft step.** It judged both edited steps against the requirements and refused to reuse them: a 25% discharge would not trigger the 20% alarm, and a date-only step no longer covers the date-and-time requirement.

The hash check cannot be argued with and catches edits that look perfectly reasonable; the model explains *why* an edit matters. Neither replaces the other. Detection, not prevention: it does not stop anyone from editing a file. The drill edit is committed on purpose so the baseline keeps flagging it, and a test asserts exactly L-16 and L-19.

## Eval detail

Planted answer key: 5 defects hidden in a 25-requirement synthetic SRS ([`data/ground_truth.json`](data/ground_truth.json), written before any code). From [`evals/latest_report.md`](evals/latest_report.md), a live run with `parse` on a local 9B model and everything else on Claude:

| What we measured | Result |
|---|---|
| Planted defects caught | **5 / 5** |
| False positives (findings not in the answer key) | **0** |
| Hallucinated citations rejected by the guardrail | 0 |
| Out-of-process edits flagged (baseline drift) | L-16, L-19 |
| Findings from deterministic checks / from the LLM | 4 / 3 |
| Obsolete legacy test steps correctly retired | 8 / 8 |
| Requirements with at least one test step | 25 / 25 |

| Planted defect | Type | Requirements | Caught by |
|---|---|---|---|
| D1 | contradiction | NP-REQ-009, NP-REQ-011 | LLM |
| D2 | missing_requirement | NP-REQ-014 | LLM |
| D3 | incomplete_enumeration | NP-REQ-001, NP-REQ-024 | LLM |
| D4 | untestable | NP-REQ-018 | deterministic rule |
| D5 | orphan_trace | NP-REQ-025 | deterministic rule |

The full history, including the failures and why they happened, is in [`evals/history.md`](evals/history.md) and [`docs/DECISIONS.md`](docs/DECISIONS.md). Short version: the first run was 4/5 (my prompt was too cautious); later runs produced false positives because the reviewer found two real gaps I had accidentally left in my own synthetic SRS, and **I fixed the input, not the answer key**; and the first attempt to run more of the pipeline locally failed the gate and was redesigned.

## Taking this into an enterprise

A staged path, each stage with an exit criterion measured by the same eval:

1. **Shadow mode.** Run beside the current manual process on a closed project. Exit: recall on known historical defects, false-positive rate an engineer will tolerate.
2. **Connect.** Swap the model backend for the organization's approved endpoint (one file: `llm.py`), put SSO in front, write the LLM log to the audit system, read the SRS and trace links from the requirements tool instead of files.
3. **Localize.** Re-run the routing comparison on real documents. Anything the local model passes (start with transcription) stays on-premises; everything else uses the approved hosted model. The decision is data, not opinion.
4. **Gate.** The planted-defect eval runs on every prompt or model change, as a regression gate. The same gate qualifies a new or cheaper model.

The engineer stays the approver at every stage.

## What this does not prove

- **Scale.** 25 requirements and 5 defects is a demo, not a benchmark. Full recall here says little about recall on a 200-page real document, and the local model's accuracy at that size is untested.
- **Cost.** Only demo-size costs are measured. The larger numbers are projections with illustrative prices.
- **Repeatability on hosted models.** Current Claude models reject temperature 0, so live runs vary slightly (D-03). That is why CI replays recorded responses, and why the live history shows every run, not a best one.
- **One hosted model family** and **one 9B local model** were evaluated. The `anthropic` SDK backend exists but is untested here (no API key was available).
- The guardrail that rejects invented citations has never fired on live output; it is proven by a unit test only.
- Detection of unapproved edits is not prevention.

## Try it

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'
make demo MOCK=1        # replays recorded responses: no model, no key
make demo               # live, through your Claude Code login (needs the `claude` CLI; no API key)
make demo HYBRID=1      # parse on a local oMLX model, judgement on Claude (needs oMLX running)
make demo BACKEND=omlx  # everything on the local model (it will not pass; see above)
make compare            # all routings live, scored into evals/ledger.jsonl (about 15 minutes)
make dashboard          # rebuild docs/dashboard.html from the ledger and open it in your browser
make test               # ruff + pytest
```

Outputs land in `out/`: `findings.md`, `trace_matrix.csv`, `draft_protocol.md`, `summary.json`, `llm_log.jsonl`. A real run is saved in [`docs/sample_output/`](docs/sample_output/). The local backend reads the oMLX key from `OMLX_API_KEY` or from oMLX's own settings file on your machine; it is never stored in this repo.

## Repo map

| Path | What it is |
|---|---|
| `src/reqtrace/llm.py` | The one place that talks to a model: four backends, schema validation, retry, budget, log |
| `src/reqtrace/router.py` | Which step runs on which backend; escalation of failed local answers |
| `src/reqtrace/parse.py`, `analyze.py`, `draft.py` | The three model steps, each with its checks |
| `src/reqtrace/checks.py`, `integrity.py` | Deterministic rules and the baseline check |
| `src/reqtrace/cost.py`, `dashboard.py` | Measured vs projected cost; the single-file dashboard |
| `evals/` | Scoring against the answer key, run history, the ledger the dashboard reads |
| `data/` | Synthetic SRS, system requirements, legacy protocol, answer key, approved baseline |
| `docs/` | [Orchestrator prompt](docs/ORCHESTRATOR_PROMPT.md) → [Plan](docs/PLAN.md) → [Decisions and eval iterations](docs/DECISIONS.md) (21 decisions, every failed run included) |

## Everything here is synthetic

The Novapump NP-200 does not exist. The device, its requirements, the "NP-100" legacy protocol and every identifier were invented for this demo; no real product, company or document was used as a source.
