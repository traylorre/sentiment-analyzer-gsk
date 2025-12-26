# Feature Specification: Fix OHLC Chart Invalid Date

**Feature Branch**: `1061-fix-ohlc-date-field`
**Created**: 2025-12-26
**Status**: Draft
**Input**: Price Chart shows "Invalid Date" on X-axis labels

## Problem Statement

The OHLC chart in `src/dashboard/ohlc.js` accesses `c.timestamp` but the backend API returns a `date` field. This mismatch causes `new Date(undefined)` which produces "Invalid Date".

**Evidence**:
- Backend: `PriceCandle.date` field (ohlc.py:76)
- Frontend: `c.timestamp` access (ohlc.js:403, 407)

## User Scenarios & Testing _(mandatory)_

### User Story 1 - OHLC Chart Date Display (Priority: P1)

As a dashboard user, I want to see proper date/time labels on the OHLC chart X-axis so I can understand the time context of price movements.

**Acceptance Scenarios**:

1. **Given** daily resolution is selected, **When** the chart renders, **Then** X-axis shows dates like "Dec 25".

2. **Given** intraday resolution (1m, 5m, etc.) is selected, **When** the chart renders, **Then** X-axis shows times like "14:30".

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Frontend MUST access `c.date` instead of `c.timestamp` in ohlc.js.
- **FR-002**: The fix MUST be applied at lines 403 and 407.
- **FR-003**: No backend changes required.

## Success Criteria _(mandatory)_

- **SC-001**: X-axis shows valid date/time labels (not "Invalid Date").
- **SC-002**: Daily resolution shows "Mon DD" format.
- **SC-003**: Intraday resolution shows "HH:MM" format.

## Implementation Notes

Two-line fix in `src/dashboard/ohlc.js`:

```diff
-        const labels = candles.map(c => this.formatTimestamp(c.timestamp));
+        const labels = candles.map(c => this.formatTimestamp(c.date));

         const data = candles.map(c => ({
-            x: this.formatTimestamp(c.timestamp),
+            x: this.formatTimestamp(c.date),
```
