# Research: Heatmap Error Resilience

**Date**: 2026-03-21
**Branch**: `1231-heatmap-error-resilience`

## Research Question 1: What Error Shapes Can the Sentiment API Return?

**Summary**: The sentiment API (`/api/v2/configurations/{id}/sentiment`) can return 4 distinct response shapes depending on where the failure occurs.

### Shape 1: Success (200 OK)

```json
{
  "config_id": "abc123",
  "tickers": [
    {
      "symbol": "AAPL",
      "sentiment": {
        "aggregated": {
          "score": 0.45,
          "label": "positive",
          "confidence": 0.8,
          "updated_at": "2026-03-21T12:00:00Z"
        }
      }
    }
  ],
  "last_updated": "2026-03-21T12:00:00Z",
  "next_refresh_at": "2026-03-21T12:05:00Z",
  "cache_status": "fresh"
}
```

### Shape 2: Success with partial data (200 OK)

When individual ticker queries fail, the response is still 200 but affected tickers have empty sentiment:

```json
{
  "config_id": "abc123",
  "tickers": [
    {"symbol": "AAPL", "sentiment": {"aggregated": {"score": 0.45, ...}}},
    {"symbol": "FAILING_TICKER", "sentiment": {}}
  ],
  ...
}
```

**Source**: `sentiment.py:332-347` -- per-ticker try/except catches exceptions and appends empty sentiment dict.

### Shape 3: Router-level error (4xx/5xx)

When auth fails, config not found, or validation fails:

```json
{"error": {"code": "CONFIG_NOT_FOUND", "message": "Configuration abc123 not found"}}
```

HTTP status varies: 400 (bad request), 401 (auth), 403 (forbidden), 404 (not found).

**Source**: `router_v2.py` helper functions `_require_user_id()`, `_get_config_with_tickers()`, `error_response()`.

### Shape 4: Network/timeout failure (no response)

The `apiClient` in `client.ts:112-177` catches network failures and throws `ApiClientError` with codes:
- `NETWORK_ERROR` (code 0) -- `TypeError` from fetch
- `TIMEOUT` (code 0) -- `AbortSignal.timeout()` triggers
- `UNKNOWN_ERROR` (code 0) -- any other exception

React-query surfaces these via `isError: true` and `error: ApiClientError`.

## Research Question 2: How Does the Frontend Currently Handle These Errors?

### API Client Layer (client.ts)

The `handleResponse` function at lines 85-110 handles non-OK responses:
- Attempts to parse JSON body as `{code, message, details}`
- If JSON parse fails, creates error with `UNKNOWN_ERROR` code and statusText
- Throws `ApiClientError` in all error cases

The `apiClient` catch block at lines 154-176 handles fetch-level errors:
- `TimeoutError` / `AbortError` -> `ApiClientError(0, 'TIMEOUT', ...)`
- `TypeError` with 'fetch' -> `ApiClientError(0, 'NETWORK_ERROR', ...)`
- Everything else -> `ApiClientError(0, 'UNKNOWN_ERROR', ...)`

### React-Query Layer (use-sentiment.ts)

The `useSentiment` hook wraps `sentimentApi.get()` with react-query. When the API call throws:
- `isError: true` is set
- `error` contains the `ApiClientError` instance
- `data` is `undefined`
- React-query automatically retries 3 times before surfacing the error

### Component Layer (heat-map-view.tsx)

Currently NO error handling exists in `HeatMapView`:
- The component accepts `tickers: TickerSentiment[]` as a prop
- It calls `Object.entries(ticker.sentiment)` at line 34
- There is no error/loading prop beyond `isLoading?: boolean`
- There is no error boundary wrapping the component
- The `HeatMapEmptyState` component exists but is only exported, never conditionally rendered based on error state

**Gap**: The component trusts that `tickers` is always a valid array of properly-shaped objects. If the parent passes `undefined` or the API response has unexpected shape, the component crashes.

## Research Question 3: What Does the Frontend Currently Do When `tickers` is Empty?

When `tickers` is an empty array `[]`:
- The `useMemo` at line 31-71 produces `matrix: []` (empty array)
- The `HeatMapGrid` renders an empty `<tbody>` with headers but no data rows
- There is no explicit empty state check -- the grid just shows column headers with no rows
- The `HeatMapEmptyState` component at line 168-180 is defined but never used by any caller

**Improvement opportunity**: Check `tickers.length === 0` and render `HeatMapEmptyState` instead of an empty grid.

## Research Question 4: What Defensive Patterns Already Exist in the Codebase?

### Pattern 1: Null check in HeatMapGrid (desktop)

At `heat-map-grid.tsx:138`:
```tsx
{cell ? (
  <HeatMapCell data={cell} ... />
) : (
  <HeatMapEmptyCell />
)}
```

This guards against undefined cells in the cells array. The mobile `CompactHeatMapGrid` at line 241-249 does NOT have this guard.

### Pattern 2: Empty cells fallback in HeatMapView

At `heat-map-view.tsx:46-48`:
```tsx
if (cells.length === 0) {
  cells.push({ source: 'aggregated' as SentimentSource, score: 0, color: '' });
}
```

This produces a neutral cell when a ticker has no sentiment sources. But it only runs if `Object.entries(ticker.sentiment)` succeeds (i.e., sentiment is an object).

### Pattern 3: ApiClientError emission (Feature 1226)

At `client.ts:37-43`:
```tsx
export function emitErrorEvent(event: string, details: Record<string, unknown> = {}) {
  console.warn(JSON.stringify({ event, timestamp, details }));
}
```

This is used by other components for Playwright test assertions. The heatmap should use this pattern for error observability.

### Pattern 4: Error banner pattern (api-health-banner)

The `ApiHealthBanner` component in `components/api-health-banner.tsx` shows a banner when API health degrades. This pattern (conditional banner with retry) can be adapted for heatmap error state.

## Research Question 5: Backend Partial Failure Behavior -- Is It Tested?

**Finding**: The per-ticker try/except at `sentiment.py:332-340` is NOT explicitly tested. The existing unit tests in `test_sentiment.py` and `test_sentiment_overview.py` test the happy path (all tickers succeed) and empty data (no timeseries buckets), but none inject an exception into `query_timeseries` for a specific ticker while others succeed.

**Risk**: Without a test, a future refactor could accidentally remove the try/except, causing the entire endpoint to 500 when any single ticker fails. This would be a regression from the current graceful degradation behavior.

**Recommendation**: Add a focused unit test that mocks `query_timeseries` to throw for one ticker and verifies the response still contains all tickers with the failed one having `sentiment: {}`.
