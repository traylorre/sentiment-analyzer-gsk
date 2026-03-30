# Implementation Plan: Fix Cached Data E2E Tests (Empty Dashboard)

**Branch**: `1273-cached-data-empty` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/1273-cached-data-empty/spec.md`

## Summary

Three Playwright E2E tests fail because they assert "previously loaded data" persists during API outages, but never load any data in the first place. The `beforeEach` navigates to `/` and waits 2-3 seconds, but the dashboard starts with an empty state (no ticker selected). Fix by adding a proper data loading step (search + select ticker + wait for chart) before each test's chaos injection phase.

## Technical Context

**Language/Version**: TypeScript (Playwright test files targeting Node.js 18+)
**Primary Dependencies**: `@playwright/test ^1.57.0`
**Storage**: N/A (test infrastructure only)
**Testing**: Playwright Test runner (`npx playwright test`)
**Target Platform**: CI runners (GitHub Actions) and local dev machines
**Project Type**: Web application (frontend E2E tests)
**Constraints**: Must work across all 5 Playwright projects (Mobile Chrome, Mobile Safari, Desktop Chrome, Firefox, WebKit)
**Scale/Scope**: 2 test files + 1 setup file, ~8 `waitForTimeout` replacements + data loading additions

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Unit test accompaniment | N/A | This IS a test fix -- no application code changes |
| GPG-signed commits | PASS | Will use `git commit -S` |
| Pipeline bypass prohibition | PASS | No bypasses planned |
| Feature branch workflow | PASS | On branch `1273-cached-data-empty` |
| Environment testing matrix | PASS | E2E tests run via Playwright config |
| Local SAST | N/A | No Python code changes |
| Tech debt tracking | PASS | This feature fixes broken tests |

**Verdict**: PASS -- all applicable gates satisfied.

## Project Structure

### Documentation (this feature)

```text
specs/1273-cached-data-empty/
├── research.md              # Root cause analysis
├── spec.md                  # Feature specification
├── plan.md                  # This file
├── tasks.md                 # Task breakdown
└── adversarial-review-1.md  # Adversarial review
```

### Source Code (files to modify)

```text
frontend/tests/e2e/
├── chaos-cached-data.spec.ts      # 5 waitForTimeout + missing data load
├── chaos-cross-browser.spec.ts    # 1 waitForTimeout in beforeEach + missing data load
└── global-setup.ts                # Improve error messaging
```

## Design Decisions

### D1: Use AAPL ticker for data loading

**Choice**: Use AAPL as the ticker in test setup, matching the pattern from `sanity.spec.ts` and `error-visibility-banner.spec.ts`.

**Rationale**: AAPL is the most commonly used ticker in the test suite and is guaranteed to be available in the mock API. Using a consistent ticker reduces variability.

**Alternative**: Use a dedicated test ticker (e.g., `e2e-CACHE-TEST`). Rejected because the mock API doesn't support custom tickers and adding them is out of scope.

### D2: Wait for chart aria-label, not main text content

**Choice**: Wait for `[role="img"][aria-label*="Price and sentiment chart"]` with a regex matching non-zero candle count.

**Rationale**: This is the most specific, stable indicator that real data has loaded. The `<main>` text content includes empty-state text which would give a false positive. The chart aria-label only contains candle counts after actual price data renders.

### D3: Keep post-chaos waitForTimeout as short waits where justified

**Choice**: Replace post-chaos `waitForTimeout(2000)` with either: (a) removal if the next assertion has its own timeout, or (b) a brief `waitForTimeout(500)` with comment explaining it allows in-flight requests to hit the route block.

**Rationale**: After `blockAllApi()`, React Query's next refetch cycle will hit the block. The assertion `expect(textDuring!.length).toBeGreaterThan(10)` is synchronous and doesn't need a wait -- the data is already in the DOM from the beforeEach. A short wait (500ms) allows any in-flight polling/refetch requests to settle, but is not strictly necessary since we're testing that existing DOM content persists.

### D4: Don't modify the beforeEach for non-cached-data tests in chaos-cross-browser.spec.ts

**Choice**: Only modify the `beforeEach` and the "cached data persists" test in `chaos-cross-browser.spec.ts`. Leave the banner and SSE tests alone.

**Rationale**: The banner test (`T042`) doesn't need pre-loaded data -- it works by triggering 3 failures via search. The SSE test (`T043`) monitors reconnection timing, not cached content. Only the cached data test (`T042 duplicate`) needs data loaded first.

**Challenge**: The `beforeEach` is shared across all tests in the describe block. Loading data for all tests would add unnecessary setup time to banner/SSE tests.

**Solution**: Move the data loading into the specific test body ("cached data persists during API outage") rather than `beforeEach`, OR make `beforeEach` smart (load data only when needed). The simplest approach: keep `beforeEach` for navigation, add data loading to the specific test.

## Implementation Phases

### Phase 1: Fix chaos-cached-data.spec.ts (T1-T2)

1. Rewrite `beforeEach` to load AAPL data using the proven sanity.spec.ts pattern
2. Replace `waitForTimeout(2000)` in T013 test body with assertion-based wait or removal
3. Replace `waitForTimeout(2000)` in T014 test body similarly
4. Verify both tests pass with `--retries=0`

### Phase 2: Fix chaos-cross-browser.spec.ts cached data test (T3)

1. Add data loading step inside the "cached data persists" test body (not beforeEach)
2. Replace `waitForTimeout(2000)` in test body
3. Leave `beforeEach` `waitForTimeout(2000)` for other tests to Feature 1271 (already addressed)
4. Verify all three tests in the file pass with `--retries=0`

### Phase 3: Improve global-setup.ts error messaging (T4)

1. Catch TypeError specifically and log a clear message
2. Verify with API server stopped

### Phase 4: Verification (T5)

1. Run all affected tests with `--retries=0`
2. Verify no `waitForTimeout` in data-loading paths
3. Confirm no regressions in other chaos tests
