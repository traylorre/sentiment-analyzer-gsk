# Tasks: Pre-Flight Health Check Button

**Feature**: 1244-preflight-health
**Generated**: 2026-03-27
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

## Phase 1: Implementation

### [ ] T-001: Add get_system_health() wrapper in chaos.py
**File**: `src/lambdas/dashboard/chaos.py`
**Depends on**: None
**Requirements**: FR-002
**Description**: Add a thin public function `get_system_health(env: str) -> dict` that calls `_capture_baseline(env)` and returns the result. This avoids exporting a private function. Add `get_system_health` to the import list in handler.py alongside existing chaos imports.

### [ ] T-002: Add GET /chaos/health endpoint in handler.py
**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T-001
**Requirements**: FR-001, FR-003, FR-004
**Description**: Add route following the `list_chaos_experiments()` pattern (line 864):
```python
@app.get("/chaos/health")
def get_chaos_health():
    event = app.current_event.raw_event
    user_id = _get_chaos_user_id_from_event(event)
    if user_id is None:
        return Response(status_code=401, ...)
    try:
        health = get_system_health(ENVIRONMENT)
        return Response(status_code=200, body=orjson.dumps(health).decode())
    except EnvironmentNotAllowedError as e:
        return Response(status_code=403, ...)
    except ChaosError as e:
        return Response(status_code=500, ...)
```
Add `get_system_health` to the chaos imports block at line ~47.

### [ ] T-003: Add health check button and status cards in chaos.html
**File**: `src/dashboard/chaos.html`
**Depends on**: T-002
**Requirements**: FR-005, SC-001, SC-002
**Description**: Add UI elements in the chaos dashboard:

1. **Alpine.js state** (add to `chaosApp()` data): `healthCheck: null`, `healthLoading: false`, `healthCheckedAt: null`, `healthCooldown: false`

2. **Button**: "Pre-Flight Health Check" button above the experiments section. Disabled when `healthLoading || healthCooldown`. Shows spinner when loading.

3. **fetchHealth() method**: Calls `GET /chaos/health` with API key header. On success, stores result in `healthCheck` and sets `healthCheckedAt` to `new Date()`. Sets `healthCooldown = true` and clears after 3 seconds (debounce per FR-005). On timeout (15s), shows error toast.

4. **Status cards**: Shown when `healthCheck` is not null. Uses `x-for` over `Object.entries(healthCheck.dependencies)` to render 4 cards. Each card shows service name, badge (`badge-success` / `badge-error`), and error detail if degraded. Overall summary banner: green "All systems healthy" or red "N services degraded".

5. **Stale data indicator**: Show "Checked N minutes ago" below the cards. If > 5 minutes, use `text-warning` color.

### [ ] T-004: Add unit test for health endpoint
**File**: `tests/unit/test_chaos_health_api.py`
**Depends on**: T-002
**Requirements**: SC-003
**Description**: Test the `GET /chaos/health` endpoint:
- Test 200 with mocked `get_system_health()` returning all-healthy baseline
- Test 200 with mocked degraded baseline (verify `all_healthy: false`)
- Test 401 when `_get_chaos_user_id_from_event` returns None
- Test 500 when `get_system_health` raises ChaosError
- Verify response JSON shape: `captured_at`, `dependencies`, `all_healthy`, `degraded_services`

## Task Summary

| Phase | Tasks | Dependencies |
|-------|-------|-------------|
| 1. Implementation | T-001 to T-004 | Sequential: T-001 → T-002 → T-003/T-004 |

**Total**: 4 tasks
**Estimated time**: 1 hour
**Critical path**: T-001 → T-002 → T-003
