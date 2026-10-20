# Novapump NP-200 Software Requirements Specification (SYNTHETIC)

> Fictional device. All content is synthetic and invented for a demo. Version 0.9 (draft for review).

Requirement format: each requirement has a heading with its ID and title, then its feature, applicable modes, applicable profiles, the parent system requirement it traces to, and its text. An empty Modes value means the requirement is not mode-specific.


## Delivery

### NP-REQ-001 — Delivery Modes
- **Feature:** Delivery
- **Modes:** Basal, Bolus, Extended Bolus, Suspend
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall support four delivery modes: Basal, Bolus, Extended Bolus, and Suspend.

### NP-REQ-002 — Basal Rate Programming
- **Feature:** Delivery
- **Modes:** Basal
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall allow a basal rate to be programmed from 0.05 U/h to 5.00 U/h in increments of 0.05 U/h.

### NP-REQ-003 — Basal Accuracy
- **Feature:** Delivery
- **Modes:** Basal
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall deliver a programmed basal rate to within ±5% of the programmed volume, measured over any 24-hour period.

### NP-REQ-004 — Bolus Delivery
- **Feature:** Delivery
- **Modes:** Bolus
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall deliver a user-selected bolus in increments of 0.05 U, beginning delivery within 2 seconds of the user confirming the bolus.

### NP-REQ-005 — Adult Maximum Bolus
- **Feature:** Delivery
- **Modes:** Bolus
- **Profiles:** Adult
- **Traces to:** NP-SYS-002
- **Text:** The pump shall reject any bolus request above 25 U when the Adult profile is active and shall display the message "Bolus exceeds limit".

### NP-REQ-006 — Extended Bolus Delivery
- **Feature:** Delivery
- **Modes:** Extended Bolus
- **Profiles:** Adult
- **Traces to:** NP-SYS-001
- **Text:** The pump shall deliver an extended bolus evenly over a user-selected duration from 30 minutes to 8 hours.

### NP-REQ-007 — Suspend Delivery
- **Feature:** Delivery
- **Modes:** Suspend
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall stop all insulin delivery within 2 seconds of the user issuing a suspend command.

### NP-REQ-008 — Resume Delivery
- **Feature:** Delivery
- **Modes:** Suspend, Basal
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-001
- **Text:** The pump shall remain suspended until the user confirms the resume prompt, and shall then resume basal delivery at the programmed rate.


## Profiles

### NP-REQ-009 — Pediatric Maximum Bolus
- **Feature:** Profiles
- **Modes:** Bolus
- **Profiles:** Pediatric
- **Traces to:** NP-SYS-002
- **Text:** The pump shall limit a single bolus to a maximum of 10 U when the Pediatric profile is active.

### NP-REQ-010 — Pediatric Extended Bolus Hidden
- **Feature:** Profiles
- **Modes:** Extended Bolus
- **Profiles:** Pediatric
- **Traces to:** NP-SYS-008
- **Text:** The pump shall not display the Extended Bolus option in any menu when the Pediatric profile is active.

### NP-REQ-011 — Pediatric Bolus Limit Enforcement
- **Feature:** Profiles
- **Modes:** Bolus
- **Profiles:** Pediatric
- **Traces to:** NP-SYS-002
- **Text:** The pump shall reject any bolus request above 15 U when the Pediatric profile is active and shall display the message "Bolus exceeds limit".

### NP-REQ-012 — Profile Switching
- **Feature:** Profiles
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-008
- **Text:** The pump shall allow the active profile to be changed only after the user enters a valid 4-digit PIN. The pump shall reject an invalid PIN, keep the current profile active, and display the message "Invalid PIN".


## Child Lock and UI

### NP-REQ-013 — Child Lock Activation
- **Feature:** Child Lock and UI
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-003
- **Text:** The pump shall toggle Child Lock ON or OFF when the user holds the Menu button for 3 seconds.

### NP-REQ-014 — Child Lock Bolus Disable
- **Feature:** Child Lock and UI
- **Modes:** Bolus
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-003
- **Text:** When Child Lock is ON, the pump shall disable the Bolus button. The Suspend/Resume, Menu, and Back buttons shall remain operable.

### NP-REQ-015 — Child Lock Indicator
- **Feature:** Child Lock and UI
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-003
- **Text:** When Child Lock is ON, the pump shall display a lock icon on the home screen.


## Buttons

### NP-REQ-016 — Button Set
- **Feature:** Buttons
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-006
- **Text:** The pump shall provide exactly four physical buttons: Bolus, Suspend/Resume, Menu, and Back.

### NP-REQ-017 — Button Assignment per Profile
- **Feature:** Buttons
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-006
- **Text:** The pump shall store a separate button function assignment for each user profile and apply it when that profile becomes active.

### NP-REQ-018 — Button Responsiveness
- **Feature:** Buttons
- **Modes:** Bolus
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-006
- **Text:** The pump shall respond quickly to a press of the Bolus button.


## Alarms

### NP-REQ-019 — Occlusion Alarm
- **Feature:** Alarms
- **Modes:** Basal, Bolus, Extended Bolus
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-004
- **Text:** When an occlusion is detected, the pump shall stop delivery, sound an alarm tone, and display the message "Occlusion detected".

### NP-REQ-020 — Low Reservoir Alarm
- **Feature:** Alarms
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-004
- **Text:** When the reservoir volume falls to 20 U or less, the pump shall sound an alarm tone and display the message "Low reservoir".

### NP-REQ-021 — Low Battery Alarm
- **Feature:** Alarms
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-004
- **Text:** When the battery charge falls to 20% or less, the pump shall sound an alarm tone and display the message "Low battery".

### NP-REQ-022 — Alarm Acknowledge
- **Feature:** Alarms
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-004
- **Text:** The pump shall silence an active alarm tone when the user presses the Back button, and shall keep the alarm message displayed until the alarm condition is cleared.


## Logging

### NP-REQ-023 — Delivery Event Log
- **Feature:** Logging
- **Modes:** Basal, Bolus, Extended Bolus, Suspend
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-005
- **Text:** The pump shall record every delivery event in the event log with its timestamp, delivery mode, and delivered units.


## Settings

### NP-REQ-024 — Settings Delivery Modes
- **Feature:** Settings
- **Modes:** Basal, Bolus, Suspend
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-006
- **Text:** The Settings menu shall allow the user to configure default parameters for the following delivery modes: Basal, Bolus, and Suspend.

### NP-REQ-025 — Date and Time Setting
- **Feature:** Settings
- **Modes:** —
- **Profiles:** Adult, Pediatric
- **Traces to:** NP-SYS-007
- **Text:** The pump shall allow the user to set the date and time, with a resolution of 1 minute, from the Settings menu.
