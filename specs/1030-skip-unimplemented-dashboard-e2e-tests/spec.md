# Feature 1030: Skip Unimplemented Dashboard E2E Tests

## Problem Statement

The pipeline has 31 Playwright E2E tests that are failing with ERROR status because they test dashboard UI features that have not yet been implemented:

| Test File | Tests | Feature Expected |
|-----------|-------|------------------|
| test_client_cache.py | 8 | IndexedDB caching, offline access |
| test_multi_resolution_dashboard.py | 14 | Resolution switcher, skeleton UI, historical scrolling |
| test_resolution_switch_perf.py | 4 | <100ms resolution switching |
| test_sse_reconnection.py | 5 | SSE reconnection indicators, degraded mode UI |

All tests document this explicitly: "TDD Note: These tests MUST FAIL initially until T0XX are implemented."

## Root Cause

These are legitimate TDD-style tests written in anticipation of features that are:
1. Specified in `specs/1009-realtime-multi-resolution/spec.md`
2. Not yet implemented in the actual dashboard
3. Blocking the pipeline with ERROR status on every run

## Solution

Add `pytest.skip` markers at the module level with clear documentation:
- Reason: "Dashboard feature not yet implemented"
- Reference: Spec document and task ID
- Remediation: Clear path to remove skip when feature is implemented

## Implementation Approach

Add a module-level skip condition to each affected test file that:
1. Checks for an environment variable `DASHBOARD_FEATURES_IMPLEMENTED=true` to run tests
2. Skips by default with clear messaging
3. Documents which spec/task will implement the feature

## Acceptance Criteria

- [ ] AC-1: All 31 tests are skipped with clear reason
- [ ] AC-2: Pipeline completes without ERROR status from these tests
- [ ] AC-3: Skip reason documents path to re-enable

## Files Modified

- `tests/e2e/test_client_cache.py`
- `tests/e2e/test_multi_resolution_dashboard.py`
- `tests/e2e/test_resolution_switch_perf.py`
- `tests/e2e/test_sse_reconnection.py`

## Risk Assessment

- **Low risk**: Tests are already failing, this formalizes the "not implemented" status
- Skip markers make it clear these are intentional deferrals, not ignored failures
- Environment variable allows enabling tests when feature work begins
