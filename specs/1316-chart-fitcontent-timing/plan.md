# Feature 1316: Implementation Plan

## Architecture Decision

**Approach**: Minimal surgical fix -- wrap the existing `fitContent()` call in
`requestAnimationFrame` with proper cleanup. No architectural changes required.

**Why not useLayoutEffect?** `useLayoutEffect` fires synchronously after DOM mutations but
before paint. However, the issue isn't about DOM timing -- it's about lightweight-charts'
internal data processing pipeline needing a paint frame after `setData()`. `useLayoutEffect`
would still fire before the chart processes the data, so it would not fix the bug.

**Why not combine all setData + fitContent into one useEffect?** The candle data and sentiment
data have different dependency arrays (`[priceData, resolution]` vs `[sentimentData,
resolution]`). Combining them would cause unnecessary re-renders and complicate the gap-filling
logic. The `requestAnimationFrame` approach is the minimal change with the correct semantics.

## Implementation Steps

### Step 1: Fix fitContent Timing (price-sentiment-chart.tsx)

**File**: `frontend/src/components/charts/price-sentiment-chart.tsx`
**Lines**: 419-427 (the fitContent useEffect)

**Current code:**
```typescript
useEffect(() => {
    if (!chartRef.current || (!priceData.length && !sentimentData.length)) return;
    chartRef.current.timeScale().fitContent();
}, [priceData, sentimentData, resolution, timeRange]);
```

**New code:**
```typescript
useEffect(() => {
    if (!chartRef.current || (!priceData.length && !sentimentData.length)) return;
    const frameId = requestAnimationFrame(() => {
        chartRef.current?.timeScale().fitContent();
    });
    return () => cancelAnimationFrame(frameId);
}, [priceData, sentimentData, resolution, timeRange]);
```

**Key details:**
- `requestAnimationFrame` defers `fitContent()` by one paint frame
- Optional chaining `?.` inside the callback guards against chart removal during the frame
- `cancelAnimationFrame(frameId)` in cleanup prevents stale calls on unmount or dep change

### Step 2: Add E2E Test (chart-zoom-data.spec.ts)

**File**: `frontend/tests/e2e/chart-zoom-data.spec.ts` (new)

**Test plan:**
1. Mock auth endpoint for anonymous access
2. Navigate to dashboard
3. Search for "AMZN" ticker
4. Click AMZN suggestion
5. Select 1Y time range button
6. Select Day resolution button
7. Wait for chart data to load via aria-label assertion
8. Extract candle count from aria-label
9. Assert count >= 200

**Why AMZN?** It's a well-known, highly liquid ticker that will have complete daily data for
any 1-year window. Existing tests use GOOG/AAPL, so this adds coverage diversity.

**Why >= 200?** A full year has ~252 trading days. Accounting for holidays, data gaps, and
varying API sources, 200 is a conservative lower bound that still catches the bug (which
shows only ~60 candles).

## Dependency Graph

```
Step 1 (fix) ──> Step 2 (test)
```

Step 2 validates Step 1. No other dependencies.

## Rollback Plan

Revert the `requestAnimationFrame` wrapper back to the synchronous `fitContent()` call.
The existing behavior (showing ~60 candles for 1Y) would resume. No data loss possible.
