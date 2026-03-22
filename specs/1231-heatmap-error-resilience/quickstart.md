# Quickstart: Heatmap Error Resilience

**Branch**: `1231-heatmap-error-resilience`

## What This Feature Does

Hardens the heatmap component against all API error states: crashes from `Object.entries(undefined)`, missing error UI for network/server failures, and untested backend partial failure behavior. After this feature, the heatmap gracefully degrades instead of crashing the dashboard.

## Implementation Order

### Step 1: Add Defensive Guards in HeatMapView

**File**: `frontend/src/components/heatmap/heat-map-view.tsx`

Guard `Object.entries(ticker.sentiment)` against non-object values:

```tsx
// BEFORE (line 34) - crashes if sentiment is undefined/null
const sentimentEntries = Object.entries(ticker.sentiment);

// AFTER - defensive guard
const sentimentEntries = Object.entries(ticker.sentiment ?? {});
```

Also add empty tickers check before the grid:

```tsx
// After heatMapData computation, before rendering the grid:
if (tickers.length === 0) {
  return <HeatMapEmptyState className={className} />;
}
```

### Step 2: Create HeatMapErrorState Component

**File**: `frontend/src/components/heatmap/heat-map-error.tsx` (NEW)

Create an error state component matching the existing `HeatMapEmptyState` pattern:

```tsx
interface HeatMapErrorStateProps {
  error: Error | null;
  onRetry?: () => void;
  className?: string;
}

export function HeatMapErrorState({ error, onRetry, className }: HeatMapErrorStateProps) {
  // Emit structured console event for Playwright (Feature 1226 pattern)
  useEffect(() => {
    if (error) {
      emitErrorEvent('heatmap:error', {
        code: error instanceof ApiClientError ? error.code : 'UNKNOWN_ERROR',
        message: error.message,
      });
    }
  }, [error]);

  return (
    <div className={cn('text-center py-12', className)}>
      <AlertTriangle className="w-12 h-12 mx-auto mb-4 text-destructive" />
      <h3>Unable to load sentiment data</h3>
      <p>{getUserFriendlyMessage(error)}</p>
      {onRetry && <Button onClick={onRetry}>Retry</Button>}
    </div>
  );
}
```

### Step 3: Add Null Guard in CompactHeatMapGrid

**File**: `frontend/src/components/heatmap/heat-map-grid.tsx`

The desktop grid has a null check for cells (line 138), but the mobile compact grid does not. Add the same guard:

```tsx
// BEFORE (line 241-249) - no null check
{row.cells.map((cell, index) => (
  <div key={index} ... style={{ backgroundColor: interpolateSentimentColor(cell.score) }} ... />
))}

// AFTER - with null guard
{row.cells.map((cell, index) => (
  cell ? (
    <div key={index} ... style={{ backgroundColor: interpolateSentimentColor(cell.score) }} ... />
  ) : (
    <div key={index} className="flex-1 h-6 rounded bg-muted/30" />
  )
))}
```

### Step 4: Export HeatMapErrorState from Index

**File**: `frontend/src/components/heatmap/index.ts`

Add export for the new error component:

```tsx
export { HeatMapErrorState } from './heat-map-error';
```

### Step 5: Write Frontend Unit Tests

**File**: `frontend/tests/unit/components/heatmap/heat-map-view.test.tsx` (NEW)

Test cases using vitest + testing-library (matching existing heat-map-cell.test.tsx patterns):

1. Renders normally with valid tickers data
2. Renders HeatMapEmptyState when tickers array is empty
3. Does not crash when ticker.sentiment is undefined
4. Does not crash when ticker.sentiment is null
5. Does not crash when ticker.sentiment is an empty object
6. Renders partial data correctly (one ticker with data, one without)
7. HeatMapErrorState renders error message and retry button
8. HeatMapErrorState emits console event (Feature 1226)

### Step 6: Write Backend Partial Failure Unit Test

**File**: `tests/unit/test_sentiment_partial_failure.py` (NEW)

Test case using pytest with moto mock:

1. Mock `query_timeseries` to succeed for "AAPL", throw `Exception` for "GOOGL"
2. Call `get_sentiment_by_configuration` with both tickers
3. Assert response is `SentimentResponse` (not error), has 2 tickers
4. Assert AAPL has non-empty sentiment, GOOGL has empty sentiment `{}`
5. Assert no exception propagated to caller

### Step 7: Verify Existing Tests Pass

Run `make test-local` and frontend tests to verify no regressions.

## Key Patterns to Follow

### Defensive Object.entries (prevent TypeError)

```tsx
// Always guard Object.entries on external data
const entries = Object.entries(value ?? {});
```

### Error Event Emission (Feature 1226)

```tsx
import { emitErrorEvent } from '@/lib/api/client';

// Emit structured event for Playwright assertions
emitErrorEvent('heatmap:error', { code: 'NETWORK_ERROR', message: '...' });
```

### React-Query Error Handling

```tsx
const { data, isError, error, refetch } = useSentiment(configId);

if (isError) {
  return <HeatMapErrorState error={error} onRetry={refetch} />;
}
if (!data || data.tickers.length === 0) {
  return <HeatMapEmptyState />;
}
return <HeatMapView tickers={data.tickers} />;
```

### Vitest Test Pattern (from existing heat-map-cell.test.tsx)

```tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

// Mock framer-motion globally in tests/setup.ts (already done)
// Mock hooks as needed
vi.mock('@/hooks/use-haptic', () => ({ useHaptic: () => ({ ... }) }));
```

## Testing Strategy

- **Frontend unit tests**: Vitest + Testing Library, mock chart store and haptic hook, test rendering with various data shapes including undefined/null/empty
- **Backend unit tests**: pytest with moto, mock `query_timeseries` to throw for specific tickers, verify partial failure returns 200 with empty sentiment
- **No integration tests needed**: This feature is purely defensive coding on existing interfaces
- **E2E consideration**: The `emitErrorEvent` calls enable future Playwright assertions but writing Playwright tests is out of scope for this feature (no page integration yet)
