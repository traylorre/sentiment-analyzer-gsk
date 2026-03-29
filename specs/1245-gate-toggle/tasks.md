# Tasks: Gate Arm/Disarm Toggle

**Feature**: 1245-gate-toggle
**Generated**: 2026-03-27
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Implementation

### [ ] T-001: Add get_gate_state() and set_gate_state() in chaos.py
**File**: `src/lambdas/dashboard/chaos.py`
**Depends on**: None
**Requirements**: FR-001, FR-002, FR-003, FR-004
**Description**: Add two public wrapper functions:

```python
def get_gate_state() -> str:
    """Return current gate state: 'armed', 'disarmed', or 'triggered'."""
    # Unlike _check_gate() which raises on 'triggered', this returns it
    ssm = _get_ssm_client()
    try:
        param = ssm.get_parameter(Name=f"/chaos/{ENVIRONMENT}/kill-switch")
        return param["Parameter"]["Value"]  # armed, disarmed, or triggered
    except ssm.exceptions.ParameterNotFound:
        return "disarmed"
    except Exception as e:
        raise ChaosError(f"Cannot read gate state: {e}") from e

def set_gate_state(new_state: str) -> dict[str, str]:
    """Set gate to 'armed' or 'disarmed'. Returns {state, previous}."""
    if new_state not in ("armed", "disarmed"):
        raise ValueError(f"Invalid gate state: {new_state}")
    current = get_gate_state()
    if current == "triggered" and new_state == "armed":
        raise ChaosError("Gate is triggered — cannot arm. Disarm first.")
    _set_kill_switch(new_state)
    return {"state": new_state, "previous": current}
```

Add both to the exports used by handler.py.

### [ ] T-002: Add GET /chaos/gate endpoint in handler.py
**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T-001
**Requirements**: FR-001, FR-005
**Description**: Add route following existing pattern:
```python
@app.get("/chaos/gate")
def get_chaos_gate():
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(status_code=401, ...)
    try:
        state = get_gate_state()
        return Response(status_code=200, body=orjson.dumps({"state": state}).decode())
    except ChaosError as e:
        return Response(status_code=500, ...)
```
Add `get_gate_state, set_gate_state` to the chaos imports block.

### [ ] T-003: Add PUT /chaos/gate endpoint in handler.py
**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T-001
**Requirements**: FR-002, FR-003, FR-004, FR-005
**Description**: Add route:
```python
@app.put("/chaos/gate")
def set_chaos_gate():
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(status_code=401, ...)
    try:
        body = app.current_event.json_body
        new_state = body.get("state")
        if new_state not in ("armed", "disarmed"):
            return Response(status_code=400, body="Invalid state")
        result = set_gate_state(new_state)
        return Response(status_code=200, body=orjson.dumps(result).decode())
    except ChaosError as e:
        # Triggered state prevention
        return Response(status_code=409, body=orjson.dumps({"detail": str(e)}).decode())
    except ValueError as e:
        return Response(status_code=400, body=orjson.dumps({"detail": str(e)}).decode())
```

### [ ] T-004: Add gate toggle UI component in chaos.html
**File**: `src/dashboard/chaos.html`
**Depends on**: T-002, T-003
**Requirements**: FR-006, FR-007, SC-001, SC-002, SC-003
**Description**: Add gate toggle to the top of the chaos dashboard (between alert banner and experiments section):

1. **Alpine.js state** (add to `chaosApp()` data): `gateState: null`, `gateLoading: false`

2. **Init**: Add `fetchGateState()` call to the init method. Fetches `GET /chaos/gate` and stores `gateState`.

3. **Toggle component**: DaisyUI card containing:
   - Label: "Chaos Gate"
   - Toggle input: checked when `gateState === 'armed'`, unchecked when `disarmed`
   - Disabled when `gateState === 'triggered'` or `gateLoading`
   - Color: `toggle-warning` when armed, `toggle-error` when triggered, default when disarmed
   - State label: "Armed" (amber), "Disarmed" (grey), "TRIGGERED" (red pulsing)

4. **toggleGate(newState) method**:
   - If arming: `if (!confirm('Arm chaos gate? Experiments will inject real faults.')) return;`
   - Set `gateLoading = true`
   - `PUT /chaos/gate` with `{state: newState}`
   - On success: update `gateState`
   - On error: show toast, revert toggle
   - Set `gateLoading = false`

5. **Auto-refresh**: Call `fetchGateState()` every 30 seconds via `setInterval` (FR-007 stale awareness).

### [ ] T-005: Add unit tests for gate endpoints
**File**: `tests/unit/test_chaos_gate_api.py`
**Depends on**: T-002, T-003
**Requirements**: SC-001, SC-002, SC-003
**Description**: Test both endpoints:
- GET 200 returns `{"state": "disarmed"}` (default)
- GET 200 returns `{"state": "armed"}` when armed
- GET 200 returns `{"state": "triggered"}` when triggered
- GET 401 for unauthenticated request
- PUT 200 arm: body `{"state": "armed"}` returns `{"state": "armed", "previous": "disarmed"}`
- PUT 200 disarm: returns `{"state": "disarmed", "previous": "armed"}`
- PUT 409 when trying to arm while triggered
- PUT 400 when body contains `{"state": "triggered"}`
- PUT 400 when body is missing state
- PUT 401 for unauthenticated request

Mock SSM `get_parameter` and `put_parameter` for all tests.

## Task Summary

| Phase | Tasks | Dependencies |
|-------|-------|-------------|
| 1. Implementation | T-001 to T-005 | T-001 first, then T-002+T-003 parallel, then T-004+T-005 parallel |

**Total**: 5 tasks
**Estimated time**: 1.5 hours
**Critical path**: T-001 → T-002/T-003 → T-004
