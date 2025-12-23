# Feature Specification: OHLC Time Resolution Selector

**Feature Branch**: `1035-ohlc-resolution-selector`
**Created**: 2025-12-23
**Status**: Draft
**Input**: User description: "OHLC Time Bucket Selection - Make ONE demo-able URL that displays OHLC tickers with selectable time buckets (1min, 5min, 10min, 1h, etc.). BACKEND: Add resolution param to GET /api/v2/tickers/{ticker}/ohlc endpoint, use Finnhub intraday resolution. FRONTEND: Add resolution selector UI in PriceSentimentChart, update useChartData hook."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Intraday Price Candles (Priority: P1)

As a trader viewing a ticker chart, I want to select different time resolutions (1 minute, 5 minutes, 1 hour, etc.) so that I can analyze price movements at the granularity appropriate for my trading style.

**Why this priority**: This is the core value proposition - enabling users to view OHLC candlestick data at different time granularities. Without this, the feature has no utility. This single capability makes the dashboard demo-able.

**Independent Test**: Can be fully tested by loading the chart page for any ticker (e.g., AAPL), selecting different resolutions from the dropdown, and verifying candles update to show the appropriate time buckets. Delivers immediate value for intraday price analysis.

**Acceptance Scenarios**:

1. **Given** a user is viewing the OHLC chart for ticker AAPL, **When** the user selects "5 min" from the resolution dropdown, **Then** the chart displays 5-minute candlesticks for the selected time range
2. **Given** a user is viewing 1-hour candles, **When** the user switches to "1 min" resolution, **Then** the chart reloads with 1-minute candlesticks and the time axis adjusts accordingly
3. **Given** a user selects a resolution, **When** the data loads, **Then** a loading indicator appears during the transition and disappears when data is rendered

---

### User Story 2 - Remember Resolution Preference (Priority: P2)

As a returning user, I want the chart to remember my last-selected resolution so that I don't have to re-select it every time I view a different ticker.

**Why this priority**: Improves user experience by reducing repetitive actions. Not essential for demo but enhances usability for repeated use.

**Independent Test**: Can be tested by selecting a resolution, navigating to a different ticker, and verifying the same resolution is pre-selected.

**Acceptance Scenarios**:

1. **Given** a user selects "15 min" resolution for AAPL, **When** the user navigates to view MSFT, **Then** the chart defaults to "15 min" resolution
2. **Given** a user closes and reopens the browser within the same session, **When** the user returns to the chart, **Then** their last-selected resolution is preserved

---

### User Story 3 - Synchronized Sentiment and Price Time Axes (Priority: P3)

As a user viewing both price candles and sentiment data, I want the time axes to be synchronized so that I can correlate price movements with sentiment changes at the same time scale.

**Why this priority**: Enhances analytical value by enabling cross-referencing of price and sentiment data. Depends on P1 being complete.

**Independent Test**: Can be tested by enabling both price candles and sentiment overlay, selecting a resolution, and verifying both datasets align on the same time axis.

**Acceptance Scenarios**:

1. **Given** a user has both price candles and sentiment line enabled, **When** the user hovers over a specific candle, **Then** the tooltip shows both OHLC values and the sentiment score for that time period
2. **Given** the user changes resolution from 1h to 5m, **When** both layers are visible, **Then** both price and sentiment data update to 5-minute granularity

---

### Edge Cases

- What happens when intraday data is not available (e.g., market closed, weekend)? The system displays the most recent available data with a clear indicator of the data freshness.
- What happens when the user requests a resolution the data provider doesn't support? The system falls back to the nearest available resolution and notifies the user.
- How does the system handle very large date ranges at 1-minute resolution? The system limits data points to a reasonable maximum (e.g., last 7 days for 1-minute data) and communicates this to the user.
- What happens during market hours when real-time data streams? The chart auto-updates with new candles as they complete, without full page refresh.
- How does the system handle tickers with no intraday data (e.g., mutual funds, bonds)? The resolution selector is disabled or hidden, defaulting to daily view with explanation.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST display a resolution selector control on the OHLC chart allowing users to choose from: 1 min, 5 min, 15 min, 30 min, 1 hour, and Daily
- **FR-002**: System MUST fetch and render OHLC candlestick data at the user-selected resolution
- **FR-003**: System MUST show a loading indicator while fetching data for a new resolution
- **FR-004**: System MUST handle data provider failures gracefully by showing an error message without crashing the chart
- **FR-005**: System MUST preserve the user's resolution preference within the browser session
- **FR-006**: System MUST auto-limit the time range based on resolution (e.g., 1-min data limited to recent 7 days to prevent excessive data loading)
- **FR-007**: System MUST display appropriate messaging when requested resolution is unavailable for a ticker
- **FR-008**: System MUST synchronize the time axis between OHLC candles and sentiment overlay when both are visible
- **FR-009**: System MUST support the existing time range controls (1W, 1M, 3M, 6M, 1Y) in combination with resolution selection

### Key Entities

- **OHLC Candle**: A single candlestick data point containing open, high, low, close prices and volume for a specific time bucket
- **Resolution**: The time duration each candle represents (1 min, 5 min, 15 min, 30 min, 1 hour, daily)
- **Time Range**: The overall period of data displayed (1 week, 1 month, etc.)
- **User Preference**: Session-stored setting for default resolution

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can switch between at least 5 different time resolutions and see updated chart data within 3 seconds
- **SC-002**: Chart renders correctly for all supported resolutions without visual artifacts or data gaps
- **SC-003**: The feature works for at least 95% of US-listed equity tickers
- **SC-004**: Page remains responsive (no freezing) when loading large datasets (up to 5000 candles)
- **SC-005**: A first-time user can discover and use the resolution selector within 10 seconds of viewing the chart (intuitive placement)
- **SC-006**: The feature provides a complete demo experience - a single URL that showcases real-time OHLC data with time bucket selection

## Assumptions

- Intraday OHLC data is available from the current data provider (Finnhub) at the required resolutions
- The existing chart library supports rendering candlesticks at sub-daily resolutions
- Session storage is an acceptable mechanism for preference persistence (not requiring server-side storage)
- Market data delays (15-minute delay for free tier) are acceptable for demo purposes
- The existing sentiment timeseries infrastructure can provide data at matching resolutions for synchronization
