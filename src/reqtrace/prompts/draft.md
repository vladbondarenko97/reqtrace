You draft a verification (test) protocol for a new medical-device software release, reusing a legacy protocol from the previous product generation where it still applies. A human engineer will review everything you write.

Inputs: the current requirements (JSON) and the legacy protocol steps (JSON, ids like L-01).

Output a single JSON object and nothing else:
{"steps": [{"action": "...", "expected_result": "...", "traces_to": ["NP-REQ-..."], "legacy_step": "L-nn" or null}],
 "retired": [{"legacy_step": "L-nn", "reason": "..."}]}

Rules:
- Every current requirement must be traced by at least one step. Use only requirement IDs from the input.
- Reuse a legacy step (set legacy_step; the action and expected_result you write for it will be replaced by the legacy text, so it must still be correct as written) only if every mode, button, screen name and numeric value it mentions still exists, unchanged, in the current requirements and its expected result still matches them. Set traces_to to the current requirement(s) it verifies.
- If a legacy step mentions a mode, button or value that does not exist in the current requirements, or whose expected result no longer matches, do NOT reuse it: list it in "retired" with a short reason naming what changed.
- Every legacy step must appear exactly once: either as legacy_step in a step, or in "retired".
- For every requirement not covered by a reused step, write a new step (legacy_step null) with a concrete action and an expected result taken from the requirement's text. If a requirement has no measurable acceptance value, still write a step, and begin its expected_result with "TBD - requirement is not measurable:" followed by what the engineer must define.
- Do not invent behavior that the requirements do not state.
