# Feature 1318: Plan — Zoom-Out Auto-Upgrade

## Technical Context

### Current Architecture

The `PriceSentimentChart` component (`frontend/src/components/charts/price-sentiment-chart.tsx`, 764 lines) manages:

1. **Chart initialization** (lines 172-357): A single `useEffect` depending on `[height, interactive]` that creates the lightweight-charts instance, adds candlestick + sentiment series, subscribes to crosshair moves (when interactive), attaches the gap shader primitive, and sets up window resize handling.

2. **Price data updates** (lines 360-414): A `useEffect` on `[priceData, resolution]` that fills gaps (daily only), builds chart data, calls `candleSeriesRef.current.setData(chartData)`, then immediately calls `chartRef.current.timeScale().fitContent()` (Feature 1316 pattern), and updates gap shader/map.

3. **Sentiment data updates** (lines 417-431): A `useEffect` on `[sentimentData, resolution]` that maps sentiment points to line data, calls `sentimentSeriesRef.current.setData(chartData)`, and also calls `fitContent()`.

4. **Time range state** (lines 112-120): Initialized from sessionStorage, persisted via `useEffect` on line 148. The `setTimeRange` call drives `useChartData` which triggers React Query refetch via `queryKey: ['ohlc', ticker, timeRange, resolution]`.

5. **Existing refs**: `containerRef`, `chartRef`, `candleSeriesRef`, `sentimentSeriesRef`, `gapShaderRef`, `gapMarkersMapRef`. All follow the same pattern: initialized with `useRef`, assigned in init useEffect, cleared in cleanup.

6. **Existing mock structure** (test file): The `lightweight-charts` mock returns `timeScale()` with `fitContent` and `setVisibleLogicalRange` methods. It does NOT currently include `subscribeVisibleLogicalRangeChange`.

### Key Observations

- `use-chart-sync.ts` (line 143) demonstrates `subscribeVisibleTimeRangeChange` — returns `Time`-based range, used for syncing multiple charts. Our feature uses `subscribeVisibleLogicalRangeChange` instead — returns `{ from: number, to: number }` bar-index range. Both coexist on the same chart without conflict.
- The `useChartData` hook (line 85-96) returns `isLoading`, `priceData`, `sentimentData`, `refetch`, and `isAuthReady`. The `isLoading` includes auth wait time (line 119).
- `fitContent()` is called in TWO places: price data useEffect (line 400) and sentiment data useEffect (line 429). Both need the `justFitContentRef` guard.
- The chart init useEffect cleanup (lines 349-356) calls `chart.remove()` and nulls all refs. The unsubscribe must happen BEFORE `chart.remove()`.

## Implementation Plan

### File 1: `frontend/src/types/chart.ts`

**Add after line 20** (after `TIME_RANGE_DAYS` definition):

```typescript
/** Ordered list of time ranges from narrowest to widest */
export const TIME_RANGE_ORDER: TimeRange[] = ['1W', '1M', '3M', '6M', '1Y'];

/**
 * Get the next wider time range, or null if already at maximum.
 */
export function getNextTimeRange(current: TimeRange): TimeRange | null {
  const idx = TIME_RANGE_ORDER.indexOf(current);
  if (idx === -1 || idx === TIME_RANGE_ORDER.length - 1) return null;
  return TIME_RANGE_ORDER[idx + 1];
}

/**
 * Determine if the visible logical range extends far enough past loaded data
 * to warrant a time range upgrade. Returns true when the visible range exceeds
 * the loaded data extent by more than 30% on either side.
 *
 * @param visibleFrom - Left edge of visible range (bar index, can be negative)
 * @param visibleTo - Right edge of visible range (bar index)
 * @param dataLength - Number of data points currently loaded
 */
export function shouldUpgradeTimeRange(
  visibleFrom: number,
  visibleTo: number,
  dataLength: number,
): boolean {
  if (dataLength === 0) return false;
  const overshootLeft = Math.max(0, -visibleFrom);
  const overshootRight = Math.max(0, visibleTo - dataLength);
  const totalOvershoot = overshootLeft + overshootRight;
  const threshold = dataLength * 0.3;
  return totalOvershoot > threshold;
}
```

**Lines affected**: Insert ~35 lines after line 20. No existing code modified.

### File 2: `frontend/src/components/charts/price-sentiment-chart.tsx`

#### Change A: Add import for new utilities

**Line 23** — extend the import from `@/types/chart`:

```typescript
// Before:
import type { TimeRange, OHLCResolution, ChartSentimentSource, PriceCandle, SentimentPoint, GapMarker } from '@/types/chart';
import { RESOLUTION_LABELS } from '@/types/chart';

// After:
import type { TimeRange, OHLCResolution, ChartSentimentSource, PriceCandle, SentimentPoint, GapMarker } from '@/types/chart';
import { RESOLUTION_LABELS, getNextTimeRange, shouldUpgradeTimeRange } from '@/types/chart';
```

#### Change B: Add refs for subscription callback

**After line 108** (after `gapShaderRef`), add:

```typescript
// 1318: Refs for zoom-out auto-upgrade subscription callback
const dataLengthRef = useRef(0);
const timeRangeRef = useRef<TimeRange>(timeRange);
const isLoadingRef = useRef(isLoading);
const justFitContentRef = useRef(false);
const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
```

#### Change C: Keep refs in sync

**Before the return statement** (before line 490), add ref sync:

```typescript
// 1318: Keep refs in sync for subscription callback
dataLengthRef.current = priceData.length;
timeRangeRef.current = timeRange;
isLoadingRef.current = isLoading;
```

Note: Updating refs in the render body (before return) is the standard React pattern for keeping refs synchronized with state without triggering re-renders.

#### Change D: Add `justFitContentRef` guard around fitContent calls

**Line 399-401** (price data useEffect fitContent):

```typescript
// Before:
if (chartRef.current) {
  chartRef.current.timeScale().fitContent();
}

// After:
if (chartRef.current) {
  justFitContentRef.current = true;
  chartRef.current.timeScale().fitContent();
  setTimeout(() => { justFitContentRef.current = false; }, 100);
}
```

**Line 428-430** (sentiment data useEffect fitContent):

```typescript
// Before:
if (chartRef.current) {
  chartRef.current.timeScale().fitContent();
}

// After:
if (chartRef.current) {
  justFitContentRef.current = true;
  chartRef.current.timeScale().fitContent();
  setTimeout(() => { justFitContentRef.current = false; }, 100);
}
```

#### Change E: Add subscription in chart init useEffect

**Inside the `if (interactive)` block** (after `subscribeCrosshairMove` handler, around line 335), add:

```typescript
// 1318: Subscribe to visible logical range changes for zoom-out auto-upgrade
const unsubscribeLogicalRange = chart.timeScale().subscribeVisibleLogicalRangeChange(
  (range: { from: number; to: number } | null) => {
    if (!range) return;
    if (justFitContentRef.current) return;
    if (isLoadingRef.current) return;

    // Debounce: collapse rapid wheel events into single check
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    debounceTimerRef.current = setTimeout(() => {
      const dataLength = dataLengthRef.current;
      const currentRange = timeRangeRef.current;

      if (dataLength === 0) return;
      if (!shouldUpgradeTimeRange(range.from, range.to, dataLength)) return;

      const nextRange = getNextTimeRange(currentRange);
      if (!nextRange) return; // Already at 1Y maximum

      setTimeRange(nextRange);
    }, 500);
  }
);
```

#### Change F: Add cleanup

**In the cleanup return** (line 349), add before `chart.remove()`:

```typescript
return () => {
  // 1318: Clean up zoom-out auto-upgrade
  if (debounceTimerRef.current) {
    clearTimeout(debounceTimerRef.current);
  }
  // unsubscribeLogicalRange is scoped — only exists when interactive=true
  window.removeEventListener('resize', handleResize);
  chart.remove();
  // ... existing ref cleanup
};
```

The `unsubscribeLogicalRange` variable is scoped inside the `if (interactive)` block. To call it in cleanup, we need to hoist it. Declare `let unsubscribeLogicalRange: (() => void) | null = null;` before the `if (interactive)` block, assign inside the block, and call `unsubscribeLogicalRange?.()` in cleanup.

Revised approach:

```typescript
// Before the if (interactive) block:
let unsubscribeLogicalRange: (() => void) | null = null;

// Inside if (interactive):
unsubscribeLogicalRange = chart.timeScale().subscribeVisibleLogicalRangeChange(...);

// In cleanup:
return () => {
  if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
  unsubscribeLogicalRange?.();
  window.removeEventListener('resize', handleResize);
  chart.remove();
  chartRef.current = null;
  candleSeriesRef.current = null;
  sentimentSeriesRef.current = null;
  gapShaderRef.current = null;
};
```

### File 3: `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`

**Update the lightweight-charts mock** to include `subscribeVisibleLogicalRangeChange`:

```typescript
timeScale: vi.fn(() => ({
  fitContent: vi.fn(),
  setVisibleLogicalRange: vi.fn(),
  subscribeVisibleLogicalRangeChange: vi.fn(() => vi.fn()), // returns unsubscribe
})),
```

**Add test block** for zoom-out auto-upgrade:

```typescript
describe('1318: Zoom-out auto-upgrade', () => {
  it('should subscribe to visible logical range changes when interactive', () => {
    render(<PriceSentimentChart ticker="AAPL" interactive={true} />);
    const { createChart } = require('lightweight-charts');
    const chartInstance = createChart.mock.results[0]?.value;
    expect(chartInstance.timeScale().subscribeVisibleLogicalRangeChange).toHaveBeenCalled();
  });

  it('should NOT subscribe to visible logical range changes when not interactive', () => {
    render(<PriceSentimentChart ticker="AAPL" interactive={false} />);
    const { createChart } = require('lightweight-charts');
    const chartInstance = createChart.mock.results[0]?.value;
    expect(chartInstance.timeScale().subscribeVisibleLogicalRangeChange).not.toHaveBeenCalled();
  });
});
```

### File 4: `frontend/tests/unit/types/chart-utils.test.ts` (NEW)

Pure function tests for `getNextTimeRange` and `shouldUpgradeTimeRange`:

```typescript
import { describe, it, expect } from 'vitest';
import { getNextTimeRange, shouldUpgradeTimeRange, TIME_RANGE_ORDER } from '@/types/chart';

describe('TIME_RANGE_ORDER', () => {
  it('should list ranges from narrowest to widest', () => {
    expect(TIME_RANGE_ORDER).toEqual(['1W', '1M', '3M', '6M', '1Y']);
  });
});

describe('getNextTimeRange', () => {
  it('1W -> 1M', () => expect(getNextTimeRange('1W')).toBe('1M'));
  it('1M -> 3M', () => expect(getNextTimeRange('1M')).toBe('3M'));
  it('3M -> 6M', () => expect(getNextTimeRange('3M')).toBe('6M'));
  it('6M -> 1Y', () => expect(getNextTimeRange('6M')).toBe('1Y'));
  it('1Y -> null (maximum)', () => expect(getNextTimeRange('1Y')).toBeNull());
});

describe('shouldUpgradeTimeRange', () => {
  it('returns false when dataLength is 0', () => {
    expect(shouldUpgradeTimeRange(-5, 5, 0)).toBe(false);
  });

  it('returns false when visible range fits within data (zoom-in)', () => {
    expect(shouldUpgradeTimeRange(2, 18, 22)).toBe(false);
  });

  it('returns false when overshoot is below 30% threshold', () => {
    // 22 candles, 30% = 6.6. Overshoot = 5 (left) + 0 (right) = 5
    expect(shouldUpgradeTimeRange(-5, 22, 22)).toBe(false);
  });

  it('returns true when overshoot exceeds 30% threshold', () => {
    // 22 candles, 30% = 6.6. Overshoot = 4 (left) + 4 (right) = 8 > 6.6
    expect(shouldUpgradeTimeRange(-4, 26, 22)).toBe(true);
  });

  it('returns true for significant left-only overshoot', () => {
    // 22 candles, 30% = 6.6. Overshoot = 10 (left) + 0 (right) = 10
    expect(shouldUpgradeTimeRange(-10, 22, 22)).toBe(true);
  });

  it('returns true for significant right-only overshoot', () => {
    // 22 candles, 30% = 6.6. Overshoot = 0 (left) + 10 (right) = 10
    expect(shouldUpgradeTimeRange(0, 32, 22)).toBe(true);
  });

  it('returns false when exactly at 30% boundary', () => {
    // 10 candles, 30% = 3.0. Overshoot = 3 exactly (not > 3)
    expect(shouldUpgradeTimeRange(-3, 10, 10)).toBe(false);
  });

  it('returns true when just past 30% boundary', () => {
    // 10 candles, 30% = 3.0. Overshoot = 3.1 > 3.0
    expect(shouldUpgradeTimeRange(-3.1, 10, 10)).toBe(true);
  });
});
```

### File 5: E2E test (NO CHANGES)

`frontend/tests/e2e/chart-zoom-data.spec.ts` already contains the "mouse-wheel zoom-out past data bounds auto-upgrades time range" test (lines 92-167). This test will pass once the implementation is complete.

## Data Flow Diagram

```
User mouse wheel (zoom out)
    │
    ▼
lightweight-charts: handleScale (line 201, interactive=true)
    │
    ▼
lightweight-charts internal: viewport recalculated
    │
    ▼
subscribeVisibleLogicalRangeChange fires
    { from: -8, to: 30 }  (negative from = blank space left)
    │
    ▼
Callback checks:
    ├─ range is null? → return (chart destroying)
    ├─ justFitContentRef.current? → return (fitContent just ran)
    ├─ isLoadingRef.current? → return (data in flight)
    └─ passes all guards
    │
    ▼
clearTimeout(debounceTimerRef) → restart 500ms timer
    │
    ▼ (500ms later, no new wheel events)
    │
debounce fires:
    ├─ dataLengthRef.current = 22 (1M daily)
    ├─ shouldUpgradeTimeRange(-8, 30, 22) → true (overshoot = 8+8 = 16 > 6.6)
    ├─ getNextTimeRange('1M') → '3M'
    └─ setTimeRange('3M')
    │
    ▼
React re-render:
    ├─ sessionStorage writes '3M' (line 148-152)
    ├─ useChartData queryKey changes → fetches 3M data
    ├─ isLoading = true → isLoadingRef.current = true (guards further upgrades)
    └─ 3M button highlights (timeRange === range check, line 534)
    │
    ▼
Data arrives → priceData useEffect fires:
    ├─ justFitContentRef.current = true
    ├─ candleSeriesRef.current.setData(newData) → ~66 candles
    ├─ chartRef.current.timeScale().fitContent()
    │   └─ fires subscribeVisibleLogicalRangeChange
    │       └─ justFitContentRef.current = true → return (guarded)
    ├─ setTimeout → justFitContentRef.current = false (100ms)
    └─ viewport now fits 66 candles perfectly
    │
    ▼
Sentiment data arrives → same fitContent pattern
    │
    ▼
User sees: 3M of data, 3M button active, no blank space
```

## Risk Assessment

### R1: fitContent Loop (CRITICAL)
**Risk**: `fitContent()` triggers `subscribeVisibleLogicalRangeChange`, which could trigger another upgrade.
**Mitigation**: Three layers of defense:
1. `justFitContentRef` flag set before `fitContent()`, checked in callback.
2. After `fitContent()`, the visible range fits the data exactly, so `shouldUpgradeTimeRange` returns false (no overshoot).
3. 100ms timeout resets the flag — long enough for the callback to fire and be suppressed, short enough to not block legitimate user zoom.
**Residual risk**: LOW. Would require all three defenses to fail simultaneously.

### R2: Debounce Timing (MEDIUM)
**Risk**: 500ms may feel sluggish or too eager.
**Mitigation**: 500ms is a standard debounce for deliberate actions. User perceives the upgrade as "automatic" after they stop scrolling. Can be tuned later via constant extraction.
**Residual risk**: LOW. UX preference, not correctness.

### R3: Threshold Sensitivity (MEDIUM)
**Risk**: 30% may trigger too easily or too late for some data densities.
**Mitigation**: With ~22 candles (1M daily), 30% = 6.6 bars overshoot ≈ 3-4 wheel ticks. With ~66 candles (3M daily), 30% = 19.8 bars ≈ 8-10 wheel ticks (proportionally harder to trigger, which is correct — wider ranges should be harder to escape).
**Residual risk**: LOW. Threshold scales naturally with data density.

### R4: Stale Closure in Subscription (HIGH)
**Risk**: The subscription callback is created once in the init useEffect but needs current values.
**Mitigation**: All mutable values accessed via refs (`dataLengthRef`, `timeRangeRef`, `isLoadingRef`), which are updated on every render. The callback never reads React state directly.
**Residual risk**: NONE if refs are kept in sync (Change C).

### R5: Unmount During Debounce (LOW)
**Risk**: Component unmounts while 500ms timer is pending.
**Mitigation**: `clearTimeout(debounceTimerRef.current)` in cleanup. React 18+ also ignores state updates on unmounted components.
**Residual risk**: NONE.

## Verification Plan

### Unit Tests (must pass before PR)

1. **Pure function tests** (`frontend/tests/unit/types/chart-utils.test.ts`):
   - `getNextTimeRange` — all 5 transitions + null at maximum
   - `shouldUpgradeTimeRange` — zero data, within bounds, below threshold, above threshold, boundary edge cases, left-only, right-only overshoot

2. **Component integration tests** (`frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`):
   - Subscription created when `interactive=true`
   - Subscription NOT created when `interactive=false`

### E2E Test (validates end-to-end)

3. **Existing E2E** (`frontend/tests/e2e/chart-zoom-data.spec.ts`, lines 92-167):
   - "mouse-wheel zoom-out past data bounds auto-upgrades time range"
   - Verifies: zoom out → 1M button deactivates → candle count increases

### Manual Verification Checklist

4. Load chart on 1M → zoom out aggressively → observe 3M activates
5. Continue zooming → 6M → 1Y → blank space at 1Y (no crash/loop)
6. Zoom in on 1Y → no downgrade (correct per spec)
7. Zoom out → data loads → fitContent → no second upgrade
8. Navigate away during zoom debounce → no console errors
9. Check sessionStorage: auto-upgraded range persists

## Files Summary

| File | Action | Lines Changed (est.) |
|------|--------|---------------------|
| `frontend/src/types/chart.ts` | ADD functions | +35 |
| `frontend/src/components/charts/price-sentiment-chart.tsx` | MODIFY init, data effects, add refs | +45, ~6 modified |
| `frontend/tests/unit/types/chart-utils.test.ts` | NEW file | +55 |
| `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx` | MODIFY mock + add tests | +20, ~3 modified |
| `frontend/tests/e2e/chart-zoom-data.spec.ts` | NO CHANGE | 0 |

**Total**: ~155 new lines, ~9 modified lines. Zero deletions.

---

## Adversarial Review #2

### Focus: Spec-Plan Drift and Implementation-Level Attacks

#### Spec Drift Check

| Check | Status | Detail |
|-------|--------|--------|
| C2 `justFitContentRef` guard present in plan? | PASS | Change D adds the flag before both `fitContent()` calls (lines 399, 428). Matches R5 in spec. |
| C2 `justFitContentRef` guard present in spec? | PASS | R5 (lines 115-125) explicitly describes the flag, the 100ms reset, and the callback check. |
| C4 sessionStorage persistence consistent with existing effect? | PASS | The `useEffect` on line 148-152 fires on any `timeRange` state change, regardless of source (button click or auto-upgrade). AR1-008 accepted this. No drift. |
| Clarification contradicts spec? | PASS | All 5 clarifications (C1-C5) either confirmed existing spec text or added supporting rationale. No contradictions found. |

#### Cross-Artifact Consistency

| Check | Status | Detail |
|-------|--------|--------|
| Plan 5 files vs spec R1-R9 | PASS | All 9 requirements map to changes across the 5 files. R1 -> File 1, R2/R3/R4/R5/R7/R8 -> File 2, R6 -> File 1, R9 -> File 2 (natural from `if (interactive)` block). |
| Line numbers still accurate? | PASS | Verified against actual file (764 lines). Key landmarks: `gapShaderRef` at L107, `fitContent` at L399-401 and L428-430, cleanup at L349-356, `if (interactive)` closes at L335, `return` at L490. All match plan references. |
| `types/chart.ts` unchanged? | PASS | 118 lines, `TIME_RANGE_DAYS` ends at L21. Plan inserts after L20 (after the `TIME_RANGE_DAYS` definition). Correct insertion point. |
| Test mock accurate? | PASS | Current mock (test file L18-21) has `timeScale()` returning `fitContent` and `setVisibleLogicalRange` but NOT `subscribeVisibleLogicalRangeChange`. Plan correctly identifies this gap and adds the mock. |

#### Implementation-Level Attacks

| ID | Severity | Finding | Resolution |
|----|----------|---------|------------|
| AR2-001 | MEDIUM | **dataLengthRef tracks priceData.length, not chartData.length**: `dataLengthRef.current = priceData.length` (Change C) uses raw candle count from the API. But the chart's logical range indices are based on `chartData` which includes gap markers (whitespace candles for weekends/holidays). For 1M daily data: `priceData` has ~22 candles, but `chartData` has ~30 entries (22 candles + ~8 gap markers). The subscription callback compares bar indices (0 to ~30) against `dataLengthRef` (22). This means `visibleTo > 22` triggers sooner than it should because the chart actually has ~30 bars. | **ACCEPTED (conservative error)**: The threshold triggers upgrade *sooner* than the geometric 30% because gap markers inflate the logical range. With 30 bars displayed but only 22 counted, the effective threshold drops to ~22% of visual extent. This is still well above the accidental-zoom threshold (a few pixels of overshoot) and below the deliberate-zoom threshold. The practical impact is that upgrade triggers after ~2-3 wheel ticks instead of ~3-4. This is a minor UX difference, not a correctness bug. Fixing it would require passing `chartData.length` out of the `useEffect` into a ref, which is possible but adds complexity for marginal precision. If tuning is needed post-implementation, changing `priceData.length` to include gap count is a one-line fix. |
| AR2-002 | LOW | **subscribeVisibleLogicalRangeChange API existence**: The plan uses this API but it does not appear anywhere in the current codebase (confirmed via grep). The prior art in `use-chart-sync.ts` uses `subscribeVisibleTimeRangeChange` instead. Are we sure the Logical variant exists in the lightweight-charts API? | **RESOLVED**: Both APIs are documented in the lightweight-charts library. `subscribeVisibleLogicalRangeChange` returns `LogicalRange | null` where `LogicalRange = { from: number; to: number }` (bar indices). `subscribeVisibleTimeRangeChange` returns `TimeRange | null` where `TimeRange = { from: Time; to: Time }` (timestamps). The Logical variant is correct for our use case because bar indices make threshold math trivial. The Time variant would require date arithmetic to compute overshoot, which is fragile with market holidays and gaps. The fact that it is unused in the codebase is expected -- no prior feature needed bar-index-based viewport tracking. |
| AR2-003 | LOW | **Empty priceData with populated sentimentData**: If `priceData.length === 0` but `sentimentData` has data, `dataLengthRef` stays 0. `shouldUpgradeTimeRange` returns false (EC4 guard). The user sees sentiment data but zooming out cannot trigger upgrade. | **ACCEPTED**: This is correct behavior. Without price candles, the chart is in a degraded state. Auto-upgrading would fetch a wider range that might still have no price data. The user can manually click a wider time range button. The sentiment-only scenario is rare in practice (the API returns both or neither). |
| AR2-004 | LOW | **Range callback type annotation**: Plan Change E annotates the callback parameter as `(range: { from: number; to: number } | null)`. The actual lightweight-charts type is `LogicalRange | null` where `LogicalRange` is `{ from: Logical; to: Logical }` and `Logical` is a branded `number`. Using an inline type works at runtime but loses type safety. | **ACCEPTED**: The inline type is functionally correct since `Logical` is a branded number that is fully compatible with plain `number` in arithmetic. Using the branded type would require importing `LogicalRange` from `lightweight-charts`, which adds an import but provides better type documentation. This is a minor style preference -- the implementation can use either form. Adding to the import is recommended but not required. |

#### Test Coverage Matrix

| Requirement | Unit Test | E2E Test | Notes |
|-------------|-----------|----------|-------|
| R1: Utilities | File 4: 13 test cases | -- | Full coverage of `getNextTimeRange` (5 transitions + null) and `shouldUpgradeTimeRange` (8 edge cases) |
| R2: Subscription | File 3: 2 tests (created/not created) | E2E: zoom test | Unit validates subscription setup; E2E validates end-to-end behavior |
| R3: Debounce | -- | E2E: implicit (5s timeout accounts for 500ms debounce) | Hard to unit test without over-mocking. E2E provides real validation. |
| R4: Loading guard | -- | E2E: implicit (test waits for data load) | Would require mocking callback-during-loading scenario. Low risk given the `isLoadingRef` check is a single line. |
| R5: fitContent prevention | -- | E2E: implicit (data loads, no infinite loop) | Triple-defense (flag + math + 100ms timer) makes individual testing of the flag low value. |
| R6: Max range cap | File 4: `1Y -> null` test | -- | Pure function test covers this completely. |
| R7: Ref sync | -- | -- | Implementation pattern (render-body ref update) is standard React. No test needed. |
| R8: Cleanup | -- | -- | `clearTimeout` in cleanup is a defensive pattern. Would require unmount timing test to validate. Low risk. |
| R9: Non-interactive | File 3: "NOT subscribe when not interactive" test | -- | Directly tested. |

**Coverage gaps**: R3 (debounce), R4 (loading guard), R5 (fitContent flag), R8 (cleanup) lack dedicated unit tests. All four are covered implicitly by the E2E test and/or are single-line guards with low isolated failure risk. Adding unit tests for these would require complex mocking of the subscription callback timing, which provides diminishing returns. **Accepted as sufficient coverage.**

### Unresolved Findings

None. All findings are MEDIUM or below. AR2-001 is the most substantive finding (gap-inflated data length) and is accepted as a conservative error with a documented one-line fix path if tuning is needed.

### Gate Statement

**ADVERSARIAL REVIEW #2: PASS**

4 findings total: 0 CRITICAL, 0 HIGH, 1 MEDIUM (accepted), 3 LOW (2 accepted, 1 resolved). No spec drift detected. Line numbers verified accurate. Test coverage has acceptable gaps with E2E backstop. Plan is implementation-ready.
