# Feature 1316: Tasks

## Task 1: Wrap fitContent in requestAnimationFrame

- **File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
- **Lines**: 419-427
- **Status**: done
- **Depends on**: none

Replace the synchronous `fitContent()` call with a `requestAnimationFrame`-deferred version:

```typescript
// BEFORE (lines 419-427):
  // Fit content when data changes to show full selected time range
  // Removed VISIBLE_CANDLES logic - user expects to see full selected range
  // (The old logic limited intraday to ~40 candles, showing only 5-6 days for 1h resolution)
  useEffect(() => {
    if (!chartRef.current || (!priceData.length && !sentimentData.length)) return;

    // Show all data for the selected time range
    chartRef.current.timeScale().fitContent();
  }, [priceData, sentimentData, resolution, timeRange]);

// AFTER:
  // Fit content when data changes to show full selected time range
  // Removed VISIBLE_CANDLES logic - user expects to see full selected range
  // (The old logic limited intraday to ~40 candles, showing only 5-6 days for 1h resolution)
  // Feature 1316: Defer fitContent by one frame so lightweight-charts processes setData first
  useEffect(() => {
    if (!chartRef.current || (!priceData.length && !sentimentData.length)) return;

    // Show all data for the selected time range
    // requestAnimationFrame defers until after the browser paints, giving
    // lightweight-charts one frame to process the setData() from preceding useEffects
    const frameId = requestAnimationFrame(() => {
      chartRef.current?.timeScale().fitContent();
    });
    return () => cancelAnimationFrame(frameId);
  }, [priceData, sentimentData, resolution, timeRange]);
```

**Verification**: `npm run build` in frontend should succeed with no type errors.

## Task 2: Add E2E test for full-range chart data visibility

- **File**: `frontend/tests/e2e/chart-zoom-data.spec.ts` (new)
- **Status**: done
- **Depends on**: Task 1

Create a Playwright E2E test that:
1. Navigates to the dashboard
2. Searches for AMZN ticker
3. Selects 1Y time range + Day resolution
4. Waits for chart data to load
5. Asserts >= 200 candles are reported (catches the ~60 candle bug)

**Verification**: `npx playwright test chart-zoom-data` passes locally.
