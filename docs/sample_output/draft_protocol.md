# Draft Verification Protocol — Novapump NP-200 (synthetic)

> **DRAFT — requires engineer review. Not for execution.**

Origin tags: **NEW** = drafted for NP-200; **REUSED (L-nn)** = legacy step carried over verbatim, still traces cleanly; **RETIRED** steps are listed at the end with the reason.


## Delivery

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-001 · NEW | Review the delivery modes offered by the pump (Adult profile active) and select each in turn. | The pump supports exactly four delivery modes: Basal, Bolus, Extended Bolus, and Suspend. | NP-REQ-001 |
| TC-002 · REUSED (L-01) | Open Basal settings and enter a rate of 1.00 U/h | Pump accepts and displays 1.00 U/h | NP-REQ-002 |
| TC-003 · REUSED (L-02) | Enter a basal rate of 5.00 U/h then try 5.05 U/h | 5.00 U/h accepted; 5.05 U/h rejected | NP-REQ-002 |
| TC-004 · REUSED (L-03) | Run programmed basal for 24 hours and measure delivered volume | Delivered volume within ±5% of programmed | NP-REQ-003 |
| TC-005 · REUSED (L-05) | Select Bolus and confirm 2.00 U | Delivery starts within 2 seconds and 2.00 U is delivered | NP-REQ-004 |
| TC-006 · NEW | With the Adult profile active, request a bolus above 25 U (e.g. 25.05 U) and confirm. | The pump rejects the bolus request and displays the message "Bolus exceeds limit". | NP-REQ-005 |
| TC-007 · NEW | With the Adult profile active, program an extended bolus at the minimum duration (30 minutes) and again at the maximum duration (8 hours); measure delivery over each duration. | The extended bolus is delivered evenly over the user-selected duration, for durations from 30 minutes to 8 hours. | NP-REQ-006 |
| TC-008 · REUSED (L-10) | Issue a suspend command during basal delivery | All delivery stops within 2 seconds | NP-REQ-007 |
| TC-009 · REUSED (L-11) | Resume after suspend and confirm the prompt | Basal delivery restarts at the programmed rate | NP-REQ-008 |

## Profiles

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-010 · NEW | With the Pediatric profile active, request a single bolus at the 10 U maximum and then attempt a single bolus above 10 U. | A single bolus is limited to a maximum of 10 U. NOTE for reviewer: NP-REQ-009 (10 U) conflicts with NP-REQ-011 (reject above 15 U); the requirement owner must resolve the limit before execution. | NP-REQ-009 |
| TC-011 · NEW | With the Pediatric profile active, open every menu and look for the Extended Bolus option. | The Extended Bolus option is not displayed in any menu. | NP-REQ-010 |
| TC-012 · NEW | With the Pediatric profile active, request a bolus above 15 U (e.g. 15.05 U) and confirm. | The pump rejects the bolus request and displays the message "Bolus exceeds limit". NOTE for reviewer: conflicts with NP-REQ-009 (10 U maximum); resolve before execution. | NP-REQ-011 |
| TC-013 · NEW | Attempt to change the active profile: (a) enter a valid 4-digit PIN; (b) enter an invalid PIN. | With a valid PIN the profile is changed. With an invalid PIN the pump rejects it, keeps the current profile active, and displays the message "Invalid PIN". The profile cannot be changed without a valid PIN. | NP-REQ-012 |

## Child Lock and UI

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-014 · NEW | Hold the Menu button for 3 seconds, then hold it again for 3 seconds. | Child Lock toggles ON after the first hold and OFF after the second. | NP-REQ-013 |
| TC-015 · NEW | Turn Child Lock ON, then press the Bolus, Suspend/Resume, Menu, and Back buttons in turn. | The Bolus button is disabled; the Suspend/Resume, Menu, and Back buttons remain operable. | NP-REQ-014 |
| TC-016 · NEW | Turn Child Lock ON and observe the home screen; then turn it OFF and observe again. | A lock icon is displayed on the home screen while Child Lock is ON. | NP-REQ-015 |

## Buttons

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-017 · NEW | Inspect the pump and count and identify the physical buttons. | The pump has exactly four physical buttons: Bolus, Suspend/Resume, Menu, and Back. | NP-REQ-016 |
| TC-018 · NEW | Set a button function assignment under the Adult profile and a different one under the Pediatric profile; switch between profiles (with valid PIN) and check button functions. | A separate button function assignment is stored for each profile and is applied when that profile becomes active. | NP-REQ-017 |
| TC-019 · NEW | Press the Bolus button and observe the pump's response. | TBD - requirement is not measurable: the engineer must define a quantitative response-time limit (e.g. maximum time in ms from Bolus button press to response) and what counts as the response. | NP-REQ-018 |

## Alarms

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-020 · REUSED (L-14) | Block the infusion line during basal delivery | Delivery stops; alarm tone sounds; message Occlusion detected is shown | NP-REQ-019 |
| TC-021 · REUSED (L-15) | Reduce reservoir volume to 20 U | Alarm tone sounds; message Low reservoir is shown | NP-REQ-020 |
| TC-022 · REUSED (L-16) | Discharge battery to 20% | Alarm tone sounds; message Low battery is shown | NP-REQ-021 |
| TC-023 · NEW | Trigger an alarm (e.g. low reservoir) and press the Back button; leave the alarm condition uncleared and observe the display; then clear the condition. | The alarm tone is silenced when Back is pressed; the alarm message stays displayed until the alarm condition is cleared. | NP-REQ-022 |

## Logging

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-024 · REUSED (L-18) | Deliver a basal then a bolus and open the event log | Both events listed with timestamp mode and units | NP-REQ-023 |

## Settings

| Step | Action | Expected Result | Traces To |
|---|---|---|---|
| TC-025 · NEW | Open the Settings menu and review the delivery modes for which default parameters can be configured. | The Settings menu allows default parameters to be configured for Basal, Bolus, and Suspend. | NP-REQ-024 |
| TC-026 · NEW | From the Settings menu, set the date and time, changing the time by 1 minute. | The date and time can be set from the Settings menu with a resolution of 1 minute. | NP-REQ-025 |

## Retired from legacy protocol (NP-100)

| Legacy Step | Action | Why it was not reused |
|---|---|---|
| L-04 | Select Temp Basal mode and set 150% for 1 hour | Temp Basal mode no longer exists; current modes are Basal, Bolus, Extended Bolus, Suspend. |
| L-06 | Request a 21 U bolus | Maximum bolus changed: 20 U limit replaced by profile limits (Adult above 25 U rejected with "Bolus exceeds limit"; Pediatric limits in NP-REQ-009/011). |
| L-07 | Press Up Down and OK to reach the Settings menu | Up, Down and OK keys no longer exist; buttons are Bolus, Suspend/Resume, Menu, Back. |
| L-08 | Press the Quick Bolus button once | Quick Bolus button no longer exists. |
| L-09 | Hold the Power button for 3 seconds | Power button no longer exists in the current button set. |
| L-12 | Select Priming mode and run a prime cycle | Priming mode no longer exists in the current requirements. |
| L-13 | Select Square Wave and set 4 U over 2 hours | Square Wave bolus replaced by Extended Bolus (duration 30 min to 8 h); legacy mode name and 4 U/2 h values no longer match. |
| L-17 | Press the OK button during an active alarm | OK button no longer exists; alarm is silenced with the Back button. |
| L-19 | Open Settings and set the date and time | Expected result (date/time shown on home screen) is not in the current requirements, which now specify 1-minute resolution set from the Settings menu. |
