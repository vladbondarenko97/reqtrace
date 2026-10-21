# Draft Verification Protocol — Novapump NP-200 (synthetic)

> **DRAFT — requires engineer review. Not for execution.**

Origin tags: **NEW** = drafted for NP-200; **REUSED (L-nn)** = legacy step carried over verbatim, still traces cleanly; **RETIRED** steps are listed at the end with the reason.


## Delivery

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-001 · NEW | Open the delivery mode selection and list the available delivery modes. | Exactly four delivery modes are available: Basal, Bolus, Extended Bolus, and Suspend. | NP-REQ-001 |
| TC-002 · REUSED (L-01) | Open Basal settings and enter a rate of 1.00 U/h | Pump accepts and displays 1.00 U/h | NP-REQ-002 |
| TC-003 · REUSED (L-02) | Enter a basal rate of 5.00 U/h then try 5.05 U/h | 5.00 U/h accepted; 5.05 U/h rejected | NP-REQ-002 |
| TC-004 · REUSED (L-03) | Run programmed basal for 24 hours and measure delivered volume | Delivered volume within ±5% of programmed | NP-REQ-003 |
| TC-005 · REUSED (L-05) | Select Bolus and confirm 2.00 U | Delivery starts within 2 seconds and 2.00 U is delivered | NP-REQ-004 |
| TC-006 · NEW | With the Adult profile active, request a 25.05 U bolus. | The pump rejects the bolus request (above 25 U) and displays the message "Bolus exceeds limit". | NP-REQ-005 |
| TC-007 · NEW | With the Adult profile active, select Extended Bolus and program a delivery over 30 minutes, then over 8 hours. | The pump delivers the extended bolus evenly over the selected duration, for durations from 30 minutes to 8 hours. | NP-REQ-006 |
| TC-008 · REUSED (L-10) | Issue a suspend command during basal delivery | All delivery stops within 2 seconds | NP-REQ-007 |
| TC-009 · REUSED (L-11) | Resume after suspend and confirm the prompt | Basal delivery restarts at the programmed rate | NP-REQ-008 |

## Profiles

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-010 · NEW | With the Pediatric profile active, attempt to program a single bolus larger than 10 U. | The pump limits a single bolus to a maximum of 10 U. NOTE for engineer: NP-REQ-009 (10 U maximum) conflicts with NP-REQ-011 (reject above 15 U); resolve the intended pediatric limit before execution. | NP-REQ-009 |
| TC-011 · NEW | With the Pediatric profile active, browse every menu and look for the Extended Bolus option. | The Extended Bolus option is not displayed in any menu. | NP-REQ-010 |
| TC-012 · NEW | With the Pediatric profile active, request a bolus above 15 U (e.g. 15.05 U). | The pump rejects the bolus request and displays the message "Bolus exceeds limit". NOTE for engineer: conflicts with NP-REQ-009 (10 U maximum); confirm the intended limit. | NP-REQ-011 |
| TC-013 · NEW | Attempt to change the active profile by entering an invalid 4-digit PIN, then repeat with a valid 4-digit PIN. | With the invalid PIN the pump rejects it, keeps the current profile active and displays "Invalid PIN". With the valid PIN the profile is changed. | NP-REQ-012 |

## Child Lock and UI

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-014 · NEW | Hold the Menu button for 3 seconds with Child Lock OFF, then hold it again for 3 seconds. | The first hold toggles Child Lock ON; the second hold toggles Child Lock OFF. | NP-REQ-013 |
| TC-015 · NEW | Turn Child Lock ON, then press the Bolus, Suspend/Resume, Menu, and Back buttons in turn. | The Bolus button is disabled; the Suspend/Resume, Menu, and Back buttons remain operable. | NP-REQ-014 |
| TC-016 · NEW | Turn Child Lock ON and view the home screen. | A lock icon is displayed on the home screen. | NP-REQ-015 |

## Buttons

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-017 · NEW | Inspect the pump for physical buttons. | The pump has exactly four physical buttons: Bolus, Suspend/Resume, Menu, and Back. | NP-REQ-016 |
| TC-018 · NEW | Set a different button function assignment for the Adult and Pediatric profiles, then switch between the profiles using a valid PIN. | Each profile keeps its own stored button function assignment, and the assignment is applied when that profile becomes active. | NP-REQ-017 |
| TC-019 · NEW | Press the Bolus button and observe the pump response. | TBD - requirement is not measurable: the engineer must define the maximum response time (and measurement method) for the pump to respond to a Bolus button press in place of "quickly". | NP-REQ-018 |

## Alarms

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-020 · REUSED (L-14) | Block the infusion line during basal delivery | Delivery stops; alarm tone sounds; message Occlusion detected is shown | NP-REQ-019 |
| TC-021 · REUSED (L-15) | Reduce reservoir volume to 20 U | Alarm tone sounds; message Low reservoir is shown | NP-REQ-020 |
| TC-022 · NEW | Discharge the battery to 20%. | The pump sounds an alarm tone and displays the message "Low battery". | NP-REQ-021 |
| TC-023 · NEW | Trigger an alarm (e.g. low reservoir), then press the Back button while the alarm is active. | The alarm tone is silenced and the alarm message remains displayed until the alarm condition is cleared. | NP-REQ-022 |

## Logging

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-024 · REUSED (L-18) | Deliver a basal then a bolus and open the event log | Both events listed with timestamp mode and units | NP-REQ-023 |

## Settings

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-025 · NEW | Open the Settings menu and view the delivery modes whose default parameters can be configured. | The Settings menu allows default parameters to be configured for Basal, Bolus, and Suspend. | NP-REQ-024 |
| TC-026 · NEW | Open the Settings menu and set the date and time, changing the time by 1 minute. | The pump allows the date and time to be set from the Settings menu with a resolution of 1 minute. | NP-REQ-025 |

## Retired from legacy protocol (NP-100)

| Legacy Step | Action | Why it was not reused |
|---|---|---|
| L-04 | Select Temp Basal mode and set 150% for 1 hour | Temp Basal mode no longer exists; current modes are Basal, Bolus, Extended Bolus, Suspend. |
| L-06 | Request a 21 U bolus | 20 U maximum bolus changed: Adult limit is now 25 U and Pediatric limit is 15 U (10 U in NP-REQ-009). |
| L-07 | Press Up Down and OK to reach the Settings menu | Up/Down/OK arrow keys no longer exist; buttons are Bolus, Suspend/Resume, Menu, Back. |
| L-08 | Press the Quick Bolus button once | Quick Bolus button no longer exists. |
| L-09 | Hold the Power button for 3 seconds | Power button no longer exists; only four buttons (Bolus, Suspend/Resume, Menu, Back). |
| L-12 | Select Priming mode and run a prime cycle | Priming mode and 0.5 U prime no longer exist in the current requirements. |
| L-13 | Select Square Wave and set 4 U over 2 hours | Square Wave bolus replaced by Extended Bolus (30 minutes to 8 hours, Adult only); 4 U over 2 hours is not stated in the requirements. |
| L-16 | Discharge battery to 25% | Low battery threshold changed from 25% to 20% or less. |
| L-17 | Press the OK button during an active alarm | OK button no longer exists; alarm is silenced with the Back button. |
| L-19 | Open Settings and set the date | Now covers date and time with 1-minute resolution; legacy step covers only the date, and the home-screen display is not in the current requirements. |
