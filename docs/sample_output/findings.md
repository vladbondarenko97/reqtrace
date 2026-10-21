# Findings — Novapump NP-200 SRS (synthetic)

> **DRAFT — requires engineer review. Not for execution.** Findings are suggestions for the reviewing engineer.


## High (4)

### F-001 · orphan_trace · deterministic
- **Cited:** NP-REQ-025
- **Rationale:** NP-REQ-025 traces to NP-SYS-007, which does not exist in the system requirements.

### F-002 · baseline_drift · deterministic
- **Cited:** L-16
- **Rationale:** L-16 (legacy) was changed after sign-off: "20%" -> "25%". Check that this went through change control.

### F-003 · baseline_drift · deterministic
- **Cited:** L-19
- **Rationale:** L-19 (legacy) was changed after sign-off: "and time" -> "(nothing)"; "and time" -> "(nothing)". Check that this went through change control.

### F-004 · contradiction · llm
- **Cited:** NP-REQ-009, NP-REQ-011
- **Rationale:** NP-REQ-009 limits a Pediatric bolus to "a maximum of 10 U", but NP-REQ-011 rejects only boluses "above 15 U" for the Pediatric profile, so the limit is 10 U in one place and 15 U in the other.


## Medium (3)

### F-005 · untestable · deterministic
- **Cited:** NP-REQ-018
- **Rationale:** NP-REQ-018 is not measurable: "The pump shall respond quickly to a press of the Bolus button."

### F-006 · missing_requirement · llm
- **Cited:** NP-REQ-014
- **Rationale:** NP-REQ-014 states "the pump shall disable the Bolus button" when Child Lock is ON, but no requirement says how the pump responds (feedback, message, tone, or explicit no response) when the user presses the disabled button.

### F-007 · incomplete_enumeration · llm
- **Cited:** NP-REQ-001, NP-REQ-024
- **Rationale:** NP-REQ-001 lists four delivery modes including Extended Bolus, while NP-REQ-024 lists the delivery modes as "Basal, Bolus, and Suspend" for both Adult and Pediatric profiles. No requirement explains why Extended Bolus is omitted.
