# Feature Specification: Fix Sentiment Overlay Timestamp Field Mismatch

**Feature Branch**: `1069-fix-sentiment-overlay-timestamp`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "fix-sentiment-overlay-timestamp"

## Problem Statement

The Price Chart shows the blue "Sentiment" line in the legend, but no actual sentiment data points appear on the chart.

### Root Cause

In `src/dashboard/ohlc.js:564`, the code looks for timestamp with wrong field names:

```javascript
const ts = bucket.bucket_timestamp || bucket.SK;  // WRONG
```

The API (`/api/v2/timeseries/{ticker}`) returns buckets with `timestamp` field:
```json
{
  "buckets": [
    {
      "timestamp": "2025-12-27T10:00:00+00:00",
      "avg": 0.45,
      ...
    }
  ]
}
```

The field name mismatch causes `ts` to be `undefined`, resulting in no sentiment data being mapped.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Sentiment Overlay on Price Chart (Priority: P1)

As a dashboard user, I want to see the sentiment line overlaid on the OHLC price chart so that I can correlate price movements with market sentiment.

**Why this priority**: This is the core purpose of Feature 1065 (sentiment-price overlay). The chart currently shows the legend but no data, making the feature broken.

**Independent Test**: Open dashboard, observe Price Chart - blue sentiment line should appear with actual data points aligned to OHLC candles.

**Acceptance Scenarios**:

1. **Given** Price Chart displays OHLC candles for AAPL, **When** sentiment data exists for the time period, **Then** blue sentiment line MUST appear with data points
2. **Given** sentiment API returns buckets with `timestamp` field, **When** chart parses the response, **Then** all bucket timestamps MUST be correctly extracted
3. **Given** resolution switch from 1h to 5m, **When** chart reloads sentiment data, **Then** new sentiment data MUST be correctly aligned to new OHLC candles

---

### User Story 2 - Console Logging for Debugging (Priority: P2)

As a developer debugging the dashboard, I want clear console logs showing how many sentiment points were aligned, so I can verify the overlay is working.

**Why this priority**: Observability for ongoing maintenance.

**Independent Test**: Open browser DevTools, switch resolutions, verify log messages show non-zero aligned points.

**Acceptance Scenarios**:

1. **Given** sentiment data loads successfully, **When** updateSentimentOverlay() runs, **Then** console MUST log "Updated sentiment overlay with N aligned points" where N > 0

---

### Edge Cases

- What happens when API returns empty buckets array? (Clear overlay, no error)
- What happens when bucket has no timestamp field at all? (Skip that bucket, log warning)
- What happens when OHLC and sentiment have no overlapping timestamps? (Show empty overlay, log warning)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST read `bucket.timestamp` as the primary timestamp field
- **FR-002**: System MUST fallback to `bucket.bucket_timestamp` then `bucket.SK` for backwards compatibility
- **FR-003**: System MUST align sentiment data points to OHLC candle timestamps within 1 hour tolerance
- **FR-004**: System MUST update chart dataset[1] with aligned sentiment values

### Key Entities

- **SentimentBucket**: API response with `timestamp`, `avg`, `count`, `label_counts`
- **OHLCCandle**: Price data with `date`, `open`, `high`, `low`, `close`
- **Chart.js Dataset[1]**: Sentiment overlay line data array

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sentiment overlay shows non-zero aligned points in console log
- **SC-002**: Blue sentiment line visible on Price Chart when sentiment data exists
- **SC-003**: No JavaScript errors in console related to undefined timestamp

## Technical Approach

### Fix Location

`src/dashboard/ohlc.js`, `updateSentimentOverlay()` method, line 564

### Proposed Change

```javascript
// Before (buggy)
const ts = bucket.bucket_timestamp || bucket.SK;

// After (correct)
const ts = bucket.timestamp || bucket.bucket_timestamp || bucket.SK;
```

This adds `bucket.timestamp` as the primary field, with fallbacks for any legacy data formats.
