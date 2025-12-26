# Feature Specification: Fix OHLCResponse Intraday Date Validation

**Feature Branch**: `1062-fix-intraday-date-validation`
**Created**: 2025-12-26
**Status**: Draft
**Input**: User description: "Fix OHLCResponse Pydantic validation for intraday resolutions - convert datetime to date before building response"

## Problem Statement

The OHLC endpoint returns HTTP 500 Internal Server Error when using intraday resolutions (1, 5, 15, 30, 60 minutes). Daily resolution (D) works correctly.

**Root Cause**: The `OHLCResponse` model defines `start_date` and `end_date` as `date` types, but when using intraday resolutions, the Tiingo IEX adapter returns `datetime` objects with time components (e.g., `2024-11-29T14:30:00Z`). Pydantic rejects these with error "Datetimes provided to dates should have zero time".

**Technical Detail**: The isinstance check at `ohlc.py:305-309` is ineffective because `datetime` is a subclass of `date`, so `isinstance(datetime_obj, date)` returns `True`, causing the `.date()` conversion to be skipped.

## User Scenarios & Testing

### User Story 1 - View Intraday OHLC Data (Priority: P1)

As a trader viewing the dashboard, I want to select 5-minute, 15-minute, or other intraday time buckets for OHLC charts so that I can analyze short-term price movements.

**Why this priority**: This is the core feature blocking the demo URL from being fully functional. All intraday resolutions are broken.

**Independent Test**: Can be fully tested by making API requests with `resolution=5` and verifying a 200 response with valid candle data.

**Acceptance Scenarios**:

1. **Given** the OHLC endpoint is deployed, **When** I request `/api/v2/tickers/AAPL/ohlc?resolution=5` with valid auth, **Then** I receive HTTP 200 with candle data for 5-minute intervals
2. **Given** the OHLC endpoint is deployed, **When** I request `/api/v2/tickers/AAPL/ohlc?resolution=1` with valid auth, **Then** I receive HTTP 200 with candle data for 1-minute intervals
3. **Given** the OHLC endpoint is deployed, **When** I request `/api/v2/tickers/AAPL/ohlc?resolution=D` with valid auth, **Then** I continue to receive HTTP 200 (no regression)

---

### User Story 2 - Frontend Time Bucket Selection (Priority: P1)

As a user on the frontend dashboard, I want to click on time bucket buttons (1m, 5m, 15m, 30m, 1h, 1d) and see the chart update with the appropriate data.

**Why this priority**: The frontend is already built with selectable time buckets but is currently broken due to the API error.

**Independent Test**: Can be tested by loading the dashboard, selecting each time bucket, and verifying the chart renders without errors.

**Acceptance Scenarios**:

1. **Given** I am on the price chart page, **When** I click "5m" button, **Then** the chart refreshes with 5-minute candles
2. **Given** I am on the price chart page, **When** I click "1D" button, **Then** the chart refreshes with daily candles (regression test)

---

### Edge Cases

- What happens when the first candle has a datetime and the last has a date? (Hybrid data) - Handle gracefully
- What happens with empty candle arrays? - Return 404 as currently implemented

## Requirements

### Functional Requirements

- **FR-001**: System MUST accept and return valid responses for all resolution values: 1, 5, 15, 30, 60, D
- **FR-002**: System MUST correctly convert `datetime` objects to `date` objects in `OHLCResponse.start_date` and `end_date` fields
- **FR-003**: System MUST maintain backwards compatibility with daily resolution which already works
- **FR-004**: System MUST NOT modify the `PriceCandle.date` field behavior (it can remain datetime for intraday)

### Technical Requirements

- **TR-001**: Fix isinstance check order at `ohlc.py:305-309` to check for `datetime` type before `date` type
- **TR-002**: Add unit test coverage for intraday response construction

## Success Criteria

### Measurable Outcomes

- **SC-001**: API requests with `resolution=5` return HTTP 200 (currently returns 500)
- **SC-002**: All intraday resolutions (1, 5, 15, 30, 60) return valid responses
- **SC-003**: Daily resolution (D) continues to work (no regression)
- **SC-004**: Unit tests pass for all resolution values
- **SC-005**: Frontend demo URL is fully functional with all time bucket selections

## Implementation Notes

The fix involves changing the isinstance check order:

```python
# Current (broken):
start_date=candles[0].date if isinstance(candles[0].date, date) else candles[0].date.date()

# Fixed:
start_date=candles[0].date.date() if isinstance(candles[0].date, datetime) else candles[0].date
```

This ensures `datetime` objects (which are subclasses of `date`) are properly converted to pure `date` objects.

## Files to Modify

- `src/lambdas/dashboard/ohlc.py` - Fix isinstance check at lines ~305-309
- `tests/unit/dashboard/test_ohlc.py` - Add tests for intraday response construction
