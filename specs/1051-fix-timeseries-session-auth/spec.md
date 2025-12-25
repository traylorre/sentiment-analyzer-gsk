# Feature Specification: Fix Timeseries Module Auth

**Feature Branch**: `1051-fix-timeseries-session-auth`
**Created**: 2024-12-24
**Status**: Draft
**Input**: "Fix 401 on /api/v2/timeseries by adding X-User-ID header to timeseries.js"

## Problem Statement

Feature 1050 fixed auth for `fetchMetrics()` in `app.js`, but the `timeseries.js` module also makes API calls without auth headers. The resolution selector and OHLC chart functionality exists but is broken due to 401 errors.

**Related**: Feature 1050 (PR #505)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - OHLC Chart Loads Successfully (Priority: P1)

User can view the OHLC timeseries chart with sentiment data for any ticker.

**Why this priority**: Core functionality - without this fix, the resolution selector and chart are unusable.

**Independent Test**: Load dashboard, enter a ticker (e.g., AAPL), verify chart displays without 401 errors.

**Acceptance Scenarios**:

1. **Given** session is initialized, **When** timeseries data is requested, **Then** data loads without 401 error
2. **Given** user switches resolution, **When** new data is fetched, **Then** fetch includes X-User-ID header

---

### User Story 2 - Resolution Switching Works (Priority: P1)

User can switch between time resolutions (1m, 5m, 10m, 1h, etc.) and see updated chart.

**Acceptance Scenarios**:

1. **Given** chart is displaying data, **When** user clicks different resolution, **Then** chart updates with correct data

---

### Edge Cases

- timeseries.js must wait for session from app.js (race condition)
- Multi-ticker batch endpoint also needs auth

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: timeseries.js MUST use session UUID from app.js for all API calls
- **FR-002**: All fetch requests in timeseries.js MUST include `X-User-ID: {uuid}` header
- **FR-003**: timeseries.js MUST wait for session initialization before making API calls

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: No 401 errors on `/api/v2/timeseries/*` endpoints
- **SC-002**: Resolution selector UI works (clicking buttons updates chart)
- **SC-003**: Multi-ticker comparison view loads all tickers

## Technical Context

### Files to Modify

1. `src/dashboard/timeseries.js` - Add sessionUserId to all fetch calls

### Pattern from Feature 1050

Use the `sessionUserId` variable from `app.js` (now global after Feature 1050):
```javascript
headers: {
    'X-User-ID': sessionUserId
}
```
