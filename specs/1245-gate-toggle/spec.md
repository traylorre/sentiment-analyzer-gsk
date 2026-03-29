# Feature Specification: Gate Arm/Disarm Toggle

**Feature Branch**: `1245-gate-toggle`
**Created**: 2026-03-27
**Status**: Draft
**Input**: "Feature 1245: Gate Arm/Disarm Toggle — expose `_check_gate()` and `_set_kill_switch(value)` via `/chaos/gate` GET/PUT endpoint + UI toggle in chaos.html"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - View and Toggle Gate State (Priority: P1)

The operator wants to see the current chaos gate state (armed/disarmed/triggered) in the dashboard and toggle between armed and disarmed with a single click. This replaces running `aws ssm put-parameter --name /chaos/{env}/kill-switch --value armed --overwrite` from the CLI.

**Why this priority**: Gate state is the primary safety control. Every gameday begins with arming and ends with disarming. Making this a UI toggle eliminates CLI friction.

**Independent Test**: Load chaos dashboard, verify gate toggle shows current state. Click to arm, verify SSM parameter updated. Click to disarm, verify SSM parameter updated.

**Acceptance Scenarios**:

1. **Given** the chaos dashboard is loaded, **When** the gate section renders, **Then** a toggle switch shows the current gate state fetched from `GET /chaos/gate` with a label: "Disarmed" (grey), "Armed" (amber), or "Triggered" (red).
2. **Given** the gate is disarmed, **When** the operator clicks the toggle, **Then** a confirmation dialog appears ("Arm chaos gate? Experiments will inject real faults."). On confirm, the gate state changes to "armed" and the toggle updates.
3. **Given** the gate is armed, **When** the operator clicks the toggle, **Then** the gate state changes to "disarmed" immediately (no confirmation needed for safe-direction toggle).
4. **Given** the gate is in "triggered" state (andon cord was pulled), **When** the operator views the toggle, **Then** the toggle is disabled with a label "TRIGGERED — resolve before re-arming" and a link to reset procedure.

---

### User Story 2 - Gate State Refresh (Priority: P2)

The operator wants the gate state to refresh automatically so that if another operator arms/disarms/triggers the gate, the dashboard reflects the change without manual page reload.

**Acceptance Scenarios**:

1. **Given** the gate state was last fetched 30+ seconds ago, **When** a new API call is made (any chaos endpoint), **Then** the gate state is re-fetched and the toggle updates.
2. **Given** the gate state changes from "armed" to "triggered" (by andon cord or kill switch), **When** the dashboard refreshes, **Then** the toggle immediately shows the triggered state.

---

### Edge Cases

- What happens when the operator tries to arm the gate in a prod environment?
  - The `PUT /chaos/gate` endpoint checks environment. Returns 403 "Chaos testing not allowed in prod". The UI should never reach this state because chaos.html is only served in dev environments, but the backend enforces it defensively.
- What happens when SSM is unreachable during a toggle?
  - Returns 500 with "Cannot set gate state (SSM unavailable)". The toggle reverts to its previous position. A toast shows the error.
- What happens when two operators toggle simultaneously?
  - Last-write-wins (SSM PutParameter is atomic). The next GET /chaos/gate fetch shows the actual state. No corruption risk.
- What happens when the operator rapidly clicks the toggle?
  - The toggle is disabled during the PUT request (optimistic UI disabled). Re-enables on response.
- What happens when trying to arm while gate is "triggered"?
  - The PUT endpoint rejects with 409: "Gate is triggered. Pull andon cord reset or manually set to disarmed first." The UI prevents this by disabling the toggle in triggered state.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST expose a `GET /chaos/gate` endpoint returning the current gate state (`armed`, `disarmed`, or `triggered`).
- **FR-002**: System MUST expose a `PUT /chaos/gate` endpoint accepting `{"state": "armed"|"disarmed"}` to toggle the gate.
- **FR-003**: System MUST NOT allow setting gate to `armed` when current state is `triggered` (return 409).
- **FR-004**: System MUST NOT allow setting gate to `triggered` via this endpoint (that is the andon cord's job).
- **FR-005**: System MUST enforce authentication using `_get_chaos_user_id_from_event()` pattern on both endpoints.
- **FR-006**: The UI MUST show a confirmation dialog before arming (dangerous direction) but not before disarming (safe direction).
- **FR-007**: The UI MUST disable the toggle when gate state is `triggered`.

### Key Entities

- **Gate State**: SSM parameter at `/chaos/{env}/kill-switch` with values: `disarmed` (default/safe), `armed` (experiments inject real faults), `triggered` (emergency stop active).

## Success Criteria _(mandatory)_

- **SC-001**: Gate toggle correctly reflects SSM parameter state on page load.
- **SC-002**: Arming sets SSM parameter to "armed" and disarming sets it to "disarmed".
- **SC-003**: Triggered state disables the toggle and shows warning message.

## Assumptions

- The existing `_check_gate()` and `_set_kill_switch()` functions in chaos.py are sufficient; no modifications needed beyond making them accessible.
- SSM parameter path is `/chaos/{env}/kill-switch` (confirmed in chaos.py line 1010).
- The confirmation dialog for arming is a browser `confirm()` call (adequate for this internal tool).

## Scope Boundaries

### In Scope
- `GET /chaos/gate` and `PUT /chaos/gate` endpoints in handler.py
- Gate toggle UI component in chaos.html
- Unit tests for both endpoints

### Out of Scope
- Audit log of gate state changes (future enhancement)
- Gate state notifications (Slack/email)
- Role-based access control for arming (all authenticated chaos users can arm)

## Dependencies

- **Feature 1237** (External Refactor): DONE — provides `_check_gate()` and `_set_kill_switch()`
- **Feature 1244** (Health Check): Independent
- **Feature 1246** (Andon Cord): The andon cord sets gate to "triggered". This feature must handle that state but does not depend on Feature 1246 being implemented first.
