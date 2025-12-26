# Feature Specification: OHLC Intraday Resolution Support via Tiingo IEX

**Feature Branch**: `1055-ohlc-resolution-selector`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "Enable intraday (1m, 5m, 15m, 30m, 1h) price resolutions by leveraging Tiingo IEX intraday endpoint instead of Finnhub (which requires Premium subscription)."

## Problem Statement

The price resolution buttons (1m, 5m, 15m, 30m, 1h) on the dashboard chart appear to "not work" because:

1. **Current behavior**: Intraday resolutions silently fall back to daily data
2. **Root cause**: Finnhub API (current intraday data source) returns 403 "You don't have access to this resource" - the free tier doesn't include stock candles
3. **Solution**: Use Tiingo IEX intraday endpoint which is available with our existing Tiingo API key

**Verified**: Tiingo IEX endpoint returns proper OHLC data at all resolutions (1min, 5min, 15min, 30min, 1hour) with our current API key.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View 5-Minute Price Candles (Priority: P1)

As a trader, I want to view AAPL price data at 5-minute resolution so I can analyze intraday price movements.

**Why this priority**: This is the core functionality that is currently broken. Without intraday resolution support, the resolution buttons are non-functional.

**Independent Test**: Click the "5m" button on the OHLC chart and verify 5-minute candles are displayed (not daily fallback).

**Acceptance Scenarios**:

1. **Given** the user is viewing the OHLC chart, **When** they click the "5m" resolution button, **Then** the chart displays 5-minute candles from Tiingo IEX data
2. **Given** the user selected 5m resolution, **When** they check the data source indicator, **Then** it shows "tiingo" (not "finnhub")
3. **Given** the user is on 5m resolution, **When** they hover over a candle, **Then** they see OHLC values (open, high, low, close) for that 5-minute period

---

### User Story 2 - View Other Intraday Resolutions (Priority: P2)

As a trader, I want to switch between 1m, 15m, 30m, and 1h resolutions to analyze different timeframes.

**Why this priority**: Extends P1 functionality to all intraday resolutions - same mechanism, different parameters.

**Independent Test**: Click each resolution button (1m, 15m, 30m, 1h) and verify appropriate candle data is displayed.

**Acceptance Scenarios**:

1. **Given** the user clicks the "1m" button, **When** the chart loads, **Then** it shows 1-minute candles (up to 7 days of data)
2. **Given** the user clicks the "15m" button, **When** the chart loads, **Then** it shows 15-minute candles
3. **Given** the user clicks the "30m" button, **When** the chart loads, **Then** it shows 30-minute candles
4. **Given** the user clicks the "1h" button, **When** the chart loads, **Then** it shows 1-hour candles

---

### User Story 3 - Daily Resolution Fallback (Priority: P3)

As a user, I want daily resolution to continue working via Tiingo daily endpoint (existing behavior preserved).

**Why this priority**: Ensures regression-free change - daily data should continue working as before.

**Independent Test**: Click "Day" button and verify daily candles display as before.

**Acceptance Scenarios**:

1. **Given** the user clicks the "Day" button, **When** the chart loads, **Then** it shows daily candles from Tiingo daily endpoint
2. **Given** daily resolution is selected, **When** querying data, **Then** the source is "tiingo" and no fallback message is shown

---

### Edge Cases

- What happens when Tiingo IEX returns no data (e.g., outside market hours)?
  - Display "No intraday data available" message with last available data
- What happens when ticker is not available on IEX?
  - Fall back to daily data with fallback message explaining IEX doesn't cover this ticker
- How does system handle rate limiting from Tiingo?
  - Return cached data if available, otherwise show error message

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST fetch intraday OHLC data from Tiingo IEX endpoint for resolutions 1, 5, 15, 30, 60 minutes
- **FR-002**: System MUST map resolution values ('1', '5', '15', '30', '60') to Tiingo resampleFreq format ('1min', '5min', '15min', '30min', '1hour')
- **FR-003**: System MUST fall back to daily data if Tiingo IEX returns empty/no data
- **FR-004**: System MUST set source="tiingo" in response for intraday data
- **FR-005**: System MUST cache intraday data with 5-minute TTL to reduce API calls
- **FR-006**: System MUST respect existing time range limits per resolution (1m: 7 days, 5m: 30 days, etc.)

### Key Entities

- **PriceCandle**: Existing entity with open, high, low, close, volume, timestamp - no changes needed
- **OHLCResponse**: Existing response model - no changes needed, already supports resolution field

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: User can view 5-minute candle data for AAPL by clicking the "5m" button (no fallback to daily)
- **SC-002**: All intraday resolutions (1m, 5m, 15m, 30m, 1h) return actual intraday data, not daily fallback
- **SC-003**: Response time for intraday data is under 2 seconds (cached responses under 100ms)
- **SC-004**: No changes to frontend code required - existing resolution buttons work with new backend

## Out of Scope

- Finnhub adapter improvements (will be deprecated for OHLC)
- Frontend UI changes
- New resolutions beyond existing (1m, 5m, 15m, 30m, 1h, D)
- Extended hours data (pre-market/after-hours)

## Technical Context (for planning)

**Existing infrastructure**:
- TiingoAdapter at `src/lambdas/shared/adapters/tiingo.py` - has `get_ohlc()` for daily, needs `get_intraday_ohlc()`
- FinnhubAdapter at `src/lambdas/shared/adapters/finnhub.py` - currently used for intraday, will be replaced
- OHLC handler at `src/lambdas/dashboard/ohlc.py` - dispatches to adapters based on resolution
- Tiingo IEX endpoint verified working: `https://api.tiingo.com/iex/{ticker}/prices?resampleFreq={resolution}&token={key}`

**Verified Tiingo IEX support**:
- 1min: Works (tested: 1049 candles)
- 5min: Works (tested: 210 candles)
- 15min: Works (tested: 70 candles)
- 30min: Works (tested: 35 candles)
- 1hour: Works (tested: 16 candles)
