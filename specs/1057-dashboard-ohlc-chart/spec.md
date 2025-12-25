# Feature Specification: Add OHLC Chart to Vanilla JS Dashboard

**Feature Branch**: `1057-dashboard-ohlc-chart`
**Created**: 2025-12-25
**Status**: Draft
**Input**: Add OHLC candlestick chart to the vanilla JS dashboard (src/dashboard/) to make the ONE URL demo-able with selectable time buckets.

## Problem Statement

The ONE URL dashboard (`https://d2z9uvoj5xlbd2.cloudfront.net`) currently displays:
- Sentiment distribution chart ✅
- Sentiment timeseries chart (calling `/api/v2/timeseries/{ticker}`) ✅

But does NOT display:
- OHLC candlestick price data ❌
- Time bucket resolution selector (1m, 5m, 15m, 30m, 1h, D) ❌

**Root Cause**: The vanilla JS dashboard (`src/dashboard/`) was never updated to call the OHLC endpoint (`/api/v2/tickers/{ticker}/ohlc`) which was implemented in Feature 1035. A Next.js frontend exists in `frontend/` with full OHLC support, but it is NOT deployed - the vanilla JS dashboard is what users see.

**Goal**: Add OHLC candlestick chart with time bucket selection to the vanilla JS dashboard to make it demo-able.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View OHLC Candlesticks (Priority: P0)

As a demo viewer, I want to see real OHLC candlestick data for a ticker on the dashboard, so that I can visualize price movements alongside sentiment.

**Why this priority**: Core demo requirement - without price data, the dashboard only shows sentiment which has limited standalone value.

**Independent Test**: Navigate to ONE URL, enter ticker "AAPL", verify candlestick chart displays with open/high/low/close data.

**Acceptance Scenarios**:

1. **Given** a user on the dashboard, **When** they enter a valid ticker (e.g., AAPL), **Then** an OHLC candlestick chart displays with price data from Tiingo/Finnhub
2. **Given** the OHLC chart is displayed, **When** user hovers over a candle, **Then** tooltip shows OHLC values for that time period
3. **Given** a user enters an invalid ticker, **When** API returns 404, **Then** chart shows empty state with error message

---

### User Story 2 - Select Time Resolution (Priority: P0)

As a trader, I want to select different time resolutions (1m, 5m, 15m, 30m, 1h, D), so that I can analyze price patterns at different granularities.

**Why this priority**: Time bucket selection is the key feature requested for demo-ability.

**Independent Test**: Click on "5m" resolution button, verify chart refetches data and displays 5-minute candles.

**Acceptance Scenarios**:

1. **Given** the OHLC chart is displayed, **When** user clicks a resolution button (e.g., "5m"), **Then** chart refetches and displays data at that resolution
2. **Given** a resolution is selected, **When** user changes ticker, **Then** selected resolution persists
3. **Given** intraday resolution selected (1m, 5m, etc.), **When** API returns fallback to daily, **Then** fallback message displays

---

### Edge Cases

- What if OHLC API returns 401 Unauthorized? Show auth error and prompt session refresh
- What if OHLC API times out? Show loading skeleton, retry once, then show error state
- What if resolution not supported for ticker? Display fallback message from API response

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard MUST display OHLC candlestick chart for valid tickers
- **FR-002**: Dashboard MUST provide resolution selector with options: 1m, 5m, 15m, 30m, 1h, D
- **FR-003**: OHLC requests MUST include X-User-ID header from session auth
- **FR-004**: Chart MUST update when resolution or ticker changes
- **FR-005**: Selected resolution MUST persist in sessionStorage
- **FR-006**: Fallback message MUST display when intraday resolution falls back to daily

### Non-Functional Requirements

- **NFR-001**: Chart render time < 500ms after data fetch complete
- **NFR-002**: Resolution switch MUST trigger data fetch within 100ms
- **NFR-003**: Use existing Chart.js library (already included in index.html)

### Key Entities

- **OHLC Candle**: { timestamp, open, high, low, close, volume }
- **Resolution**: '1' | '5' | '15' | '30' | '60' | 'D' (backend values)
- **Display Labels**: '1m', '5m', '15m', '30m', '1h', 'Day'

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: ONE URL displays OHLC candlestick chart for any valid US equity ticker
- **SC-002**: 6 resolution buttons visible and functional
- **SC-003**: Resolution preference persists across page reloads
- **SC-004**: No console errors during normal operation
- **SC-005**: OHLC chart displays alongside existing sentiment charts (not replacing)

## Technical Approach

### Files to Modify

1. **src/dashboard/index.html**: Add OHLC chart container section
2. **src/dashboard/ohlc.js** (NEW): OHLC chart logic, resolution selector, API integration
3. **src/dashboard/styles.css**: Styles for OHLC chart and resolution selector
4. **src/dashboard/config.js**: Add OHLC endpoint configuration

### API Integration

Endpoint: `GET /api/v2/tickers/{ticker}/ohlc`
Query params: `resolution`, `range`
Headers: `X-User-ID: {sessionUserId}`

### Reference Implementation

The Next.js frontend (`frontend/src/components/charts/price-sentiment-chart.tsx`) has complete OHLC chart implementation. Key patterns to port:
- Resolution selector button group
- OHLC API response handling
- Fallback message display
- Chart.js candlestick rendering

## Dependencies

- Feature 1035 (OHLC Resolution Selector) - MERGED (provides backend endpoint)
- Feature 1056 (Dashboard OHLC Secrets) - MERGED (provides API key access)
- Session auth (Feature 1050) - MERGED (provides X-User-ID)

## Out of Scope

- Next.js frontend deployment (using vanilla JS)
- Backend changes (endpoint already exists)
- SSE streaming for OHLC (future enhancement)
- Sentiment overlay on OHLC chart (future enhancement)
