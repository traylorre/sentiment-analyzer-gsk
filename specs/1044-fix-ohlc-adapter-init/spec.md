# Feature Specification: Fix OHLC Adapter Initialization

**Feature Branch**: `1044-fix-ohlc-adapter-init`
**Created**: 2025-12-24
**Status**: Draft
**Input**: User description: "Fix OHLC endpoint TiingoAdapter/FinnhubAdapter initialization bug: get_tiingo_adapter() and get_finnhub_adapter() dependency functions in src/lambdas/dashboard/ohlc.py call adapters without passing required api_key argument, causing TypeError at runtime. Fix should read API keys from environment variables TIINGO_API_KEY and FINNHUB_API_KEY."

## Problem Statement

The OHLC endpoint at `/api/v2/tickers/{ticker}/ohlc` is non-functional in production. When users attempt to view OHLC candlestick data, the Lambda returns a 500 Internal Server Error.

**Root Cause**: The `get_tiingo_adapter()` and `get_finnhub_adapter()` dependency functions in `src/lambdas/dashboard/ohlc.py` instantiate `TiingoAdapter()` and `FinnhubAdapter()` without passing the required `api_key` argument, causing a `TypeError` at runtime:

```
TypeError: TiingoAdapter.__init__() missing 1 required positional argument: 'api_key'
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View OHLC Data for a Ticker (Priority: P1)

As a dashboard user, I want to view OHLC candlestick data when I search for a ticker, so that I can analyze price movements.

**Why this priority**: This is the core feature being blocked. Without this fix, the entire OHLC visualization feature is non-functional.

**Independent Test**: Can be tested by making an API request to `/api/v2/tickers/AAPL/ohlc?resolution=D` with a valid X-User-ID header and verifying a 200 response with candle data.

**Acceptance Scenarios**:

1. **Given** the Lambda has TIINGO_API_KEY environment variable set, **When** a user requests OHLC data for a valid ticker, **Then** the system returns OHLC candle data with a 200 status code
2. **Given** the Lambda has FINNHUB_API_KEY environment variable set, **When** a user requests intraday OHLC data, **Then** the system returns intraday candles from Finnhub
3. **Given** the API key environment variables are not set, **When** a user requests OHLC data, **Then** the system returns a graceful error (503) indicating the data source is unavailable

---

### User Story 2 - Resolution Selection Works (Priority: P1)

As a dashboard user, I want to select different time resolutions (1m, 5m, 15m, 30m, 1h, D) for OHLC data, so that I can analyze price patterns at different granularities.

**Why this priority**: This is part of the core OHLC feature being blocked by the initialization bug.

**Independent Test**: Can be tested by making API requests with different resolution query parameters and verifying the returned data matches the requested resolution.

**Acceptance Scenarios**:

1. **Given** the OHLC endpoint is functional, **When** a user requests resolution=5, **Then** the system returns 5-minute candles
2. **Given** intraday data is unavailable, **When** a user requests an intraday resolution, **Then** the system falls back to daily data with a fallback message

---

### Edge Cases

- What happens when TIINGO_API_KEY is not set but FINNHUB_API_KEY is? System uses Finnhub as fallback for all resolutions.
- What happens when neither API key is set? System returns 503 with clear error message.
- What happens when API keys are invalid? System logs error and returns 503 or 404 (no data available).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read the Tiingo API key from the `TIINGO_API_KEY` environment variable when initializing TiingoAdapter
- **FR-002**: System MUST read the Finnhub API key from the `FINNHUB_API_KEY` environment variable when initializing FinnhubAdapter
- **FR-003**: System MUST pass the API key to adapter constructors when creating instances
- **FR-004**: System MUST handle missing API key environment variables gracefully (log warning, skip that data source)
- **FR-005**: System MUST return 503 Service Unavailable if no data source is available due to missing API keys

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: OHLC endpoint returns 200 with valid candle data for known tickers (AAPL, MSFT, GOOGL)
- **SC-002**: Dashboard displays real OHLC candlestick charts when a user searches for a ticker
- **SC-003**: Resolution selector in the dashboard works (switching between 1m, 5m, 15m, 30m, 1h, D)
- **SC-004**: No TypeError exceptions in Lambda logs related to adapter initialization

## Assumptions

- TIINGO_API_KEY and FINNHUB_API_KEY environment variables are already configured in the Lambda's Terraform configuration
- The existing adapter implementations are correct and only the initialization is broken
- Feature 1035 (OHLC Resolution Selector) and Feature 1038 (Dashboard Integration) are already complete

## Dependencies

- TIINGO_API_KEY secret must be set in AWS Secrets Manager and referenced in Lambda environment
- FINNHUB_API_KEY secret must be set in AWS Secrets Manager and referenced in Lambda environment

## Out of Scope

- Changes to TiingoAdapter or FinnhubAdapter classes themselves
- Changes to the OHLC response format or data model
- Frontend changes (already complete in Features 1035/1038)
