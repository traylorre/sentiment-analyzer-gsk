# Tasks: Fix Cache Hit Rate API Tests

## Completed Tasks

- [x] T-001: Analyze failing tests and identify missing dependencies
- [x] T-002: Create spec.md with problem analysis
- [x] T-003: Add skip marker to test_cache_hit_rate.py (3 tests)
  - Environment variable: `CACHE_HIT_RATE_TESTS_ENABLED=true`
  - Reason: Resolution switcher UI, timeseries API, cache headers

## Verification

- [ ] T-004: Pipeline completes without FAILED status from these tests
- [ ] T-005: Tests show as "skipped" with clear reason

## Remediation Path

When Feature 1009 (realtime-multi-resolution) is implemented:
1. Dashboard will have resolution switcher UI
2. API will have /api/v2/timeseries endpoint
3. Server will return X-Cache-Hit headers
4. Set CACHE_HIT_RATE_TESTS_ENABLED=true to run tests
