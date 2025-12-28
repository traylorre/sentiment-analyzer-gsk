# Implementation Plan: OHLC Chart Time Axis Fixes

**Branch**: `001-1090-ohlc-chart` | **Date**: 2025-12-28 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-1090-ohlc-chart/spec.md`

## Summary

Fix 6 interrelated OHLC chart issues all stemming from improper time type handling in the frontend chart component. The core problem is that `price-sentiment-chart.tsx` passes ISO date strings directly to lightweight-charts without proper conversion:
- Intraday resolutions (1m, 5m, 1h) need Unix timestamps (seconds)
- Daily resolution needs "YYYY-MM-DD" strings
- Tooltip/crosshair handler assumes numeric time, fails on daily string dates
- No resolution-aware visible range setting causes 1m/5m to be invisible

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: lightweight-charts v5.0.9, React 18
**Storage**: N/A (frontend-only changes)
**Testing**: Vitest with @testing-library/react
**Target Platform**: Modern browsers (Chrome, Firefox, Safari, Edge)
**Project Type**: Web application (frontend only for this feature)
**Performance Goals**: Chart renders < 100ms, smooth 60fps pan/zoom
**Constraints**: No backend changes, must support all 6 resolutions
**Scale/Scope**: Single component fix affecting ~100 lines

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] No new dependencies required
- [x] Single component modification (price-sentiment-chart.tsx + format.ts)
- [x] No infrastructure changes
- [x] No new API endpoints
- [x] Existing test patterns apply

## Project Structure

### Documentation (this feature)

```text
specs/001-1090-ohlc-chart/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
└── tasks.md             # Task breakdown (next step)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   └── charts/
│   │       └── price-sentiment-chart.tsx  # PRIMARY: Time conversion, visible range
│   ├── lib/
│   │   └── utils/
│   │       └── format.ts                  # SECONDARY: Resolution-aware date formatting
│   ├── hooks/
│   │   └── use-chart-data.ts              # MINOR: Pass resolution to chart
│   └── types/
│       └── chart.ts                       # Reference only (no changes)
└── tests/
    └── unit/
        └── components/
            └── charts/
                └── price-sentiment-chart.test.tsx  # Add time conversion tests
```

**Structure Decision**: Frontend-only modification. Web application pattern with existing test structure.

## Complexity Tracking

No constitution violations. Single-component fix with utility helper.

## Implementation Phases

### Phase 1: Time Type Conversion (FR-001, FR-002)

**Goal**: Convert ISO strings to proper lightweight-charts Time types based on resolution.

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`

**Changes**:
1. Add `resolution` prop to component interface
2. Create helper function:
   ```typescript
   function convertToChartTime(dateStr: string, resolution: OHLCResolution): Time {
     if (resolution === 'D') {
       // Daily: return YYYY-MM-DD string
       return dateStr.split('T')[0] as Time;
     }
     // Intraday: return Unix timestamp in seconds
     return Math.floor(new Date(dateStr).getTime() / 1000) as Time;
   }
   ```
3. Update candlestick data mapping (line 262-268):
   ```typescript
   time: convertToChartTime(candle.date, resolution),
   ```
4. Update sentiment data mapping (line 277-280):
   ```typescript
   time: convertToChartTime(point.date, resolution),
   ```

### Phase 2: Tooltip/Crosshair Fix (FR-004, FR-006)

**Goal**: Handle both string and numeric Time types in crosshair handler without errors.

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`

**Changes**:
1. Fix line 212 crosshair handler:
   ```typescript
   // Before: (param.time as number) * 1000 - fails for strings
   // After:
   const timestamp = typeof param.time === 'number'
     ? param.time * 1000
     : new Date(param.time as string).getTime();
   ```
2. Update tooltip date format based on resolution:
   ```typescript
   const tooltipDate = formatChartDate(param.time, resolution);
   ```

**File**: `frontend/src/lib/utils/format.ts`

**Add function**:
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

### Phase 3: Visible Range for Intraday (FR-003)

**Goal**: Set appropriate initial visible range so 1m/5m candlesticks are visible.

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`

**Changes**:
1. After `fitContent()` call (line 288), add resolution-aware range:
   ```typescript
   const VISIBLE_CANDLES: Record<OHLCResolution, number> = {
     '1': 120,   // 2 hours of 1-min candles
     '5': 78,    // 1 trading day of 5-min candles
     '15': 52,   // 2 trading days
     '30': 26,   // 2 trading days
     '60': 40,   // 5 trading days
     'D': 0,     // Show all (fitContent)
   };

   const visibleCount = VISIBLE_CANDLES[resolution];
   if (visibleCount > 0 && chartData.length > visibleCount) {
     const fromIndex = chartData.length - visibleCount;
     chart.timeScale().setVisibleLogicalRange({
       from: fromIndex,
       to: chartData.length - 1,
     });
   }
   ```

### Phase 4: Panning Verification (FR-005)

**Goal**: Ensure horizontal panning works.

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`

**Investigation**:
- Current code (line 147): `handleScroll: interactive` - should enable panning
- Verify no conflicting CSS (overflow: hidden, pointer-events: none)
- Verify no event.preventDefault() on drag events

**Changes** (if needed):
```typescript
handleScroll: {
  mouseWheel: true,
  pressedMouseMove: true,
  horzTouchDrag: true,
  vertTouchDrag: false,
},
```

### Phase 5: Wire Resolution Prop

**File**: `frontend/src/hooks/use-chart-data.ts` or parent component

**Changes**:
- Ensure resolution is passed from hook/parent to `PriceSentimentChart` component
- Check existing props - resolution may already be available

## Test Strategy

### Unit Tests (Vitest)

**File**: `frontend/tests/unit/components/charts/price-sentiment-chart.test.tsx`

1. **T090**: `convertToChartTime` returns Unix timestamp for intraday resolutions
2. **T091**: `convertToChartTime` returns YYYY-MM-DD string for daily resolution
3. **T092**: Tooltip handles numeric Time without error
4. **T093**: Tooltip handles string Time without error
5. **T094**: `formatChartDate` formats intraday with weekday+time
6. **T095**: `formatChartDate` formats daily with weekday+date only

### Manual Verification

Per SC-001 through SC-005:
- [ ] 1h resolution: No gaps, proper hour labels
- [ ] 5m resolution: Candlesticks visible, ~78 shown initially
- [ ] 1m resolution: Candlesticks visible, ~120 shown initially
- [ ] Day resolution: Mon-Fri labels, all candles visible
- [ ] Double-click zoom reset: No console errors
- [ ] Horizontal pan: Works in both directions

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Timezone issues with UTC timestamps | Use UTC consistently; test across timezones |
| Performance regression with many candles | setVisibleLogicalRange limits initial render |
| Breaking existing daily chart behavior | Daily keeps string format (unchanged) |

## Rollback Plan

Single PR with isolated frontend changes. Revert PR if issues detected.
