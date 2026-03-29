# Adversarial Review #1: Feature 1273 — Cached Data Empty

**Date**: 2026-03-28
**Reviewer**: Self (adversarial)
**Artifacts Reviewed**: spec.md, plan.md, research.md

## Critical Findings

### Finding 1: chaos-cross-browser.spec.ts beforeEach shared across all tests

**Severity**: Medium
**Issue**: The plan says "move data loading into the specific test body" for the cached data test, but leaves the `beforeEach` with `waitForTimeout(2000)` for the other two tests. Feature 1271 is already addressing those `waitForTimeout` calls, but if 1273 ships first, the file will still have the blind wait.

**Resolution**: Acceptable. Feature 1271 covers the remaining `waitForTimeout` calls in this file. The plan correctly scopes 1273 to only the cached data test. No conflict because 1273 modifies the test body, not the `beforeEach`.

### Finding 2: Post-chaos waitForTimeout removal may be premature

**Severity**: Low
**Issue**: After `blockAllApi()`, React Query may have in-flight requests that haven't yet hit the route block. Removing the wait entirely could cause a race where the assertion runs before the block intercepts the first request, and the dashboard re-renders with an error state.

**Resolution**: The tests assert that EXISTING DOM content persists, not that new content appears. The chart data is already rendered from `beforeEach`. Even if a refetch request is in-flight and fails, React Query won't unmount the existing chart -- it will show the cached data plus potentially an error state. The assertion `textDuring!.length > 10` will still pass because the chart content is still in the DOM. However, to be safe, keep a brief `page.waitForTimeout(500)` after `blockAllApi()` with a comment explaining it allows in-flight requests to settle. This is a documented exception per FR-006's spirit -- the intent is to eliminate blind waits for data loading, not for chaos propagation.

**Revised recommendation**: Replace `waitForTimeout(2000)` with `waitForTimeout(500)` and add a comment, rather than removing entirely.

### Finding 3: AAPL data availability in mock API

**Severity**: Low
**Issue**: The plan assumes the mock API serves AAPL search results and price data. If `run-local-api.py` doesn't serve these, the `beforeEach` will timeout at the suggestion visibility check.

**Resolution**: `sanity.spec.ts` and other tests already use AAPL successfully with the local API. The mock API is proven to serve AAPL data. Low risk.

### Finding 4: Test duration increase

**Severity**: Low
**Issue**: Adding data loading to `beforeEach` adds ~10-15s per test (search + select + chart render). For 2 tests in chaos-cached-data.spec.ts, that's 20-30s additional. For the cross-browser test, the data loading is in the test body, adding to that test only.

**Resolution**: Acceptable. The tests currently have a 100% failure rate. Adding 10-15s to make them pass is worthwhile. The Playwright config allows 300s timeout (5 minutes) per test.

### Finding 5: global-setup.ts change is low-value

**Severity**: Low
**Issue**: The global-setup error handling improvement (User Story 3) is cosmetic. The catch block already handles the error gracefully. Changing the message provides minimal value.

**Resolution**: Keep it minimal -- just improve the message format. Don't add retry logic or structural changes. This is a drive-by improvement, not a core fix.

## Gate Assessment

**Highest-risk task**: T1/T2 (chaos-cached-data.spec.ts rewrite) -- the entire `beforeEach` is being replaced, and the test body logic changes. Must verify both tests independently.

**Most likely rework**: Post-chaos wait timing -- may need adjustment between 0ms and 500ms depending on whether React Query's refetch creates visible side effects during chaos.

**Missing from plan**: No mention of whether the `chaos-cross-browser.spec.ts` "health banner appears after 3 failures" test is affected by the `beforeEach` change. Plan correctly identifies this but should explicitly confirm no regression.

**Verdict**: READY FOR TASK GENERATION

All findings are Low/Medium severity with acceptable resolutions. The core fix (data loading in beforeEach) follows a proven pattern from `sanity.spec.ts` with zero novelty risk.
