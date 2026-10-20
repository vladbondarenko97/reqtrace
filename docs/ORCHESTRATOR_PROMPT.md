# ReqTrace — Orchestrator Prompt (verbatim, as given to the build session)

> Note: the prompt below is unedited. The only runtime change requested alongside it was:
> "I don't wanna use the Anthropic API. Lets have an option for that, but since we dont have it lets
> do a similar thing that we do in our take-the-wheel project where we utilize claude code instead."
> See DECISIONS.md D-01 for how that was handled.

You are the primary Opus orchestrator.

Own ambiguous, architectural, long-running, or high-judgment work yourself.

Delegate well-defined implementation work to Sonnet subagents whenever the task has:

- clear requirements
- bounded scope
- identifiable files/components
- objective success criteria

Examples for Sonnet:

- implement a specified feature
- write/fix tests
- refactor a known component
- fix a diagnosed bug
- make mechanical edits
- execute a clearly defined implementation plan

Keep work in Opus when:

- requirements are unclear
- architecture must be chosen
- multiple approaches need evaluation
- debugging requires broad investigation
- the task spans many interacting systems
- the task is long-running and requires ongoing judgment

After delegating, verify the Sonnet worker's result rather than blindly accepting it.

Prefer the cheapest capable model, but optimize for successful completion rather than token cost.

## Mission

Build ReqTrace, a guardrailed AI pipeline that ingests a medical-device Software Requirements Specification (SRS), finds gaps and contradictions, builds a requirements-to-test trace matrix, and drafts a verification protocol for engineer review. It must be production-shaped: deterministic checks, cited AI findings, evals with known answers, and CI on every commit.

The device is 100% fictional: the Novapump NP-200, a wearable insulin pump. Everything in this repo is synthetic. Nothing may reference, resemble, or be derived from any real company's product, requirement text, or internal document. If a name or behavior would look like a real device, change it.

Hard rule: this prompt file is committed to the repo as docs/ORCHESTRATOR_PROMPT.md and every planning decision goes in docs/DECISIONS.md. The repo must tell the whole story from prompt to result; a reader should understand what was built and why without talking to the author.

## Working style

- Start by writing docs/PLAN.md: architecture, module boundaries, data contracts, and the delegation plan (which tasks go to Sonnet and the acceptance criteria for each). Commit it before writing code.
- Make small commits with clear messages. Each phase below is at least one commit.
- After each Sonnet delegation, run the tests and the eval yourself before accepting.
- Never fabricate results. If the eval scores below target, say so in docs/DECISIONS.md and fix it or document the limitation.
- No API key in the repo. Read ANTHROPIC_API_KEY from the environment; .env is gitignored. Provide a --mock mode that runs the full pipeline with recorded fixture responses so CI and reviewers can run it without a key.

## Phase 1 — Synthetic inputs (Opus writes these; they define the ground truth)

**data/novapump_srs.md** — 25 requirements, IDs NP-REQ-001 … NP-REQ-025, grouped by feature. Each has: ID, title, text ("The pump shall…"), applicable modes/profiles, and a traced-from parent ID (NP-SYS-xxx) where it makes sense.

Device concept (fictional):

- Delivery modes: Basal, Bolus, Extended Bolus, Suspend.
- User profiles: Adult, Pediatric. Pediatric profile hides Extended Bolus and forces a lower max bolus.
- Child Lock: when ON, the Bolus button is disabled and the screen shows a lock icon.
- Buttons: Bolus, Suspend/Resume, Menu, Back. Each assignable at the profile level.
- Alarms: Occlusion, Low Reservoir, Low Battery, with tone and on-screen message.
- Logging: every delivery event logged with timestamp, mode, units.

Planted defects (exactly 5, recorded in data/ground_truth.json with ID, type, and the REQ IDs involved):

1. Contradiction: two requirements disagree on the max bolus for the Pediatric profile (e.g., one says 10 U, one says 15 U).
2. Missing requirement: the Child Lock behavior says the Bolus button is disabled, but no requirement states what happens when the user presses it anyway (no tone? message?). The behavior exists in the UI section but has no requirement.
3. Incomplete enumeration: the mode list in the Settings section omits Extended Bolus, while the Delivery section includes it.
4. Untestable requirement: one requirement uses "shall respond quickly" with no measurable value.
5. Orphan trace: one requirement traces to a parent NP-SYS- ID that does not exist in data/novapump_system_reqs.md.

**data/novapump_system_reqs.md** — About 8 system-level parent requirements (NP-SYS-001…). Deliberately omit the parent referenced by defect 5.

**data/legacy_protocol_v1.csv** — An outdated test protocol from "Novapump NP-100" (previous generation). Columns: step, description, action, expected_result, traces_to. Some steps reference modes or button names that no longer exist in NP-200, so the pipeline must show it reused what still applies and flagged what doesn't, rather than copy-pasting.

## Phase 2 — Pipeline (src/reqtrace/)

Python 3.11+, pydantic, anthropic, click, pytest. Keep it to a handful of modules:

- **parse.py** — Claude converts the SRS markdown into a list of Requirement Pydantic models (id, title, text, feature, modes, profiles, traces_to, measurable: bool). Schema validation rejects anything malformed; retry once with the validation error in the prompt, then fail loudly.
- **checks.py** — deterministic, no AI: every requirement has ≥1 test; every test traces to an existing requirement; every mode/profile value named anywhere appears in the canonical enum; every traces_to parent exists. Emits Finding objects with source="deterministic".
- **analyze.py** — Claude reviews the structured requirements for contradictions, gaps, and untestable language. Guardrail: every finding must cite ≥1 requirement ID that exists in the parsed set; findings that cite unknown IDs are dropped and counted in a rejected_findings metric. Emits Finding objects with source="llm", severity, cited_ids, rationale.
- **trace.py** — builds the trace matrix (requirement ↔ test step) from the legacy protocol plus newly drafted steps. Writes out/trace_matrix.csv.
- **draft.py** — generates out/draft_protocol.md: a table with Step | Action | Expected Result | Traces To, one block per feature, header stamped "DRAFT — requires engineer review. Not for execution." Reuses legacy steps that still trace cleanly; marks reused vs. new vs. retired-from-legacy.
- **report.py** — writes out/findings.md (grouped by severity, each with cited IDs and rationale) and out/summary.json.
- **cli.py** — `reqtrace run --srs data/novapump_srs.md --sys data/novapump_system_reqs.md --legacy data/legacy_protocol_v1.csv --out out/ [--mock]`.

Every Claude call: system prompt pinned in src/reqtrace/prompts/, temperature 0, response parsed as JSON into Pydantic, max 2 attempts, all calls logged to out/llm_log.jsonl (model, tokens, latency, validation pass/fail). Budget cap: abort the run if total tokens exceed a configurable limit.

## Phase 3 — Evals (evals/)

evals/run_eval.py compares out/findings.md + summary.json to data/ground_truth.json.

Metrics: planted defects caught (recall), false positives (findings not in ground truth), rejected hallucinated citations, deterministic-vs-LLM split, tokens and wall time.

Target: 5/5 planted defects caught, 0 false positives across 3 consecutive runs. If not met, iterate on prompts/checks and record each iteration's score in evals/history.md. Do not edit the ground truth to make the score pass.

Output evals/latest_report.md with a short table that a non-engineer can read.

## Phase 4 — Tests and CI

tests/ with pytest: schema validation, every deterministic check (positive and negative case), the citation guardrail (a finding citing NP-REQ-999 must be rejected), trace matrix completeness, and a full --mock pipeline run.

.github/workflows/ci.yml: on every push and PR, run ruff, pytest, and `reqtrace run --mock` followed by `evals/run_eval.py --mock`. Fail the build if recall < 5/5 or false positives > 0. Keep the whole job under 2 minutes. Add the CI badge to the README.

Makefile or justfile: `make demo` runs the whole thing and prints the eval table.

## Phase 5 — The README tells the story without the author in the room

README.md, in this order, short:

1. One-paragraph problem statement: in regulated device development, engineers hand-cross-reference redlined SRS documents against legacy protocols and trace matrices; it is slow and gaps slip through to physical testing.
2. A 60–90 second GIF (docs/demo.gif, recorded with vhs or asciinema+agg) showing `make demo` end to end: run, findings, trace matrix, draft protocol, eval table.
3. The eval table (copied from evals/latest_report.md).
4. Architecture diagram (Mermaid) showing where deterministic checks, LLM analysis, guardrails, evals, and human review sit.
5. "Guardrails" section: schema validation, citation-or-reject, token budget, temperature 0, full LLM log, human-review stamp, CI gate.
6. "What this would look like inside an enterprise" section: swap the Anthropic client for the organization's approved model endpoint; add SSO, audit logging, and a requirements-tool connector; keep the engineer as the approver. Three to five bullets, no vendor names beyond "approved enterprise endpoint."
7. "Everything here is synthetic" disclaimer: the Novapump NP-200 does not exist; no real product data was used.
8. Links to docs/ORCHESTRATOR_PROMPT.md, docs/PLAN.md, docs/DECISIONS.md.

## Definition of done

- `make demo` runs clean on a fresh clone with an API key, and `make demo MOCK=1` runs clean without one.
- CI green with badge.
- evals/latest_report.md shows 5/5 recall, 0 false positives, and the number of rejected hallucinated citations.
- README has the GIF, the table, and the diagram.
- docs/DECISIONS.md lists every architectural choice and every eval iteration honestly.
- Zero references to any real device, company, or requirement text. Run a final grep for anything that looks like a real product name before finishing.

## Build checklist (from the author)

Setup: new empty folder, git init, public GitHub repo named `reqtrace`; API key only in the shell, never in the repo.

While it builds, check: PLAN.md committed before any code; the 5 defects in ground_truth.json match the prompt; nothing in data/ sounds like anything touched at work; eval history is honest (4 tries to hit 5/5 is fine and shows iteration).

Finish: `make demo` works on a fresh clone and with MOCK=1 and no key; CI badge green; GIF plays in the README; final grep for real product names.
