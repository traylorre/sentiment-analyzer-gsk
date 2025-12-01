# Feature Specification: Price-Sentiment Overlay Chart

**Feature Branch**: `011-price-sentiment-overlay`
**Created**: 2025-12-01
**Status**: Draft
**Input**: User description: "Add OHLC price time series endpoint and dual-axis chart combining price candles with sentiment line overlay"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Price and Sentiment Together (Priority: P1)

As an investor using the sentiment analyzer dashboard, I want to see stock price movements alongside sentiment data on a single chart so that I can identify correlations between news sentiment and price action, helping me make more informed trading decisions.

**Why this priority**: This is the core value proposition - users currently see sentiment in isolation. Combining price and sentiment on one chart enables pattern recognition that drives investment decisions. Without this, sentiment data lacks actionable context.

**Independent Test**: Can be fully tested by viewing a ticker's combined chart and verifying both price candles and sentiment line appear with proper scaling. Delivers immediate visual correlation insight.

**Acceptance Scenarios**:

1. **Given** I have a configuration with tickers, **When** I view the sentiment details for a ticker, **Then** I see a chart with price candlesticks and a sentiment line overlaid on a secondary axis
2. **Given** the chart is displayed, **When** I hover over a data point, **Then** I see a tooltip showing the date, OHLC prices, and sentiment score for that day
3. **Given** the chart is displayed, **When** I look at the Y-axes, **Then** I see price scale on the left axis and sentiment scale (-1 to +1) on the right axis
4. **Given** the chart is loading data, **When** data is being fetched, **Then** I see a loading indicator until both price and sentiment data are ready

---

### User Story 2 - Access Historical Price Data (Priority: P1)

As a dashboard user, I want to retrieve historical OHLC (Open, High, Low, Close) price data for any ticker in my configuration so that I can analyze price movements over time.

**Why this priority**: This is a prerequisite for the overlay chart - without price data, there's nothing to combine with sentiment. Equal priority to User Story 1 as they are interdependent.

**Independent Test**: Can be tested by calling the price data endpoint and verifying it returns properly formatted OHLC data for a given ticker and date range.

**Acceptance Scenarios**:

1. **Given** I have an authenticated session, **When** I request price data for a valid ticker, **Then** I receive OHLC data points for the requested time period
2. **Given** I request price data, **When** I specify a date range, **Then** I receive only data within that range
3. **Given** I request price data for a ticker, **When** the ticker has no data available, **Then** I receive an appropriate message indicating no data is available
4. **Given** I request price data, **When** the external data source is unavailable, **Then** I receive cached data if available, or a graceful error message

---

### User Story 3 - Customize Chart Time Range (Priority: P2)

As a user analyzing market trends, I want to select different time ranges for the chart (1 week, 1 month, 3 months, 6 months, 1 year) so that I can analyze short-term and long-term correlations between sentiment and price.

**Why this priority**: Enhances the core feature by allowing users to focus on relevant time periods. Default 30-day view works for MVP, but range selection significantly improves analytical capability.

**Independent Test**: Can be tested by selecting different time range options and verifying the chart updates to show the correct date range for both price and sentiment data.

**Acceptance Scenarios**:

1. **Given** the chart is displayed with default 30-day range, **When** I select "3 months", **Then** the chart updates to show 90 days of price and sentiment data
2. **Given** I select a time range, **When** the chart updates, **Then** both price and sentiment data are aligned to the same time range
3. **Given** I select a time range longer than available data, **When** the chart renders, **Then** it shows all available data with appropriate indication of data boundaries

---

### User Story 4 - Toggle Chart Layers (Priority: P3)

As a user analyzing the chart, I want to toggle the visibility of price candles and sentiment line independently so that I can focus on one data type when needed.

**Why this priority**: Nice-to-have feature that improves user experience but doesn't block core functionality. Users can achieve basic goals without toggles.

**Independent Test**: Can be tested by clicking toggle buttons and verifying the corresponding chart element appears or disappears while the other remains visible.

**Acceptance Scenarios**:

1. **Given** both price and sentiment are displayed, **When** I toggle off the sentiment line, **Then** only price candles remain visible
2. **Given** both price and sentiment are displayed, **When** I toggle off price candles, **Then** only the sentiment line remains visible
3. **Given** one layer is hidden, **When** I toggle it back on, **Then** it reappears on the chart

---

### Edge Cases

- What happens when sentiment data exists but price data is unavailable for certain dates? Display sentiment with gaps in price data, clearly indicating missing data periods.
- What happens when the ticker is delisted or no longer traded? Show historical data up to the delisting date with a clear indicator.
- How does the system handle weekends and market holidays? Price data only exists for trading days; sentiment may exist for all days. Chart should align data appropriately, showing sentiment for non-trading days without price candles.
- What happens when the user's configuration has no tickers? Display an empty state with guidance to add tickers.
- How does the chart handle extremely volatile sentiment or price swings? Auto-scale axes to fit all data points while maintaining readability.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide historical OHLC price data for any valid stock ticker
- **FR-002**: System MUST return price data with fields: date, open, high, low, close, volume
- **FR-003**: System MUST support date range filtering for price data (default: 30 days)
- **FR-004**: System MUST align price data with sentiment data by date for chart rendering
- **FR-005**: System MUST display price data as candlestick visualization on the left Y-axis
- **FR-006**: System MUST display sentiment data as a line chart on the right Y-axis (scale: -1 to +1)
- **FR-007**: System MUST provide interactive tooltips showing date, OHLC values, and sentiment on hover
- **FR-008**: System MUST handle missing data gracefully (gaps in either price or sentiment)
- **FR-009**: System MUST cache price data until next market open (or 24 hours for non-trading days) to reduce external data source calls
- **FR-010**: System MUST respect existing authentication (X-User-ID header) for price data access
- **FR-011**: System MUST provide time range selection options: 1W, 1M, 3M, 6M, 1Y
- **FR-012**: System MUST display loading state while fetching chart data
- **FR-013**: System MUST provide a dropdown selector allowing users to choose which sentiment source (Tiingo, Finnhub, our_model, or aggregated) to display on the chart
- **FR-014**: System MUST use Tiingo as the primary price data source, falling back to Finnhub when Tiingo is unavailable or returns no data

### Key Entities

- **PriceCandle**: Represents a single day's price data - contains date, open, high, low, close, and volume for a trading day
- **SentimentPoint**: Represents sentiment at a point in time - contains date, score (-1 to +1), and source
- **ChartDataSet**: Combined price and sentiment data for a ticker - contains aligned arrays of price candles and sentiment points for the selected date range

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view a combined price-sentiment chart within 3 seconds of requesting it
- **SC-002**: Price data is available for at least 1 year of historical data for active tickers
- **SC-003**: Chart renders correctly on both desktop (1024px+) and mobile (320px+) viewports
- **SC-004**: 95% of price data requests return successfully (excluding invalid tickers)
- **SC-005**: Users can identify sentiment-price correlation patterns without switching between views
- **SC-006**: Chart tooltip displays complete information (date, OHLC, sentiment) within 200ms of hover
- **SC-007**: Time range changes update the chart within 2 seconds

## Clarifications

### Session 2025-12-01

- Q: Which sentiment source should be displayed on the overlay chart? → A: User-selectable source (dropdown to pick which source to show)
- Q: What cache duration should be used for OHLC price data? → A: Until next market open (or 24 hours for non-trading days)
- Q: Which external adapter should be the primary source for price data? → A: Tiingo primary, Finnhub fallback

## Assumptions

- Price data will be sourced from existing external adapters (Tiingo/Finnhub) that already provide OHLC data for ATR calculations
- The frontend already uses TradingView Lightweight Charts library which supports dual-axis charts
- Sentiment data is already available via existing endpoints and can be aligned with price data by date
- Users have already authenticated via the existing anonymous session flow
- Default time range of 30 days balances data volume with typical user analysis needs
