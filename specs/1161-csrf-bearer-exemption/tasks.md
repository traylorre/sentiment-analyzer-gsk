# Feature 1161: Tasks

## Implementation Tasks

- [x] T1161.1: Update CSRF_EXEMPT_PATHS in csrf.py
- [x] T1161.2: Add unit test verifying exemptions
- [x] T1161.3: Verify E2E tests pass in CI (Deploy Pipeline run 20767209754 - SUCCESS)

## Task Details

### T1161.1: Update CSRF_EXEMPT_PATHS
- File: `src/lambdas/shared/auth/csrf.py`
- Add `/api/v2/auth/signout` to CSRF_EXEMPT_PATHS
- Add `/api/v2/auth/session/refresh` to CSRF_EXEMPT_PATHS
- Update comments to explain Bearer token exemption rationale

### T1161.2: Add unit test
- File: `tests/unit/middleware/test_csrf.py`
- Add test `test_bearer_endpoints_exempt_from_csrf`
- Verify both endpoints return True from is_csrf_exempt()

### T1161.3: Verify E2E tests
- Wait for CI pipeline to run
- Confirm `test_signout_invalidates_session` passes
- Confirm `test_session_refresh_extends_expiry` passes
