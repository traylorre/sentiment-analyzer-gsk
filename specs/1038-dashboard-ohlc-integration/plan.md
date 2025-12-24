# Plan: Dashboard OHLC Integration

**Feature ID**: 1038
**Spec**: spec.md

## Implementation Strategy

This is a **frontend-only integration** of existing components. No new backend work required.

### Phase 1: Prepare Dashboard Page

**Goal**: Update imports and remove mock data

1. Update imports in `frontend/src/app/(dashboard)/page.tsx`:
   - Add: `import { PriceSentimentChart } from '@/components/charts'`
   - Remove: `SentimentChart` dynamic import

2. Remove mock data:
   - Delete `generateMockData` function
   - Remove `SentimentTimeSeries` type import if unused

3. Simplify state:
   - Keep `activeTicker` for current selection
   - Remove `tickers` array with embedded `data` (chart fetches its own data)

### Phase 2: Integrate PriceSentimentChart

**Goal**: Replace SentimentChart with PriceSentimentChart

1. Replace chart component usage:
   ```tsx
   // Before
   <SentimentChart data={activeTickerData.data} ticker={...} />

   // After
   <PriceSentimentChart ticker={activeTicker} />
   ```

2. PriceSentimentChart handles internally:
   - API data fetching via `useChartData` hook
   - Resolution selector UI
   - Time range selector
   - Loading states
   - Error handling

### Phase 3: Maintain Ticker Chips (Optional)

**Goal**: Keep multi-ticker chip functionality if desired

1. TickerChipList can remain for quick ticker switching
2. Active chip triggers `setActiveTicker`
3. Chart re-fetches data for new ticker automatically

### Phase 4: Unit Tests

**Goal**: Verify integration works

1. Test that PriceSentimentChart renders when ticker selected
2. Test resolution selector is visible
3. Test ticker switching updates chart

## File Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/app/(dashboard)/page.tsx` | Modify | Replace SentimentChart with PriceSentimentChart |
| `frontend/src/__tests__/app/dashboard.test.tsx` | Create | Integration tests |

## Execution Sequence

```
T001: Update imports → T002: Remove mock data → T003: Replace chart component →
T004: Test manually → T005: Add unit tests → T006: Run make validate
```

## Rollback Plan

If issues arise:
- Revert `page.tsx` to use SentimentChart with mock data
- No backend changes to rollback
