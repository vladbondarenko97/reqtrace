# ReqTrace eval report

Run: live (claude-code, sonnet) · result: **PASS**

| What we measured | Result |
|---|---|
| Planted defects caught | **5 / 5** |
| False positives (findings not in the answer key) | **0** |
| Hallucinated citations rejected by the guardrail | 0 |
| Findings from deterministic checks / from the LLM | 2 / 3 |
| Obsolete legacy test steps correctly retired | 8 / 8 |
| Requirements with at least one test step | 25 / 25 |
| Tokens (in / out) | 23,702 / 9,332 |
| Model time | 51.9 s |

| Planted defect | Type | Requirements | Caught by |
|---|---|---|---|
| D1 | contradiction | NP-REQ-009, NP-REQ-011 | F-002 (llm) |
| D2 | missing_requirement | NP-REQ-014 | F-004 (llm) |
| D3 | incomplete_enumeration | NP-REQ-001, NP-REQ-024 | F-005 (llm) |
| D4 | untestable | NP-REQ-018 | F-003 (deterministic) |
| D5 | orphan_trace | NP-REQ-025 | F-001 (deterministic) |
