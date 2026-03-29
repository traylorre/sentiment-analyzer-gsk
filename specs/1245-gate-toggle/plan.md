# Implementation Plan: Gate Arm/Disarm Toggle

**Branch**: `1245-gate-toggle` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)

## Summary

Expose the existing `_check_gate()` and `_set_kill_switch()` functions via `GET /chaos/gate` and `PUT /chaos/gate` endpoints. Add a toggle switch in chaos.html that shows current state and allows arming/disarming with confirmation for the dangerous direction.

## Technical Context

**Language/Version**: Python 3.13, JavaScript (Alpine.js)
**Primary Dependencies**: boto3 (SSM), orjson (existing)
**Storage**: SSM Parameter Store (existing `/chaos/{env}/kill-switch`)
**Target Platform**: AWS Lambda (existing dashboard Lambda)
**Constraints**: Must not allow arming when triggered; must not allow setting "triggered" via this endpoint
**Scale/Scope**: ~5 toggles/gameday

## Project Structure (in target repo: ../sentiment-analyzer-gsk/)

```text
src/lambdas/dashboard/
├── chaos.py       # MODIFY: Add get_gate_state() and set_gate_state() public wrappers
├── handler.py     # MODIFY: Add GET/PUT /chaos/gate routes (~50 lines)

src/dashboard/
├── chaos.html     # MODIFY: Add gate toggle component (~60 lines)

tests/unit/
├── test_chaos_gate_api.py  # NEW: Endpoint contract tests (~60 lines)
```

## Implementation (Single Phase)

### Step 1: Add public wrappers in chaos.py
- `get_gate_state() -> str`: Wraps `_check_gate()`, catches ChaosError for triggered state and returns "triggered" instead of raising (the endpoint needs to return the state, not block).
- `set_gate_state(state: str) -> str`: Validates state is "armed" or "disarmed" (not "triggered"). Checks current state — if triggered, raises `ChaosError("Gate is triggered, cannot arm")`. Calls `_set_kill_switch(state)`. Returns new state.

### Step 2: Add GET /chaos/gate endpoint
- Auth: `_get_chaos_user_id_from_event(event)` — 401 if None
- Call `get_gate_state()` — note: for GET, "triggered" is a valid return, not an error
- Return `{"state": "armed"|"disarmed"|"triggered"}`
- Handle SSM failure → 500

### Step 3: Add PUT /chaos/gate endpoint
- Auth: same pattern — 401 if None
- Parse body: `{"state": "armed"|"disarmed"}`
- Validate: reject "triggered" with 400
- Call `set_gate_state(state)` — catch ChaosError for triggered-state rejection → 409
- Return `{"state": "<new_state>", "previous": "<old_state>"}`

### Step 4: Add UI toggle in chaos.html
- Alpine.js state: `gateState: null`, `gateLoading: false`
- `fetchGateState()`: Called on init and after any toggle. `GET /chaos/gate`.
- Toggle component: DaisyUI toggle input. Checked = armed, unchecked = disarmed. Disabled when `gateState === 'triggered'` or `gateLoading`.
- On toggle to armed: `confirm("Arm chaos gate? Experiments will inject real faults.")` — abort if cancelled.
- On toggle to disarmed: No confirmation needed.
- `toggleGate(newState)`: `PUT /chaos/gate` with `{state: newState}`. On success, update `gateState`. On error, revert toggle and show toast.
- Triggered state: Show red badge "TRIGGERED" with disabled toggle.

### Step 5: Unit tests
- GET 200 returns current state for each of armed/disarmed/triggered
- GET 401 for unauthenticated
- PUT 200 arm (disarmed -> armed)
- PUT 200 disarm (armed -> disarmed)
- PUT 409 when trying to arm while triggered
- PUT 400 when body contains "triggered"
- PUT 401 for unauthenticated
