# Implementation Plan: OHLC Pan Limits Fix

**Branch**: `1080-ohlc-pan-limits` | **Date**: 2025-12-28 | **Spec**: [spec.md](spec.md)

## Summary

Fix pan functionality by adding X-axis limits and enabling bi-directional (XY) pan mode.

## Technical Context

**Language/Version**: JavaScript (ES6+)
**Primary Dependencies**: Chart.js v4.x, chartjs-plugin-zoom
**Storage**: N/A (frontend-only fix)
**Testing**: Browser manual testing
**Target Platform**: Web browser
**Project Type**: Web application (frontend fix only)
**Scale/Scope**: Single file change (ohlc.js)

## Implementation Details

### Change 1: Add X-axis limits

Add `x` key to the `limits` object in zoom plugin configuration:

```javascript
limits: {
    x: {
        min: 'original',      // Use original data range minimum
        max: 'original',      // Use original data range maximum
        minRange: 60000       // Minimum 1 minute visible (ms)
    },
    price: { min: 'original', minRange: 5 },
    sentiment: { min: -1, max: 1, minRange: 2 }
}
```

### Change 2: Enable XY pan mode

Change `mode: 'x'` to `mode: 'xy'`:

```javascript
pan: {
    enabled: true,
    mode: 'xy',    // Allow both horizontal and vertical panning
    threshold: 5,
    modifierKey: null,
    onPanStart: ({ chart }) => { chart.canvas.style.cursor = 'grabbing'; },
    onPanComplete: ({ chart }) => { chart.canvas.style.cursor = 'grab'; }
}
```

## File Changes

- `src/dashboard/ohlc.js`: Lines ~446 (pan mode) and ~476 (limits)
