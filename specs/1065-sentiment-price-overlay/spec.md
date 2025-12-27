# Feature Specification: Sentiment-Price Overlay Chart

**Feature Branch**: `1065-sentiment-price-overlay`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Overlay sentiment trend line on OHLC price chart - combine sentiment data visualization with price candlesticks on a single dual-axis Chart.js chart"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Sentiment Overlay on Price Chart (Priority: P1)

As an investor using the sentiment analyzer dashboard, I want to see the sentiment trend line overlaid directly on top of the OHLC price candlestick chart so that I can immediately identify correlations between news sentiment and price movements without switching between charts.

**Why this priority**: This is the core value proposition. Currently, the dashboard shows OHLC and sentiment as separate charts, requiring mental context-switching. A unified dual-axis chart enables instant pattern recognition - the key insight users need for trading decisions.

**Independent Test**: Can be fully tested by viewing the OHLC chart and verifying the sentiment line appears overlaid with correct scaling on the right Y-axis. Delivers immediate correlation insight.

**Acceptance Scenarios**:

1. **Given** the OHLC chart is rendered with price data, **When** sentiment data is available for the same ticker and resolution, **Then** a sentiment trend line appears overlaid on the chart with sentiment scale on the right Y-axis
2. **Given** the overlay chart is displayed, **When** I hover over any data point, **Then** I see a tooltip showing: date/time, OHLC prices (Open, High, Low, Close), and sentiment score
3. **Given** the overlay chart is rendered, **When** I look at the Y-axes, **Then** I see price scale (dollars) on the left axis and sentiment scale (-1.0 to +1.0) on the right axis
4. **Given** I change the resolution via the unified selector, **When** the chart updates, **Then** both price candles and sentiment line update to match the new resolution

---

### User Story 2 - Visual Distinction Between Data Types (Priority: P1)

As a user analyzing the combined chart, I want the sentiment line to be visually distinct from the price candlesticks so that I can easily differentiate between the two data types at a glance.

**Why this priority**: Equal priority with overlay display - without visual distinction, the overlay becomes confusing rather than helpful. Color coding and styling are essential for usability.

**Independent Test**: Can be tested by rendering the overlay and verifying the sentiment line has a distinct color and style (smooth line vs block candles).

**Acceptance Scenarios**:

1. **Given** the overlay chart is displayed, **When** I view the chart, **Then** the sentiment line is rendered in a distinctive color (blue) that contrasts with bullish (green) and bearish (red) candles
2. **Given** the overlay chart has data, **When** I view the chart legend, **Then** it clearly labels "Price" and "Sentiment" with their respective colors
3. **Given** the sentiment line crosses through candle regions, **When** I view the overlap area, **Then** the sentiment line remains visible with appropriate opacity/z-index

---

### User Story 3 - Handle Data Alignment (Priority: P2)

As a user viewing the overlay chart, I want price and sentiment data to be properly aligned by timestamp so that correlations are accurate even when one dataset has gaps.

**Why this priority**: Important for accuracy but not blocking basic visualization. Users can get value from approximate alignment initially.

**Independent Test**: Can be tested by displaying data with known gaps and verifying points align correctly by timestamp.

**Acceptance Scenarios**:

1. **Given** sentiment data exists for times when no price data exists (weekends/holidays), **When** the chart renders, **Then** the sentiment line continues but price candles are absent for those periods
2. **Given** price data exists for times when no sentiment data exists, **When** the chart renders, **Then** price candles appear but the sentiment line has gaps
3. **Given** both datasets are available, **When** the chart renders, **Then** data points align by their timestamp, not by array index

---

### Edge Cases

- What happens when sentiment data is completely unavailable for a ticker? Display OHLC chart normally with a message indicating sentiment data is unavailable.
- What happens when price data is unavailable but sentiment exists? Display a degraded chart with only the sentiment line visible and a message.
- How does the chart handle extreme sentiment values near +1.0 or -1.0? Right Y-axis should always show the full -1.0 to +1.0 range to maintain consistent visual reference.
- What happens when both datasets have very different time ranges? Display the intersection of both ranges, with indicators showing data availability boundaries.
- How does the chart handle rapid resolution changes? Use debouncing (existing 300ms debounce) to prevent excessive API calls.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST overlay sentiment data as a line chart on top of the existing OHLC candlestick chart
- **FR-002**: System MUST display the right Y-axis with sentiment scale from -1.0 to +1.0
- **FR-003**: System MUST display the left Y-axis with price scale (auto-scaled to data)
- **FR-004**: System MUST render the sentiment line in a contrasting color (#3b82f6 blue)
- **FR-005**: System MUST fetch sentiment data from the existing timeseries API endpoint
- **FR-006**: System MUST align sentiment and price data by timestamp
- **FR-007**: System MUST update tooltips to show both price (OHLC) and sentiment values
- **FR-008**: System MUST handle resolution changes from the unified selector (Feature 1064)
- **FR-009**: System MUST display loading state while fetching sentiment data
- **FR-010**: System MUST gracefully degrade when sentiment data is unavailable (show OHLC only)
- **FR-011**: System MUST include a legend showing both data series
- **FR-012**: System MUST preserve existing OHLC chart functionality (candle colors, tooltips, etc.)

### Key Entities

- **SentimentDataPoint**: Represents a single sentiment reading - contains timestamp, average_score (float -1.0 to +1.0), and item_count
- **OHLCCandle**: Existing - contains date, open, high, low, close
- **OverlayDataset**: Combined visualization data - contains aligned arrays of candles and sentiment points

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view both price and sentiment data on a single chart without scrolling or switching views
- **SC-002**: Chart tooltip displays complete information (date, OHLC, sentiment) within 200ms of hover
- **SC-003**: Sentiment line is visually distinguishable from price candles at any zoom level
- **SC-004**: Resolution changes via unified selector update both datasets within 3 seconds
- **SC-005**: Chart renders correctly on desktop viewports (1024px+)
- **SC-006**: Users can identify correlation patterns between sentiment spikes and price movements

## Assumptions

- The existing OHLC chart (ohlc.js) uses Chart.js which supports multiple datasets and dual Y-axes
- The timeseries API endpoint already provides sentiment data in the required format
- The unified resolution selector (Feature 1064) is already integrated and functional
- Session authentication (X-User-ID) is already implemented and working
