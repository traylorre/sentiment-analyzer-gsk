# Implementation Plan: OHLC Pan-to-Load

**Branch**: `1101-ohlc-pan-to-load` | **Date**: 2025-12-29 | **Spec**: [spec.md](./spec.md)

## Summary

Implement bidirectional infinite scroll for OHLC chart. When user pans left (toward history), fetch older data. When user pans right (toward present), fetch newer data if available. Use lightweight-charts `subscribeVisibleLogicalRangeChange` API with `barsInLogicalRange` for edge detection.

## Technical Context

**Language/Version**: TypeScript 5.x (Next.js frontend)
**Primary Dependencies**: lightweight-charts v5.0.9, React, zustand
**Storage**: N/A (in-memory chart data)
**Testing**: Jest, React Testing Library
**Target Platform**: Modern browsers
**Project Type**: web (frontend-only change)
**Performance Goals**: Data load within 2s, no duplicate requests
**Constraints**: Maintain scroll position when prepending data

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| No external API abuse | ✅ PASS | Debounce prevents rapid requests |
| Error handling | ✅ PASS | Network failures handled gracefully |

## Project Structure

```text
frontend/
├── src/
│   ├── components/charts/
│   │   └── price-sentiment-chart.tsx  # MODIFY: Add pan listener
│   ├── hooks/
│   │   ├── use-chart-data.ts          # MODIFY: Support pagination
│   │   └── use-pan-to-load.ts         # CREATE: Pan detection hook
│   └── lib/api/
│       └── ohlc.ts                    # MODIFY: Add before/after params
└── tests/
    └── unit/hooks/
        └── use-pan-to-load.test.ts    # CREATE: Unit tests
```

## Implementation Approach

### Phase 1: Backend API Enhancement
1. Verify OHLC endpoint supports `startDate`/`endDate` params for pagination
2. Add `before` parameter to fetch data before a given date

### Phase 2: Pan Detection Hook
3. Create `use-pan-to-load.ts` hook:
   - Subscribe to `visibleLogicalRangeChange`
   - Use `barsInLogicalRange()` to detect edge proximity
   - Debounce callbacks (500ms)
   - Track `isFetching` state to prevent duplicates

### Phase 3: Data Integration
4. Modify `use-chart-data.ts`:
   - Add `loadMoreHistory(beforeDate)` function
   - Add `loadMoreRecent(afterDate)` function
   - Merge new data with existing dataset

### Phase 4: Chart Integration
5. Modify `price-sentiment-chart.tsx`:
   - Integrate pan-to-load hook
   - Handle data prepend without view jump
   - Add loading indicator (optional)

## Key APIs (lightweight-charts)

```typescript
// Edge detection
chart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
  const barsInfo = series.barsInLogicalRange(range);
  if (barsInfo.barsBefore < 50) loadMoreHistory();
  if (barsInfo.barsAfter < 50) loadMoreRecent();
});

// Data update
series.setData([...newOlderData, ...existingData]);
```

## Files to Modify

| File | Change | Description |
|------|--------|-------------|
| `frontend/src/hooks/use-pan-to-load.ts` | CREATE | Pan detection hook |
| `frontend/src/hooks/use-chart-data.ts` | MODIFY | Pagination support |
| `frontend/src/components/charts/price-sentiment-chart.tsx` | MODIFY | Integrate hook |
| `frontend/src/lib/api/ohlc.ts` | MODIFY | Add date params |
