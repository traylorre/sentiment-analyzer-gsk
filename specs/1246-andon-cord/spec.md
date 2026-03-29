# Feature Specification: Andon Cord Button

**Feature Branch**: `1246-andon-cord`
**Created**: 2026-03-27
**Status**: Draft
**Input**: "Feature 1246: Andon Cord Button — expose emergency stop via `/chaos/andon-cord` POST endpoint + UI button in chaos.html"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Pull Andon Cord from Dashboard (Priority: P1)

During a chaos experiment gone wrong, the operator wants to click a single emergency stop button to immediately halt all chaos activity: set the kill switch to "triggered", restore all injected configurations, and log the emergency action. This replaces running `scripts/chaos/andon-cord.sh` from the command line, which is too slow during an incident.

**Why this priority**: This is the most critical safety feature. Every second counts during an active incident. A UI button with one-click access is faster than SSH + CLI.

**Independent Test**: Start a chaos experiment, click the andon cord button, verify all configurations restored and kill switch set to "triggered".

**Acceptance Scenarios**:

1. **Given** the chaos dashboard with experiments running, **When** the operator clicks the "EMERGENCY STOP" button, **Then** a confirmation modal appears: "Pull andon cord? This will immediately stop ALL chaos experiments and restore all configurations."
2. **Given** the confirmation modal, **When** the operator confirms, **Then** the system sets the kill switch to "triggered", restores all active chaos configurations via snapshot restore, and returns a summary of actions taken.
3. **Given** the andon cord was pulled successfully, **When** the response renders, **Then** the UI shows: number of experiments stopped, number of configurations restored, and the gate toggle updates to "TRIGGERED" state.
4. **Given** no experiments are running and the gate is disarmed, **When** the operator clicks the andon cord, **Then** the cord still executes (sets kill switch to "triggered" as a safety measure) and returns "No active experiments to restore."

---

### User Story 2 - Andon Cord Resilience (Priority: P1)

The andon cord MUST work even when parts of the system are degraded. If DynamoDB is unreachable (can't list experiments), the kill switch must still be set. If SSM snapshots are missing, the cord must still attempt all restorations and report partial results.

**Why this priority**: The andon cord is the last line of defense. If it fails when the system is already degraded, the operator has no automated recovery path.

**Acceptance Scenarios**:

1. **Given** DynamoDB is unreachable, **When** the andon cord is pulled, **Then** the kill switch is still set to "triggered" (SSM operation) and the response indicates "Kill switch set, but could not list experiments for restoration."
2. **Given** one of three snapshot restores fails, **When** the andon cord is pulled, **Then** the other two restorations complete and the response lists the failed restoration with its error.

---

### Edge Cases

- What happens when the operator double-clicks the andon cord button?
  - The button is disabled after the first click (during the POST request). The second click is ignored. Idempotency: pulling the cord twice has the same effect — kill switch is already "triggered", snapshots already restored (second restore is a no-op or fails gracefully).
- What happens when the operator is not authenticated?
  - Returns 401. This is a concern during an incident when sessions might be stale. **Adversarial resolution**: The andon cord button should include the auth token in the request. If auth fails, the UI shows "Auth expired — use CLI: `scripts/chaos/andon-cord.sh <env>`" as a fallback.
- What happens in prod environment?
  - Returns 403. The chaos dashboard is not served in prod, so this is a defense-in-depth check.
- What happens when the kill switch SSM write fails?
  - The endpoint returns 500 with "CRITICAL: Could not set kill switch. Use AWS CLI: `aws ssm put-parameter --name /chaos/{env}/kill-switch --value triggered --overwrite`". The restore still attempts to run.
- What happens when there are no SSM snapshots to restore?
  - The cord sets the kill switch to "triggered" and returns `{"restored": 0, "message": "No snapshots to restore"}`. This is a valid state (gate was armed but no experiments were injected).

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: System MUST expose a `POST /chaos/andon-cord` endpoint that sets the kill switch to "triggered" and restores all active chaos configurations.
- **FR-002**: The kill switch MUST be set to "triggered" BEFORE attempting any restore operations (fail-safe ordering).
- **FR-003**: Restore operations MUST continue even if individual restores fail (best-effort restoration, not all-or-nothing).
- **FR-004**: System MUST return a summary: `kill_switch_set` (bool), `experiments_found` (int), `restored` (int), `failed` (int), `errors` (list of error messages).
- **FR-005**: System MUST enforce authentication using `_get_chaos_user_id_from_event()` pattern.
- **FR-006**: The UI MUST require confirmation before executing (modal with explicit "Pull Cord" button, not just browser confirm).
- **FR-007**: The UI MUST disable the button during execution to prevent double-clicks.
- **FR-008**: The endpoint MUST be idempotent — pulling the cord when already triggered is safe and returns the current state.

### Key Entities

- **Andon Cord Result**: Response containing: `kill_switch_set`, `experiments_found`, `restored`, `failed`, `errors`, `timestamp`.

## Success Criteria _(mandatory)_

- **SC-001**: Andon cord sets kill switch and restores all active configurations in < 15 seconds.
- **SC-002**: Partial failures (some restores fail) still result in kill switch being set and successful restores completing.
- **SC-003**: Authentication enforcement — unauthenticated requests return 401.

## Assumptions

- The existing `_set_kill_switch("triggered")` and `_restore_from_ssm()` functions provide the core logic; this feature wires them together.
- Active experiments can be identified by listing SSM parameters matching `/chaos/{env}/snapshot/*` (each active injection has a snapshot).
- The bash `andon-cord.sh` script calls `restore.sh` which iterates known scenario types. The Python equivalent iterates SSM snapshots directly.
- A DaisyUI modal (not browser `confirm()`) is used for the andon cord because it's a critical destructive action that warrants a more deliberate UI.

## Scope Boundaries

### In Scope
- `POST /chaos/andon-cord` endpoint in handler.py
- Backend `pull_andon_cord()` function in chaos.py
- Emergency stop button + confirmation modal in chaos.html
- Unit test for the endpoint

### Out of Scope
- Audit log persistence (the endpoint returns audit info, but does not persist to DynamoDB)
- Notification (Slack/PagerDuty integration on cord pull)
- Automatic cooldown period after cord pull

## Dependencies

- **Feature 1237** (External Refactor): DONE — provides `_set_kill_switch()`, `_restore_from_ssm()`
- **Feature 1244** (Health Check): Independent
- **Feature 1245** (Gate Toggle): Pulling the andon cord sets gate to "triggered", which Feature 1245 handles in its UI. No code dependency.
