# Tasks: Andon Cord Button

**Feature**: 1246-andon-cord
**Generated**: 2026-03-27
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Implementation

### [ ] T-001: Add pull_andon_cord() function in chaos.py
**File**: `src/lambdas/dashboard/chaos.py`
**Depends on**: None
**Requirements**: FR-001, FR-002, FR-003, FR-004, FR-008
**Description**: Add a public function that executes the andon cord sequence:

```python
def pull_andon_cord() -> dict[str, Any]:
    """Emergency stop: set kill switch + restore all active chaos configs."""
    result = {
        "kill_switch_set": False,
        "experiments_found": 0,
        "restored": 0,
        "failed": 0,
        "errors": [],
        "timestamp": datetime.now(UTC).isoformat() + "Z",
    }

    # Step 1: Kill switch FIRST (FR-002)
    try:
        _set_kill_switch("triggered")
        result["kill_switch_set"] = True
    except Exception as e:
        result["errors"].append(f"CRITICAL: Kill switch failed: {e}")
        # Continue with restores anyway

    # Step 2: Discover active snapshots
    try:
        ssm = _get_ssm_client()
        response = ssm.get_parameters_by_path(
            Path=f"/chaos/{ENVIRONMENT}/snapshot/",
            Recursive=False,
        )
        snapshots = response.get("Parameters", [])
        result["experiments_found"] = len(snapshots)
    except Exception as e:
        result["errors"].append(f"Cannot list snapshots: {e}")
        return result  # Can't restore what we can't find

    # Step 3: Restore each snapshot (best-effort, FR-003)
    for param in snapshots:
        param_name = param["Name"]
        scenario_key = param_name.split("/")[-1]  # e.g., "ingestion-failure"
        scenario_type = scenario_key.replace("-", "_")
        try:
            _restore_from_ssm(scenario_type)
            result["restored"] += 1
        except Exception as e:
            result["failed"] += 1
            result["errors"].append(f"Restore {scenario_type} failed: {e}")

    # Step 4: Disarm after restores complete (leave in safe state)
    if result["kill_switch_set"] and result["failed"] == 0:
        try:
            _set_kill_switch("disarmed")
        except Exception:
            pass  # Leave triggered if disarm fails — safer

    return result
```

Add `pull_andon_cord` to the module exports used by handler.py.

### [ ] T-002: Add POST /chaos/andon-cord endpoint in handler.py
**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T-001
**Requirements**: FR-001, FR-005
**Description**: Add route following existing chaos endpoint pattern:
```python
@app.post("/chaos/andon-cord")
def pull_chaos_andon_cord():
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(status_code=401, ...)
    try:
        result = pull_andon_cord()
        status = 200 if result["kill_switch_set"] else 500
        return Response(status_code=status, body=orjson.dumps(result).decode())
    except EnvironmentNotAllowedError as e:
        return Response(status_code=403, ...)
    except Exception as e:
        return Response(status_code=500, body=orjson.dumps({
            "detail": f"Andon cord failed: {e}",
            "fallback": f"aws ssm put-parameter --name /chaos/{ENVIRONMENT}/kill-switch --value triggered --overwrite"
        }).decode())
```
Add `pull_andon_cord` to the chaos imports block.

### [ ] T-003: Add emergency stop button and confirmation modal in chaos.html
**File**: `src/dashboard/chaos.html`
**Depends on**: T-002
**Requirements**: FR-006, FR-007, SC-001
**Description**: Add the andon cord UI elements:

1. **Alpine.js state** (add to `chaosApp()` data): `andonLoading: false`, `andonResult: null`, `showAndonModal: false`

2. **Emergency stop button**: Large red button positioned in the navbar area (visible at all times):
   ```html
   <button class="btn btn-error btn-lg gap-2"
           :disabled="andonLoading"
           @click="showAndonModal = true">
       <svg><!-- warning icon --></svg>
       EMERGENCY STOP
   </button>
   ```
   Shows spinner when `andonLoading`.

3. **Confirmation modal** (DaisyUI modal):
   - Title: "Pull Andon Cord?"
   - Body: "This will immediately: (1) Set kill switch to TRIGGERED, (2) Restore ALL chaos-injected configurations, (3) Block all new experiments. This action cannot be undone from the UI."
   - Actions: "Cancel" (closes modal) and "PULL CORD" (red button, calls `pullAndonCord()`)

4. **pullAndonCord() method**:
   - Set `andonLoading = true`, close modal
   - `POST /chaos/andon-cord` with API key header
   - On success: store `andonResult`, refresh gate state (`fetchGateState()` if Feature 1245 is present)
   - On 401: show toast "Auth expired. Fallback: scripts/chaos/andon-cord.sh <env>"
   - On error: show toast with fallback CLI command
   - Set `andonLoading = false`

5. **Result display**: When `andonResult` is not null, show a card with:
   - Kill switch status (green check or red X)
   - Experiments found / restored / failed counts
   - Error details if any

### [ ] T-004: Add unit tests for andon cord
**File**: `tests/unit/test_chaos_andon_cord_api.py`
**Depends on**: T-001, T-002
**Requirements**: SC-001, SC-002, SC-003
**Description**: Test the endpoint and core logic:

**Endpoint tests**:
- Test 200 with successful cord pull (mock pull_andon_cord returning success)
- Test 401 for unauthenticated request
- Test 403 for prod environment

**Logic tests** (test pull_andon_cord directly):
- Test successful pull: mock SSM get_parameters_by_path returning 2 snapshots, mock _restore_from_ssm succeeding. Verify `kill_switch_set=True, restored=2, failed=0`.
- Test partial failure: mock first restore succeeding, second raising. Verify `restored=1, failed=1, errors` contains the failure message.
- Test no snapshots: mock get_parameters_by_path returning empty list. Verify `kill_switch_set=True, restored=0`.
- Test kill-switch-first ordering: use `unittest.mock.call_args_list` to verify `_set_kill_switch("triggered")` is called before any `_restore_from_ssm`.
- Test idempotent: call twice, verify second call is safe (no errors, same result shape).
- Test SSM unreachable for snapshot listing: verify kill switch still set, errors list populated.

## Task Summary

| Phase | Tasks | Dependencies |
|-------|-------|-------------|
| 1. Implementation | T-001 to T-004 | T-001 first, then T-002, then T-003+T-004 parallel |

**Total**: 4 tasks
**Estimated time**: 1.5 hours
**Critical path**: T-001 → T-002 → T-003
