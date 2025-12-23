# Feature 1029: Fix E2E Test Timeout

## Problem Statement

The Preprod Integration Tests job in deploy.yml is timing out at 360 seconds (6 minutes) before pytest can complete, causing:
- All remaining tests to be marked as incomplete
- Test results artifact to not be generated (`preprod-test-results.xml`)
- Pipeline to fail with "timeout" reason instead of showing actual test results

## Evidence

From workflow run 20453562748:
```
##[error]Integration tests did not pass: timeout
##[warning]No files were found with the provided path: preprod-test-results.xml
```

## Root Cause

The 360s timeout was set with a "20% buffer over 279s avg runtime" but:
1. Playwright E2E tests add significant overhead (~10s per test for browser startup)
2. The test suite has grown to include more Playwright-based tests
3. Lambda cold starts during tests can add unpredictable delays

## Solution

Increase the timeout from 360s to 480s (8 minutes):
- Provides 33% buffer over current ~360s runtime
- Allows pytest to complete and generate results even if some tests are slow
- Ensures test results artifact is always uploaded

## Acceptance Criteria

- [ ] AC-1: Timeout increased to 480s in deploy.yml test-preprod job
- [ ] AC-2: Comment updated to reflect new timeout rationale
- [ ] AC-3: Pipeline completes without timeout (tests may still fail, but not due to timeout)

## Files Modified

- `.github/workflows/deploy.yml` - line ~1345, timeout value in test-preprod job

## Risk Assessment

- **Low risk**: This is a simple numeric change
- Increasing timeout does not fix underlying test failures, it just allows them to be reported properly
- If tests consistently take >8 minutes, we should investigate root causes (Lambda cold starts, test efficiency)
