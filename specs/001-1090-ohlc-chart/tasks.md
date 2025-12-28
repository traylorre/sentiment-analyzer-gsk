# Tasks: OHLC Chart Time Axis Fixes

**Branch**: `001-1090-ohlc-chart` | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

## Task Breakdown

### T001: Add resolution prop and time conversion helper

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Small
**Dependencies**: None

**Implementation**:
1. Add `resolution: OHLCResolution` to component props interface
2. Add import for `OHLCResolution` from `@/types/chart`
3. Create `convertToChartTime` helper function at top of file:
   - For 'D' resolution: extract YYYY-MM-DD from ISO string
   - For intraday: convert to Unix timestamp (seconds)

**Acceptance**:
- [ ] Component accepts resolution prop
- [ ] Helper function handles both daily and intraday formats

---

### T002: Update candlestick and sentiment data mapping

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Small
**Dependencies**: T001

**Implementation**:
1. Update candlestick data mapping (~line 262-268):
   - Change `time: candle.date as Time` to `time: convertToChartTime(candle.date, resolution)`
2. Update sentiment data mapping (~line 277-280):
   - Change `time: point.date as Time` to `time: convertToChartTime(point.date, resolution)`

**Acceptance**:
- [ ] Candlestick data uses converted time values
- [ ] Sentiment data uses converted time values

---

### T003: Fix crosshair handler time type detection

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Small
**Dependencies**: T001

**Implementation**:
1. In crosshair move handler (~line 212), replace:
   ```typescript
   // Old: (param.time as number) * 1000
   // New:
   const timestamp = typeof param.time === 'number'
     ? param.time * 1000
     : new Date(param.time as string).getTime();
   ```
2. Use `timestamp` for Date construction in tooltip

**Acceptance**:
- [ ] No console error on daily resolution hover
- [ ] No console error on intraday resolution hover

---

### T004: Add resolution-aware date formatter

**File**: `frontend/src/lib/utils/format.ts`
**Effort**: Small
**Dependencies**: None

**Implementation**:
1. Add import for `Time` from lightweight-charts
2. Add import for `OHLCResolution` from `@/types/chart`
3. Add `formatChartDate` function:
   ```typescript
   export function formatChartDate(time: Time, resolution: OHLCResolution): string {
     const date = typeof time === 'number'
       ? new Date(time * 1000)
       : new Date(time as string);

     if (resolution === 'D') {
       return date.toLocaleDateString('en-US', {
         weekday: 'short', month: 'short', day: 'numeric'
       });
     }
     return date.toLocaleDateString('en-US', {
       weekday: 'short', month: 'numeric', day: 'numeric',
       hour: 'numeric', minute: '2-digit'
     });
   }
   ```

**Acceptance**:
- [ ] Daily format: "Mon Dec 23"
- [ ] Intraday format: "Mon 12/23 2:00 PM"

---

### T005: Update tooltip to use resolution-aware formatter

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Small
**Dependencies**: T003, T004

**Implementation**:
1. Import `formatChartDate` from `@/lib/utils/format`
2. In crosshair handler, replace `formatDateTime` call with:
   ```typescript
   date: formatChartDate(param.time, resolution),
   ```

**Acceptance**:
- [ ] Tooltip shows resolution-appropriate date format

---

### T006: Add visible range setting for intraday

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Medium
**Dependencies**: T001, T002

**Implementation**:
1. Define visible candle counts at module level:
   ```typescript
   const VISIBLE_CANDLES: Record<OHLCResolution, number> = {
     '1': 120,   // 2 hours
     '5': 78,    // 1 trading day
     '15': 52,   // 2 trading days
     '30': 26,   // 2 trading days
     '60': 40,   // 5 trading days
     'D': 0,     // Show all
   };
   ```
2. In the `fitContent` useEffect (~line 286-290), after `fitContent()`:
   ```typescript
   const visibleCount = VISIBLE_CANDLES[resolution];
   if (visibleCount > 0 && priceData.length > visibleCount) {
     chartRef.current.timeScale().setVisibleLogicalRange({
       from: priceData.length - visibleCount,
       to: priceData.length - 1,
     });
   }
   ```
3. Add `resolution` to useEffect dependency array

**Acceptance**:
- [ ] 1m shows ~120 candles initially
- [ ] 5m shows ~78 candles initially
- [ ] Day shows all candles (fitContent behavior)

---

### T007: Verify and fix panning configuration

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Effort**: Small
**Dependencies**: None

**Implementation**:
1. Check current `handleScroll` setting (~line 147)
2. If `handleScroll: interactive`, verify it enables `pressedMouseMove`
3. If panning still doesn't work, replace with explicit config:
   ```typescript
   handleScroll: {
     mouseWheel: true,
     pressedMouseMove: true,
     horzTouchDrag: true,
     vertTouchDrag: false,
   },
   ```
4. Check for CSS that might block drag events on chart container
5. Verify no parent element has `overflow: hidden` cutting off drag

**Acceptance**:
- [ ] Horizontal drag pans chart left/right
- [ ] Pan stops at data boundaries

---

### T008: Wire resolution prop from parent

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx` (check usage)
**File**: `frontend/src/hooks/use-chart-data.ts` or parent page
**Effort**: Small
**Dependencies**: T001

**Implementation**:
1. Find where `PriceSentimentChart` is used
2. Pass `resolution` prop from parent state/hook
3. Verify resolution value matches expected OHLCResolution type

**Acceptance**:
- [ ] Resolution prop flows from selector to chart component

---

### T009: Add unit tests for time conversion

**File**: `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`
**Effort**: Medium
**Dependencies**: T001, T004

**Implementation**:
1. Export `convertToChartTime` for testing (or test via component)
2. Add tests:
   - T090: Intraday resolution returns Unix timestamp
   - T091: Daily resolution returns YYYY-MM-DD string
   - T092: `formatChartDate` with numeric time (intraday)
   - T093: `formatChartDate` with string time (daily)
   - T094: Intraday format includes time
   - T095: Daily format omits time

**Acceptance**:
- [ ] All 6 unit tests pass
- [ ] Tests cover edge cases (midnight, year boundary)

---

## Task Summary

| Task | Description | Effort | Status |
|------|-------------|--------|--------|
| T001 | Add resolution prop and conversion helper | Small | Pending |
| T002 | Update data mapping to use converter | Small | Pending |
| T003 | Fix crosshair time type detection | Small | Pending |
| T004 | Add resolution-aware date formatter | Small | Pending |
| T005 | Update tooltip formatter | Small | Pending |
| T006 | Add visible range for intraday | Medium | Pending |
| T007 | Verify/fix panning configuration | Small | Pending |
| T008 | Wire resolution prop from parent | Small | Pending |
| T009 | Add unit tests | Medium | Pending |

**Total Effort**: ~4-6 hours
**Critical Path**: T001 → T002 → T006 (visible range depends on proper time conversion)
