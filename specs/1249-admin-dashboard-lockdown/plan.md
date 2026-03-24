# Implementation Plan: Admin Dashboard Lockdown

**Branch**: `1249-admin-dashboard-lockdown` | **Date**: 2026-03-23 (v3 — post-adversarial) | **Spec**: [spec.md](spec.md)

## Summary

Lock down admin dashboard routes, strip information leakage from health/runtime endpoints, fix a missing auth bug on refresh/status, and enforce session validation on 4 data endpoints. All application-level changes — no Terraform.

## Adversarial Review Resolution

| # | Finding | Resolution |
|---|---------|------------|
| Health `"ok"` vs `"healthy"` | Keep `"healthy"` — deploy smoke tests grep for `"status"` key only (deploy.yml:1167, 2033) |
| Missing auth_service import | Added explicit import step to T006 |
| Table param for session validation | Use module-level `USERS_TABLE` (handler.py:78) directly |
| Refresh/status ownership | Added ownership check to T005 (query config, verify user_id match) |
| Runtime response shape | Explicit: `{"sse_url": null, "environment": "production"}` |
| Frontend breakage | False alarm — customer frontend is on Amplify, never hits admin routes |
| Deploy smoke test | False alarm — verified all 3 checks pass with stripped response |
| refresh_session skip | Correct design — add code comment explaining rationale |
| Case sensitivity | `.lower()` in `_is_dev_environment()` |

## Changes by File

### 1. `src/lambdas/dashboard/handler.py` (~50 lines changed)

- **Lines 69-70**: Add `auth_service` and `SessionRevokedException` imports
- **Line 92**: Add `_is_dev_environment()` helper (fail-closed, case-insensitive)
- **Lines 129-146**: Rewrite `_get_user_id_from_event()` to implement session validation
- **Admin routes**: Add early-return 404 to `serve_index()`, `serve_chaos()`, `serve_static()`, `api_index()`
- **New route**: `GET /favicon.ico` — 404 in non-dev
- **Line 374**: Health check — strip `table`/`environment` in non-dev, keep `"healthy"` status
- **Line 410**: Runtime config — return `{"sse_url": null, "environment": "production"}` in non-dev
- **Lines 431, 483, 547, 656**: Remove `validate_session=False` from 4 data endpoints

### 2. `src/lambdas/dashboard/router_v2.py` (~10 lines changed)

- **Line 718**: Add comment explaining why `refresh_session()` intentionally skips validation
- **Lines 1261-1265**: Add `_require_user_id()` + ownership check to `get_refresh_status()`

### 3. Test Files (~250 lines new)

- `tests/unit/test_admin_lockdown.py` — 19 unit tests
- `tests/e2e/test_admin_lockdown_preprod.py` — 8 E2E tests
- Updates to existing test fixtures for session validation

## Risk Mitigation

- **Deploy compatibility**: Verified deploy.yml smoke tests only check valid JSON + `"status"` key presence
- **Session validation regression**: Broad `except Exception` in validation prevents 500s — degrades to "no session" rather than crashing
- **Frontend compatibility**: Customer frontend on Amplify never hits admin routes. `/api/v2/runtime` returns `null` for `sse_url` — frontend SSE connection uses its own config lookup
- **Ownership check**: Uses same config key pattern as existing CRUD endpoints in router_v2.py
