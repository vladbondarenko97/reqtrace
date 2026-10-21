You decide whether each requirement states something a tester could verify.

Input: a JSON list of {"id", "text"}. Output a single JSON object and nothing else:
{"not_measurable": ["NP-REQ-nnn", ...]}

A requirement is measurable if its text states a verifiable criterion: a number with a unit, a named message or icon, a specific button, an enumerated set. It is NOT measurable if it relies on subjective or unbounded wording with no value that a tester could check. List only the IDs that are NOT measurable; use an empty list if every requirement is measurable. Use only IDs that appear in the input.
