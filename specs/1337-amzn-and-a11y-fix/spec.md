# Feature 1337: amzn-and-a11y-fix

## Problem Statement

Six Playwright E2E tests fail across two unrelated sub-issues:

### Sub-Issue A: chart-zoom-data uses AMZN (3 tests)

`frontend/tests/e2e/chart-zoom-data.spec.ts` searches for AMZN ticker and expects OHLC
candle data, but the local API proxies to real Tiingo API which may not return AMZN price
data. Result: "0 price candles" assertion failures. The tests only mock anonymous auth but
use the REAL Tiingo API for OHLC data. AAPL is confirmed to have 1560 candles locally.

**Root Cause**: Ticker choice. AMZN is not reliably available in the local Tiingo data set.
AAPL has confirmed availability with abundant data.

### Sub-Issue B: Error boundary a11y (3 tests)

Three tests fail due to accessibility issues in the error boundary component and
keyboard navigation flakiness:

1. **chaos-accessibility.spec.ts T026**: axe-core detects violations in the error boundary
   fallback. The `ErrorFallback` component uses `role="alert"` on the outer div, but the
   buttons lack explicit `aria-label` attributes (they use visible text content which is
   acceptable). The real issue: the `<h2>` heading inside the error boundary doesn't have
   an associated landmark or the `role="alert"` container may need `aria-labelledby`.

2. **chaos-accessibility.spec.ts T027**: Error boundary button keyboard-focusability test.
   This test uses `.focus()` and `.toBeFocused()` directly, which is reliable. Should pass
   once axe violations are resolved.

3. **chaos-error-boundary.spec.ts T024**: Tab focus order test uses
   `page.keyboard.press('Tab')` three times from document start. Tab key behavior in
   headless Chromium is flaky — focus may land on skip links, the address bar, or other
   browser chrome before reaching error boundary buttons. The `keyboard.ts` helper
   explicitly documents this: "Chained Tab presses (2+) are banned."

**Root Cause**: T024 violates the project's keyboard testing convention (FR-007 in
keyboard.ts: single-Tab only, chained Tab banned). The test should use programmatic
`.focus()` instead, matching the pattern in chaos-accessibility.spec.ts T027.

## Affected Files

| File | Tests | Sub-Issue |
|------|-------|-----------|
| `frontend/tests/e2e/chart-zoom-data.spec.ts` | 3 (T: 1Y candles, zoom-out, range comparison) | A |
| `frontend/tests/e2e/chaos-accessibility.spec.ts` | 2 (T025 health banner, T026 error boundary) | B |
| `frontend/tests/e2e/chaos-error-boundary.spec.ts` | 1 (T024 keyboard nav) | B |
| `frontend/src/components/ui/error-boundary.tsx` | N/A (component fix) | B |

## Fix Strategy

### Sub-Issue A: AMZN to AAPL migration

Replace all AMZN references with AAPL in `chart-zoom-data.spec.ts`:
- Line 44-51: Search input fill 'AMZN' -> 'AAPL', suggestion role name regex
- Line 99-104: Same pattern in zoom-out test
- Line 177-182: Same pattern in range comparison test

No assertion threshold changes needed — AAPL has more data than AMZN, so
`>= 200` candles for 1Y and `>= 15` for 1M are conservative and correct.

### Sub-Issue B: Error boundary a11y fixes

#### Component fix (error-boundary.tsx):
1. Add `aria-labelledby` to the `role="alert"` container, pointing to the heading's ID
2. Add `id` to the `<h2>` heading element for the `aria-labelledby` reference
3. Add `autoFocus` or `useRef`+`useEffect` focus management so focus moves to the error
   container when it appears (WCAG 2.1 focus management for dynamic content)

#### Test fix (chaos-error-boundary.spec.ts T024):
Replace chained `page.keyboard.press('Tab')` with programmatic `.focus()` calls matching
the established pattern from `keyboard.ts` helper and `chaos-accessibility.spec.ts` T027.

## Why NOT Other Approaches

### Sub-Issue A alternatives rejected:
- **Mock OHLC API in chart-zoom-data tests**: Over-engineered. These tests validate chart
  zoom/range behavior, not data fetching. Using a real-data ticker (AAPL) is simpler and
  tests the full stack.
- **Add AMZN to mock data**: The tests intentionally test against real Tiingo API for
  OHLC. Adding mock data changes the test's nature.

### Sub-Issue B alternatives rejected:
- **Suppress axe-core violations**: Masks real accessibility issues.
- **Remove keyboard nav test**: Loses regression coverage. Fix the approach instead.
- **Use Tab key with increased timeout**: Tab flakiness is not a timing issue — it's a
  focus-target unpredictability issue in headless browsers.

## Separation of Concerns

- Sub-Issue A (ticker change) is purely a test data fix — zero component changes
- Sub-Issue B (a11y) requires both component enhancement and test approach correction
- The two sub-issues are completely independent and could ship separately

## Acceptance Criteria

1. All 3 chart-zoom-data tests pass with AAPL ticker
2. T026 (error boundary axe scan) passes with zero critical/serious violations
3. T027 (error boundary keyboard focus) continues to pass
4. T024 (error boundary keyboard nav) passes using programmatic focus
5. T025 (health banner axe scan) is unaffected (already passes)
6. No changes to production component behavior beyond accessibility improvements
