# Implementation Plan: OHLC Time Axis Formatting Fix

**Branch**: `1081-time-axis-formatting` | **Date**: 2025-12-28 | **Spec**: [spec.md](spec.md)

## Summary

Fix time axis formatting to include date context for multi-day intraday data by detecting day boundaries and showing abbreviated dates for first candle of each day.

## Technical Context

**Language/Version**: JavaScript (ES6+)
**Primary Dependencies**: Chart.js v4.x
**Storage**: N/A (frontend-only fix)
**Testing**: Static analysis unit tests + browser manual testing
**Target Platform**: Web browser
**Project Type**: Web application (frontend fix only)
**Scale/Scope**: Single file change (ohlc.js)

## Implementation Details

### Change 1: Track Day Boundaries in Labels

Modify `formatTimestamp()` to accept candle index and detect day transitions:

```javascript
/**
 * Format timestamp for chart label with day context
 * @param {string} timestamp - ISO timestamp
 * @param {number} index - Candle index in data array
 * @param {Array} candles - All candles for day boundary detection
 */
formatTimestamp(timestamp, index, candles) {
    const date = new Date(timestamp);
    const resolution = this.currentResolution;

    if (resolution === 'D') {
        // Day resolution: "Dec 23" format
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    // Check if this is first candle of a new day
    const isFirstOfDay = index === 0 || this.isDifferentDay(candles[index - 1].date, timestamp);

    if (isFirstOfDay) {
        // Show abbreviated date: "Mon 12/23"
        const weekday = date.toLocaleDateString('en-US', { weekday: 'short' });
        const monthDay = `${date.getMonth() + 1}/${date.getDate()}`;
        return `${weekday} ${monthDay}`;
    }

    // Same day: show time only
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

/**
 * Check if two timestamps are on different calendar days
 */
isDifferentDay(timestamp1, timestamp2) {
    const d1 = new Date(timestamp1);
    const d2 = new Date(timestamp2);
    return d1.toDateString() !== d2.toDateString();
}
```

### Change 2: Pass Candle Context to Formatter

Update `updateChart()` to pass index and candles array:

```javascript
const labels = candles.map((c, index) => this.formatTimestamp(c.date, index, candles));
```

## File Changes

- `src/dashboard/ohlc.js`: Lines ~597 (labels generation), ~743 (formatTimestamp method)

## Testing

Add static analysis tests in `tests/unit/dashboard/test_time_axis_formatting.py`:
- Test `isDifferentDay` method exists
- Test `formatTimestamp` handles day boundaries
- Test Feature 1081 comment exists for traceability
