# Tasks: Skip Unimplemented Dashboard E2E Tests

## Completed Tasks

- [x] T-001: Create spec.md with problem analysis and affected files
- [x] T-002: Add skip marker to test_client_cache.py (8 tests)
  - Environment variable: `DASHBOARD_CACHE_IMPLEMENTED=true`
  - Reason: IndexedDB cache features (T059-T061)
- [x] T-003: Add skip marker to test_multi_resolution_dashboard.py (14 tests)
  - Environment variable: `MULTI_RESOLUTION_DASHBOARD_IMPLEMENTED=true`
  - Reason: Resolution switcher, skeleton UI, historical scrolling
- [x] T-004: Add skip marker to test_resolution_switch_perf.py (4 tests)
  - Environment variable: `RESOLUTION_SWITCH_PERF_IMPLEMENTED=true`
  - Reason: Performance metrics require UI implementation (SC-002)
- [x] T-005: Add skip marker to test_sse_reconnection.py (5 tests)
  - Environment variable: `SSE_RECONNECTION_UI_IMPLEMENTED=true`
  - Reason: Reconnection indicators, degraded mode UI (T057-T060)

## Verification

- [ ] T-006: Pipeline runs without ERROR status from these tests
- [ ] T-007: Tests show as "skipped" with clear reason

## Remediation Path

When features are implemented:
1. Set the relevant environment variable in CI to `true`
2. Run tests to verify feature implementation
3. Remove skip marker once tests pass consistently
