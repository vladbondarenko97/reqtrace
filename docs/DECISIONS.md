# Decisions

Every architectural choice and every eval iteration, including the ones that went badly. Newest information wins; nothing here was rewritten after the fact except typo fixes.

## Architecture

**D-01 — Default backend is the Claude Code CLI, not the Anthropic API.**
The author has no API key and asked for the same approach as their `take-the-wheel` project, which shells out to `claude -p`. `llm.py` does the same: one subprocess per call, run from an empty temp directory with `--tools ""`, `--strict-mcp-config`, `--disable-slash-commands`, `--no-session-persistence`, `--output-format json`, so the model sees only our pinned system prompt and our input. The Anthropic SDK backend exists behind `--backend anthropic` (needs `ANTHROPIC_API_KEY`). The brief said "read ANTHROPIC_API_KEY from the environment"; that still holds for that backend, it is just not the default.

**D-02 — Three backends behind one `LLM.ask()`.** `claude-code`, `anthropic`, `mock`. Everything that must hold for every call (pinned prompt, JSON → Pydantic, max 2 attempts with the validation error fed back, token budget, `llm_log.jsonl`) lives in one place, so a backend swap cannot skip a guardrail.

**D-03 — "Temperature 0" is not achievable as specified. Deviation.**
Current Claude models reject sampling parameters (`temperature` returns a 400), and the Claude Code CLI has no temperature flag. So: the `claude-code` backend cannot set it; the `anthropic` backend sends `temperature=0` only to Haiku 4.5, the one current model that accepts it. Reproducibility therefore comes from (a) recorded fixtures for CI and (b) repeated live runs in the eval (below), not from sampling settings. The README says this too.

**D-04 — Mock mode replays recordings of real runs.** Fixtures in `src/reqtrace/fixtures/` were written by `reqtrace run --record` from live `claude-code` runs, not hand-written. Each stores a SHA-256 of system prompt + input; if either changes, mock mode fails with "fixture is stale" instead of silently replaying an old answer. (This hash originally covered only the input; iteration 5 added the system prompt after I noticed a prompt edit could go undetected.) Token and latency numbers shown for mock runs are the recorded ones and are labelled as such.

**D-05 — `anthropic` is an optional extra, and that backend is untested.** The brief lists `anthropic` as a dependency; it is imported lazily and installed with `pip install -e '.[anthropic]'` so CI and `--mock` users do not need it. No API key was available, so `_anthropic()` has never been run against the real API. It is ~8 lines and follows the SDK's documented `messages.create` shape, but treat it as unverified.

**D-06 — What is deterministic and what is not.**
Deterministic (`checks.py`): parent exists (D5), mode/profile values in the canonical enum, requirement flagged not-measurable, every requirement has ≥1 test, every test traces to a real requirement. The enum check covers the structured `modes`/`profiles` fields only (steps carry no such fields), which is how I read "named anywhere". Contradictions, missing requirements and incomplete enumerations need language understanding and go to the LLM with the citation guardrail.

**D-07 — D4 (untestable) is reported as *deterministic*.** The rule is deterministic, but its input, the `measurable` flag, is set by the LLM during parsing. When the LLM analysis also flags the same requirement, `report.merge` keeps the deterministic copy and counts the other as deduplicated. The "deterministic vs LLM" split in the eval table is therefore about which component *emits* a finding, not about whether AI was upstream.

**D-08 — Reused legacy steps are copied verbatim.** The model decides *which* legacy steps still apply and what they trace to; `trace.py` then overwrites the step text from the legacy CSV, so "reuse" can never be a quiet paraphrase. Legacy steps the model neither reuses nor retires are retired by default with an "engineer must decide" reason.

**D-09 — Citation guardrail drops, counts, never repairs.** A finding citing any ID not in the parsed set is dropped and counted in `rejected_findings`. In every live run so far the count was 0: the model never hallucinated an ID on this 25-requirement input. The guardrail is covered by a unit test (a finding citing NP-REQ-999 is rejected), not by observed behavior. The eval table reports the real number, 0, rather than a staged one.

**D-10 — The model-facing taxonomy is closed.** The LLM may emit only `contradiction`, `missing_requirement`, `incomplete_enumeration`, `untestable` (enforced by Pydantic `Literal`); deterministic checks emit the rest. This makes eval matching a plain comparison.

**D-11 — Eval matching rule.** A finding catches a planted defect if `type` is equal and `cited_ids` overlaps the defect's `req_ids`. Extra findings that also match a defect are not false positives; anything else is. Ground truth was committed with the data, before any pipeline code, and has one commit in history. It was never edited.

**D-12 — Secondary eval metric: obsolete legacy steps retired (8/8).** `ground_truth.json` also lists the 8 legacy steps that mention NP-100-only modes, buttons or values. Informational, not part of the 5/5 gate, but it is how the "reused vs. flagged" requirement is checked rather than eyeballed.

**D-13 — Delegation.** The brief assumes an Opus orchestrator; this session ran on Sonnet 5.5, so orchestrator and workers were the same model family. The split was still applied: data, architecture, prompts and eval design stayed with the orchestrator (judgment, defines ground truth); the pytest suite was delegated to one Sonnet subagent with written acceptance criteria. Verification: I re-ran `pytest` and ruff myself (23 passed, clean) and re-ran the full mock pipeline and eval. The subagent also reported two things it did not change, both accurate: the token budget is checked before each attempt, so one call can overshoot the cap (it aborts on the next call); and mock mode cannot exercise the retry path with a recorded response, because a retry prompt no longer matches the fixture hash (retry is unit-tested with a patched `_call` instead). Tests were not otherwise edited.

**D-14 — Tooling.** ruff rules `E,F,I,UP` minus line length/ambiguous names (prose-heavy f-strings). The GIF was recorded with `asciinema` + `agg`, installed with Homebrew for this task (`brew install asciinema agg`); `make demo PAUSE=5` adds clear-and-wait between stages so the recording is readable. `docs/demo.cast` is the source recording of a real live run.

**D-15 — `out/` is gitignored; `docs/sample_output/` holds one real live run** (findings, matrix, protocol, summary, LLM log) so a reader can browse results without running anything.

## Eval iterations

Times are UTC from `evals/history.md`, which is appended by the eval script itself. Every live run is listed there, passing or not.

| # | Change | Result | Why |
|---|---|---|---|
| 1 | First live run, prompts as first written | **4/5**, 0 FP | `missing_requirement` rule was too cautious ("only when directly implied; do not speculate") and never fired. D2 missed. My prompt's fault. |
| 2 | Rewrote the rule as: *a requirement blocks/disables/rejects an action and no requirement specifies the response to attempting it* (generic; does not mention Child Lock) | **5/5**, 0 FP | |
| – | Two more runs, nothing changed | 5/5 with **2 FP**, then 5/5 with **1 FP** | Not a model hallucination: the rewritten rule worked and found a real hole in *my* SRS (see below). |
| 3 | **Input fix, not a prompt fix.** NP-REQ-005 (Adult max 25 U) limited bolus size but never said what happens above it, an accidental sixth defect. I gave it a stated response, parallel to NP-REQ-011. Ground truth untouched. | 5/5, 0 FP; then stability runs: 0 FP, 0 FP, **1 FP** | The third stability run flagged NP-REQ-012: invalid PIN response unspecified. Same class, another accidental gap. |
| 4 | **Input fix.** NP-REQ-012 gained an invalid-PIN response; NP-REQ-008 reworded to say the pump stays suspended until resume is confirmed. | 5/5, 0 FP, then 3/3 stability runs 5/5 with 0 FP | |
| 5 | Fixture hash now includes the system prompt (D-04); fixtures re-recorded from a live run. No prompt or data change. | 5/5, 0 FP, then 2/2 stability runs 5/5, 0 FP | |

Reading this honestly:
- The brief says "iterate on prompts/checks." Iteration 2 is that. Iterations 3 and 4 changed **my synthetic input**, because the brief also says the SRS contains *exactly* 5 planted defects, and the reviewer correctly found extra real ones I had written by accident. Changing the input to remove unplanted defects is not the same as editing the answer key, but it is a judgment call and a reader should know it was made. The planted defects themselves and `ground_truth.json` are unchanged.
- After iteration 4 the history shows 7 consecutive passing live runs (5/5, 0 FP: iteration 4, three stability runs, iteration 5, two stability runs), plus the live run recorded in the GIF (also a pass, not in the history file because it was started by `make demo`). Before iteration 4, 3 of the 6 live runs after iteration 2 failed the 0-FP target. So the 3-consecutive target is met **on the final prompts and data**, not on the first ones.
- Live-model variance is real: even after iteration 3, one of three identical runs added a spurious-looking finding. A reviewer that sometimes flags extra real-looking gaps is why the CI gate runs on recorded fixtures (deterministic) and the live stability runs are recorded separately here.

## Known limitations

- CI proves the pipeline, guardrails and scoring logic are intact on recorded responses. It does **not** prove the live model still passes; that needs `make demo` with a model, and the history above is the evidence for it.
- 25 requirements and 5 defects is a demo, not a benchmark. 100% recall here says little about recall on real documents.
- The `anthropic` backend is untested (D-05). Temperature 0 is not enforced (D-03).
- The citation guardrail has never fired on live output (D-09).
- One model family (Sonnet via Claude Code) was evaluated.
