# Implementation Plan: Pre-Flight Health Check Button

**Branch**: `1244-preflight-health` | **Date**: 2026-03-27 | **Spec**: [spec.md](spec.md)

## Summary

Expose the existing `_capture_baseline(env)` function via a new `GET /chaos/health` endpoint and add a UI button in chaos.html that displays dependency status cards. Zero new backend logic — pure wiring.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard), JavaScript (Alpine.js)
**Primary Dependencies**: boto3 (existing), orjson (existing)
**Storage**: None (stateless health check)
**Target Platform**: AWS Lambda (existing dashboard Lambda)
**Constraints**: Must reuse `_capture_baseline()` without modification
**Scale/Scope**: ~10 calls/day (manual pre-flight checks)

## Project Structure (in target repo: ../sentiment-analyzer-gsk/)

```text
src/lambdas/dashboard/
├── chaos.py       # NO CHANGE — _capture_baseline() already public-ready
├── handler.py     # MODIFY: Add GET /chaos/health route (~25 lines)

src/dashboard/
├── chaos.html     # MODIFY: Add health check button + status cards (~80 lines)

tests/unit/
├── test_chaos_health_api.py  # NEW: Endpoint contract test (~40 lines)
```

## Implementation (Single Phase)

### Step 1: Export _capture_baseline from chaos.py
- Make `_capture_baseline` importable by adding to the module's public API
- Or call it via a thin wrapper `get_system_health(env)` that delegates to `_capture_baseline`

### Step 2: Add GET /chaos/health endpoint in handler.py
- Follow existing pattern from `list_chaos_experiments()` (line 864)
- Auth: `_get_chaos_user_id_from_event(event)` — return 401 if None
- Call `_capture_baseline(ENVIRONMENT)` (or wrapper)
- Return 200 with health check result JSON
- Catch `EnvironmentNotAllowedError` → 403
- Catch `ChaosError` → 500

### Step 3: Add UI in chaos.html
- Add "Pre-Flight Check" button in the top section (before experiment list)
- Alpine.js state: `healthCheck: null`, `healthLoading: false`, `healthCheckedAt: null`
- On click: `fetchHealth()` — sets loading, calls `/chaos/health`, stores result
- Render 4 dependency cards using `x-for` over `healthCheck.dependencies`
- DaisyUI badges: `badge-success` for healthy, `badge-error` for degraded
- Show stale data warning if `healthCheckedAt` is > 5 minutes ago
- Debounce: disable button while `healthLoading` is true, re-enable after 3s minimum

### Step 4: Unit test
- Test 200 response with mock healthy baseline
- Test 401 for unauthenticated request
- Test response shape matches expected JSON structure
