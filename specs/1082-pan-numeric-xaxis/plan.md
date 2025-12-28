# Implementation Plan: Fix OHLC Pan with Numeric X-Axis

**Branch**: `1082-pan-numeric-xaxis` | **Date**: 2025-12-28 | **Spec**: [spec.md](spec.md)

## Summary

Convert OHLC chart X-axis from categorical string labels to numeric epoch milliseconds to enable chartjs-plugin-zoom pan calculations.

## Technical Context

**Language/Version**: JavaScript (ES6+)
**Primary Dependencies**: Chart.js v4.x, chartjs-plugin-zoom v2.0.1
**Storage**: N/A (frontend-only fix)
**Testing**: Static analysis unit tests + browser manual testing
**Target Platform**: Web browser
**Scale/Scope**: Single file change (ohlc.js)

## Implementation Details

### Change 1: Update X-axis Scale Configuration

Configure X-axis as time scale with numeric values:

```javascript
scales: {
    x: {
        type: 'time',           // Use time scale for numeric handling
        time: {
            unit: 'auto',       // Auto-detect based on data range
            displayFormats: {
                minute: 'HH:mm',
                hour: 'HH:mm',
                day: 'MMM d'
            }
        },
        ticks: {
            source: 'data',     // Generate ticks from data points
            autoSkip: true,
            maxRotation: 0,
            callback: function(value, index, ticks) {
                // Custom formatting based on resolution
                return this.chart.options.plugins.ohlcChart.formatLabel(value);
            }
        }
    }
}
```

### Change 2: Convert Data to Numeric X Values

Update `updateChart()` data generation:

```javascript
// Before (categorical string):
const data = candles.map((c, i) => ({
    x: this.formatTimestamp(c.date, i, candles),
    y: [c.low, c.high],
    ohlc: {...}
}));

// After (numeric epoch ms):
const data = candles.map((c, i) => ({
    x: new Date(c.date).getTime(),  // Numeric timestamp
    y: [c.low, c.high],
    ohlc: {...},
    dateStr: c.date  // Keep original for formatting
}));
```

### Change 3: Update Limits to Use Numeric Bounds

Update zoom plugin limits:

```javascript
limits: {
    x: {
        min: data[0].x,                           // First candle timestamp
        max: data[data.length - 1].x,             // Last candle timestamp
        minRange: 60000                           // 1 minute in ms
    },
    price: { min: 'original', minRange: 5 },
    sentiment: { min: -1, max: 1, minRange: 2 }
}
```

### Change 4: Update Tooltip for Numeric X Values

Modify tooltip callbacks to format numeric timestamps:

```javascript
tooltip: {
    callbacks: {
        title: (items) => {
            const timestamp = items[0].raw.x;
            return new Date(timestamp).toLocaleString('en-US', {
                weekday: 'short',
                month: 'numeric',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        },
        label: (context) => { /* existing OHLC values */ }
    }
}
```

## File Changes

- `src/dashboard/ohlc.js`: Lines ~370 (scales config), ~600 (data generation), ~480 (limits), ~420 (tooltip)

## Dependencies

- Chart.js time scale adapter: `chartjs-adapter-date-fns` or inline handling
- May need to add adapter to index.html if not already present
