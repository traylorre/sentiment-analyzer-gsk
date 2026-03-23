# Feature Specification: Heatmap Error Resilience

**Feature Branch**: `1231-heatmap-error-resilience`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Ensure the heatmap gracefully handles all error states from the sentiment API: empty data, error responses, network failures, and partial data (some tickers have data, others don't)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Frontend Gracefully Handles All API Error States (Priority: P1)

A user opens their dashboard and views the sentiment heatmap. If the sentiment API returns an error response (500, network timeout, malformed JSON), the heatmap displays a meaningful empty/error state instead of crashing with an unhandled exception. The user can see which tickers failed and retry.

**Why this priority**: This is the user-facing crash bug. The frontend `heat-map-view.tsx` calls `Object.entries(ticker.sentiment)` which throws a TypeError if `ticker.sentiment` is undefined, null, or a non-object (e.g., when the API returns an error shape `{error: {code, message}}` instead of the expected `{tickers: [{symbol, sentiment: {...}}]}` shape). This crashes the entire dashboard, not just the heatmap.

**Independent Test**: Can be fully tested by simulating API error responses (500, timeout, malformed) in the frontend test harness and verifying the heatmap renders an error state instead of throwing.

**Acceptance Scenarios**:

1. **Given** the sentiment API returns a 500 Internal Server Error, **When** the heatmap component receives the error via react-query, **Then** the heatmap displays an error banner with a retry button and does not crash.
2. **Given** the sentiment API request times out (no response within the configured timeout), **When** the heatmap component receives a TIMEOUT error, **Then** the heatmap displays a "Connection timed out" message with a retry option.
3. **Given** the sentiment API returns a 200 OK with an unexpected body shape (e.g., `{error: {code: "DB_ERROR", message: "Database error"}}`), **When** the frontend attempts to render the heatmap, **Then** the component treats the response as empty data (zero tickers) rather than crashing on property access.
4. **Given** the sentiment API returns valid data but with an empty `tickers` array, **When** the heatmap renders, **Then** the `HeatMapEmptyState` component is shown with the "No sentiment data" message.

---

### User Story 2 - Backend Returns Consistent Error Shapes (Priority: P2)

When the sentiment API encounters failures (DynamoDB errors, individual ticker query failures), it returns a well-structured response that the frontend can predictably handle. Partial successes (some tickers have data, others failed) are represented as a successful response with empty sentiment for the failed tickers, not as a top-level error.

**Why this priority**: The backend already handles most error cases correctly (per-ticker try/except in `get_sentiment_by_configuration` catches individual failures and returns empty sentiment dicts). However, the router endpoint at `/api/v2/configurations/{id}/sentiment` can still return error shapes from `_require_user_id` and `_get_config_with_tickers` that bypass the sentinel response model. This story ensures the backend contract is fully documented and the frontend knows every possible response shape.

**Independent Test**: Can be tested by injecting failures into `query_timeseries` for specific tickers and verifying the response still has `tickers` array with empty sentiment for failed tickers. Can also test router-level errors return the standard `{error: {code, message}}` shape.

**Acceptance Scenarios**:

1. **Given** a configuration with tickers ["AAPL", "GOOGL"] where AAPL's timeseries query fails with an exception, **When** the user requests sentiment data, **Then** the response is 200 OK with AAPL having `sentiment: {}` (empty) and GOOGL having real data.
2. **Given** a request with an expired or missing auth token, **When** the sentiment endpoint is called, **Then** the response is `{error: {code: "...", message: "..."}}` with appropriate HTTP status (401/403).
3. **Given** a configuration ID that does not exist, **When** the sentiment endpoint is called, **Then** the response is 404 with `{error: {code: "CONFIG_NOT_FOUND", message: "..."}}`.

---

### Edge Cases

- What happens when `ticker.sentiment` is undefined or null in the frontend data model? The `HeatMapView` component treats it as an empty object (`{}`), producing a single empty "aggregated" cell for that ticker. This is the existing fallback behavior at line 46 (`if (cells.length === 0)`), but only runs when `Object.entries()` succeeds -- it fails if sentiment is not an object.
- What happens when the network is completely offline? The `ApiClientError` with code `NETWORK_ERROR` is thrown by `client.ts:167-168`. React-query's `isError` flag triggers, and the heatmap shows the error state.
- What happens when the response is 200 but the JSON is malformed? The `handleResponse` in `client.ts:109` calls `response.json()` which throws, caught by the apiClient try/catch as `UNKNOWN_ERROR`.
- What happens when some tickers have data and others don't (partial data)? The backend already handles this: per-ticker try/except in `get_sentiment_by_configuration` (line 332-340) catches failures and appends `TickerSentimentData(symbol=symbol, sentiment={})`. The frontend's existing empty-cell fallback (line 46-48 in heat-map-view.tsx) renders these as neutral cells.
- What happens when the API returns an HTML error page instead of JSON? The `handleResponse` JSON parse fails, falls into the catch block, and creates an `ApiError` with code `UNKNOWN_ERROR` and the statusText as message.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `HeatMapView` component MUST NOT crash when `ticker.sentiment` is undefined, null, or a non-object type. It MUST treat any non-object value as equivalent to an empty sentiment dict `{}`.
- **FR-002**: The `HeatMapView` component MUST display a user-visible error state (error banner or message) when the sentiment API request fails, distinguishing between network errors, timeouts, and server errors.
- **FR-003**: The error state MUST include a retry mechanism (button or automatic retry via react-query) that allows the user to re-fetch sentiment data without navigating away.
- **FR-004**: When the `tickers` array is empty or all tickers have empty sentiment, the `HeatMapEmptyState` component MUST be rendered instead of an empty grid.
- **FR-005**: The parent component that passes `tickers` to `HeatMapView` MUST guard against the case where `useSentiment` returns error state, by passing an empty array and rendering the error UI separately.
- **FR-006**: The backend sentiment endpoint MUST continue to return 200 with partial data when individual ticker queries fail, not escalate to a 500 error. This behavior already exists but MUST be preserved and tested.
- **FR-007**: The `CompactHeatMapGrid` (mobile) MUST apply the same defensive checks as the desktop `HeatMapGrid`, specifically guarding `cell.score` access against undefined cells.
- **FR-008**: Error console events MUST be emitted (via `emitErrorEvent` from `client.ts`) when the heatmap enters an error state, enabling Playwright test assertions per Feature 1226 pattern.

### Key Entities

- **TickerSentiment**: Frontend type representing a single ticker's sentiment data. Has `symbol: string` and `sentiment: Record<string, SentimentScore>`. The `sentiment` field can be empty `{}` for tickers with no data or failed queries.
- **SentimentData**: Frontend type representing the full API response. Has `tickers: TickerSentiment[]` among other fields. When the API returns an error shape, this type is not populated and react-query surfaces an error instead.
- **HeatMapData**: Derived data structure computed in `HeatMapView.useMemo()` from `TickerSentiment[]`. The transformation is the crash point when input data is malformed.
- **ApiClientError**: Error class from `client.ts` representing API failures with typed error codes (NETWORK_ERROR, TIMEOUT, SERVER_ERROR, etc.).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero frontend crashes (unhandled exceptions) when any of these API states occur: 500 error, timeout, network failure, empty tickers, malformed response, partial data. Verified by frontend unit tests covering all 6 scenarios.
- **SC-002**: The heatmap error state is visible to the user within 500ms of the error occurring (no blank screen or infinite spinner). Verified by Playwright test measuring time-to-error-state.
- **SC-003**: The retry mechanism successfully re-fetches data and transitions from error state to data state when the API recovers. Verified by a test that simulates failure then success.
- **SC-004**: Backend integration tests confirm partial-failure behavior: when 1 of 3 tickers fails, the response is still 200 OK with 3 tickers (2 with data, 1 with empty sentiment). Verified by unit test with mocked `query_timeseries` throwing for one ticker.
- **SC-005**: All existing heatmap unit tests continue to pass after the defensive changes. Zero regressions.

## Assumptions

- The `useSentiment` hook from `hooks/use-sentiment.ts` is the sole data source for the heatmap's `tickers` prop. There is no SSE or WebSocket push path for sentiment overview data currently.
- React-query (TanStack Query) handles retry logic automatically (default 3 retries). The retry mechanism in FR-003 leverages react-query's `refetch()` rather than custom retry logic.
- The backend `get_sentiment_by_configuration` function's per-ticker try/except pattern (line 332-340) is the correct and intentional behavior for partial failures. No changes needed to this function.
- The `emitErrorEvent` function from Feature 1226 is the established pattern for error observability and is already imported/available in the frontend.
