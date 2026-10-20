# Eval history

Appended by `evals/run_eval.py --note`; never edited by hand.

| When (UTC) | Run | Caught | FP | Rejected | Det/LLM | Legacy retired ok | Tokens in/out | Note |
|---|---|---|---|---|---|---|---|---|
| 2026-10-20 23:25 | live (claude-code, sonnet) | 4/5 | 0 | 0 | 2/2 | 8/8 | 23451/9402 | iteration 1: first live run, prompts as first written |
| 2026-10-20 23:26 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23522/9951 | iteration 2: missing_requirement rule rewritten as 'blocked action has no specified response to the attempt' |
| 2026-10-20 23:27 | live (claude-code, sonnet) | 5/5 | 2 | 0 | 2/5 | 8/8 | 23524/10126 | run 3 of 3-consecutive stability check (prompts unchanged since iteration 2) |
| 2026-10-20 23:28 | live (claude-code, sonnet) | 5/5 | 1 | 0 | 2/4 | 8/8 | 23523/10032 | run 4 of 3-consecutive stability check (prompts unchanged since iteration 2) |
| 2026-10-20 23:29 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23564/9501 | iteration 3 (input fix): SRS NP-REQ-005 gained a stated over-limit response; an unplanted real gap had caused FPs in runs 3-4 |
| 2026-10-20 23:30 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23564/9751 | stability run 1/3 after iteration 3 (nothing changed between runs) |
| 2026-10-20 23:31 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23564/9621 | stability run 2/3 after iteration 3 (nothing changed between runs) |
| 2026-10-20 23:32 | live (claude-code, sonnet) | 5/5 | 1 | 0 | 2/4 | 8/8 | 23564/10194 | stability run 3/3 after iteration 3 (nothing changed between runs) |
| 2026-10-20 23:33 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23701/9938 | iteration 4 (input fix): NP-REQ-012 gained invalid-PIN response, NP-REQ-008 clarified; run 3 of iteration 3 had flagged the PIN gap |
| 2026-10-20 23:34 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23702/10218 | stability run 1/3 after iteration 4 (nothing changed between runs) |
| 2026-10-20 23:35 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23702/9248 | stability run 2/3 after iteration 4 (nothing changed between runs) |
| 2026-10-20 23:36 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23701/9399 | stability run 3/3 after iteration 4 (nothing changed between runs) |
| 2026-10-20 23:37 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23700/9372 | iteration 5: fixture hash now covers system prompt; fixtures re-recorded (no prompt or data change) |
| 2026-10-20 23:38 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23700/9723 | stability run 1/2 after iteration 5 |
| 2026-10-20 23:39 | live (claude-code, sonnet) | 5/5 | 0 | 0 | 2/3 | 8/8 | 23700/9432 | stability run 2/2 after iteration 5 |
