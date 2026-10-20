# Findings — Novapump NP-200 SRS (synthetic)

> **DRAFT — requires engineer review. Not for execution.** Findings are suggestions for the reviewing engineer.


## High (2)

### F-001 · orphan_trace · deterministic
- **Cited:** NP-REQ-025
- **Rationale:** NP-REQ-025 traces to NP-SYS-007, which does not exist in the system requirements.

### F-002 · contradiction · llm
- **Cited:** NP-REQ-009, NP-REQ-011
- **Rationale:** NP-REQ-009 says "limit a single bolus to a maximum of 10 U" for the Pediatric profile, but NP-REQ-011 says to "reject any bolus request above 15 U" for the same profile, so the Pediatric maximum bolus has two different values.


## Medium (3)

### F-003 · untestable · deterministic
- **Cited:** NP-REQ-018
- **Rationale:** NP-REQ-018 is not measurable: "The pump shall respond quickly to a press of the Bolus button."

### F-004 · missing_requirement · llm
- **Cited:** NP-REQ-014
- **Rationale:** NP-REQ-014 says "the pump shall disable the Bolus button" when Child Lock is ON, but no requirement says how the pump responds (feedback, tone, message, or no response) when the user presses the disabled button.

### F-005 · incomplete_enumeration · llm
- **Cited:** NP-REQ-001, NP-REQ-024
- **Rationale:** NP-REQ-001 lists four delivery modes (Basal, Bolus, Extended Bolus, Suspend), while NP-REQ-024 lists only "Basal, Bolus, and Suspend" for both profiles. Extended Bolus is omitted with no stated reason.
