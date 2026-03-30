# Feature Specification: Fix Cached Data E2E Tests (Empty Dashboard)

**Feature Branch**: `1273-cached-data-empty`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Three Playwright E2E tests fail because they assert cached data persistence without ever loading data first.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cached Data Tests Load Data Before Asserting Persistence (Priority: P1)

A developer pushes a PR that touches the dashboard frontend or the chaos testing infrastructure. The CI pipeline runs the Playwright E2E suite. The three "cached data" tests now properly load dashboard data (by searching for and selecting a ticker), verify the data is rendered, THEN block the API and assert the data persists. Tests pass deterministically on the first attempt without relying on CI retries.

**Why this priority**: These tests are the only E2E validation that cached data survives API outages -- a critical chaos resilience property (Feature 1265, US1/FR-015). With all three failing, there is zero automated verification of this property.

**Independent Test**: Run the three affected tests with `--retries=0` and confirm all pass on the first attempt.

**Acceptance Scenarios**:

1. **Given** the dashboard has loaded with AAPL ticker data (chart visible with price candles), **When** all API calls are blocked with 503, **Then** the chart and data remain visible and the `<main>` content text length exceeds 10 characters.
2. **Given** the dashboard has loaded with AAPL ticker data, **When** all API calls are aborted with `timedout`, **Then** the chart and data remain visible and interactive elements do not crash when clicked.
3. **Given** the dashboard has loaded with AAPL ticker data (cross-browser project), **When** all API calls are blocked with 503, **Then** the chart and data remain visible with text content exceeding 10 characters.

---

### User Story 2 - Tests Use Event-Based Waiting, Not Blind Timeouts (Priority: P1)

A developer reads `chaos-cached-data.spec.ts` or `chaos-cross-browser.spec.ts` and sees zero `waitForTimeout()` calls in the data-loading phase. The `beforeEach` block uses Playwright's built-in waiting mechanisms (`expect().toBeVisible()`, `expect().toHaveAttribute()`, `waitForResponse()`) to confirm data is rendered before proceeding.

**Why this priority**: Blind waits are the root cause -- `waitForTimeout(3000)` is insufficient for data loading and makes tests both slow and flaky. This directly follows the pattern established in Features 1270 and 1271.

**Independent Test**: Search each modified file for `waitForTimeout` in the `beforeEach` block and confirm zero instances remain in data-loading paths.

**Acceptance Scenarios**:

1. **Given** `chaos-cached-data.spec.ts` currently uses `waitForTimeout(3000)` in `beforeEach`, **When** the fix is applied, **Then** the `beforeEach` waits for a specific data element (chart with price candles) instead.
2. **Given** `chaos-cross-browser.spec.ts` currently uses `waitForTimeout(2000)` in `beforeEach`, **When** the fix is applied, **Then** the `beforeEach` waits for a specific data element instead.
3. **Given** the post-chaos `waitForTimeout(2000)` calls in individual tests, **When** the fix is applied, **Then** each is replaced with `waitForResponse()` observing the 503/timeout response, or removed if unnecessary.

---

### User Story 3 - Global Setup Handles Server-Not-Ready Gracefully (Priority: P2)

A developer runs `npx playwright test` and the global-setup cleanup phase logs a clear, non-scary message when the API server isn't ready yet, rather than a raw `TypeError: fetch failed` stack trace. The cleanup is already best-effort, but the error message should be informative.

**Why this priority**: This is cosmetic -- the global-setup catch block already swallows the error. But the `TypeError: fetch failed` in logs creates confusion during debugging. A clear message prevents wasted investigation time.

**Independent Test**: Run `npx playwright test` with a stopped API server and verify the console output includes a human-readable skip message, not a raw TypeError.

**Acceptance Scenarios**:

1. **Given** the API server is not yet running when global-setup executes, **When** the cleanup fetch fails with `TypeError: fetch failed`, **Then** the logged message says "API not reachable, skipping cleanup" (or similar) instead of printing the raw error object.

---

### Edge Cases

- What if the mock API doesn't serve AAPL ticker data? The local API mock (`run-local-api.py`) serves ticker search results. If it doesn't, the test will fail at the suggestion visibility check with a clear timeout error -- not a confusing empty-content assertion.
- What if chart rendering takes longer than 15 seconds in CI? The timeout is consistent with `sanity.spec.ts` which uses 15s successfully. CI retries (2 in config) provide additional safety.
- What if the empty state text changes? The tests no longer depend on empty state text. They wait for chart aria-label attributes which are stable.
- What if blocking the API also blocks pending chart data requests? The `beforeEach` waits for the chart to fully render (aria-label with price candle count) BEFORE any test blocks the API. By the time API is blocked, data is already in the DOM.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `chaos-cached-data.spec.ts` `beforeEach` MUST navigate to `/`, search for a ticker, select it, and wait for the chart to render with non-zero price candle data before returning control to the test body.
- **FR-002**: `chaos-cross-browser.spec.ts` `beforeEach` MUST navigate to `/`, search for a ticker, select it, and wait for the chart to render with non-zero price candle data before returning control to the test body.
- **FR-003**: The chart render verification MUST use `expect(chartContainer).toHaveAttribute('aria-label', /[1-9]\d* price candles/, { timeout: 15000 })` -- the same proven pattern from `sanity.spec.ts`.
- **FR-004**: The post-chaos `waitForTimeout(2000)` in each test body MUST be replaced with `page.waitForResponse()` observing the failed response, or `page.waitForLoadState('networkidle')`, or removed entirely if the subsequent assertion has its own timeout.
- **FR-005**: `global-setup.ts` MUST catch `TypeError` specifically and log a clear message indicating the API server is not reachable, rather than logging the raw error object.
- **FR-006**: No `waitForTimeout()` calls may remain in `chaos-cached-data.spec.ts` after the fix.
- **FR-007**: No `waitForTimeout()` calls may remain in the `beforeEach` of `chaos-cross-browser.spec.ts` after the fix. (Note: `waitForTimeout(5000)` in the SSE reconnection test T043 is acceptable if documented with justification -- it waits for reconnection attempts over time, not for a specific event.)

### Non-Functional Requirements

- **NFR-001**: Tests MUST pass deterministically with `--retries=0` in local and CI environments.
- **NFR-002**: Test duration increase from data loading is acceptable (expected 10-15s per test) since the alternative is 100% failure rate.
- **NFR-003**: The fix MUST NOT modify any application source code -- only test files and test infrastructure.

### Out of Scope

- Replacing `waitForTimeout` in `chaos-cross-browser.spec.ts` SSE reconnection test (T043) -- that test waits for time-based reconnection behavior, not a specific event.
- Modifying `triggerHealthBanner()` in `chaos-helpers.ts` -- already addressed by Feature 1271.
- Modifying other chaos test files not listed in this spec.

## Technical Design

### Data Loading Pattern (from sanity.spec.ts)

```typescript
// Proven pattern for loading dashboard data
const searchInput = page.getByPlaceholder(/search tickers/i);
await searchInput.fill('AAPL');
const suggestion = page.getByRole('option', { name: /AAPL/i });
await expect(suggestion).toBeVisible({ timeout: 10000 });
await suggestion.click();
const chartContainer = page.locator(
  '[role="img"][aria-label*="Price and sentiment chart"]'
);
await expect(chartContainer).toHaveAttribute(
  'aria-label',
  /[1-9]\d* price candles/,
  { timeout: 15000 }
);
```

### Post-Chaos Wait Replacement

```typescript
// BEFORE: blind wait after blocking API
await blockAllApi(page, 503);
await page.waitForTimeout(2000);

// AFTER: wait for a failed response to confirm the block is active
await blockAllApi(page, 503);
// Trigger a request that will hit the block (React Query refetch)
// and wait for the 503 to confirm chaos is active.
// If no automatic refetch, the block is immediately active and no wait is needed.
```

### Files Modified

| File | Change |
|------|--------|
| `frontend/tests/e2e/chaos-cached-data.spec.ts` | Replace `beforeEach` with data loading pattern; replace `waitForTimeout` in test bodies |
| `frontend/tests/e2e/chaos-cross-browser.spec.ts` | Replace `beforeEach` with data loading pattern for cached data test |
| `frontend/tests/e2e/global-setup.ts` | Improve error message in catch block |
