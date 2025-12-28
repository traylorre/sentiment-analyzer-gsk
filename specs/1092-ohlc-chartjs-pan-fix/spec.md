# Feature 1092: OHLC Chart.js Comprehensive Fixes

## Problem Statement

The OHLC price chart in the Dashboard Lambda (`src/dashboard/ohlc.js`) had multiple issues:

1. **X-axis panning not working** - Pan gestures had no effect
2. **1d view shows Sun-Thu instead of Mon-Fri** - Weekday display off by one day
3. **5min/1min candlesticks invisible** - Bars not rendering despite data loading
4. **Double-click reset error** - Console errors when clicking empty chart areas
5. **1hr resolution gaps** - Addressed by time unit configuration

## Root Cause Analysis

### Issue 1: Pan Not Working

**Root Cause**: The `limits.x` config used `'original'` keyword which is evaluated at chart creation time when no data exists, resulting in undefined/invalid limits that block pan operations.

**Fix**: Remove `'original'` keyword from initial limits config. Set explicit numeric limits only in `updateChart()` after data loads.

### Issue 2: Weekday Off by One Day

**Root Cause**: JavaScript's `new Date("2024-12-27")` parses date-only strings as midnight **UTC**. When displayed in local timezone (e.g., PST = UTC-8), this shows as the previous day.

**Fix**: Append `"T00:00:00"` to date-only strings to force local time interpretation: `new Date("2024-12-27T00:00:00")`.

### Issue 3: Invisible Candlesticks

**Root Cause**: `chart.resetZoom()` was called after setting scale min/max, but the zoom plugin stores "original" values at chart creation (before data exists). `resetZoom()` restored scales to those invalid original values.

**Fix**: Update `chart.scales.{x,price}.originalOptions` with correct min/max before calling update, ensuring `resetZoom()` uses current data range.

### Issue 4: Double-Click Console Error

**Root Cause**: Tooltip title callback accessed `item.raw.x` or `item.raw.dateStr` without null checks, causing errors when clicking empty chart areas where no data point exists.

**Fix**: Add guards for `!item || !item.raw` and wrap in try/catch to gracefully handle missing data.

## Changes Made

### `src/dashboard/ohlc.js`

1. **Limits Config** (lines 498-516):
   - Removed `min: 'original'` and `max: 'original'` from `limits.x` and `limits.price`
   - Kept only `minRange` constraints

2. **Date Parsing Helper** (lines 652-659):
   - Added `parseDate()` function that appends `T00:00:00` to date-only strings
   - Applied to both `updateChart()` and `updateSentimentOverlay()` functions

3. **Scale Original Options** (lines 708-717):
   - Update `chart.scales.x.originalOptions` and `chart.scales.price.originalOptions`
   - Ensures `resetZoom()` resets to correct data-derived limits

4. **Tooltip Null Checks** (lines 417-441):
   - Added `if (!item || !item.raw) return ''` guard
   - Wrapped timestamp parsing in try/catch

## Acceptance Criteria

1. **Pan Works**: Click and drag horizontally scrolls time axis
2. **Weekdays Correct**: Daily view shows Mon-Fri for trading week
3. **Candlesticks Visible**: All resolutions display visible bars
4. **No Console Errors**: Double-click and empty area clicks produce no errors
5. **Zoom Reset Works**: Double-click resets to data range, not stale values

## Test Plan

### Manual Testing

1. Load dashboard at `<dashboard-lambda-url>`
2. Select 1D resolution - verify Mon-Fri weekdays
3. Select 5m resolution - verify candlesticks visible
4. Select 1m resolution - verify candlesticks visible
5. Click and drag horizontally - verify pan works
6. Double-click - verify zoom resets, no console errors
7. Click empty chart area - verify no console errors

## Dependencies

- chartjs-plugin-zoom v2.0.1
- Hammer.js v2.0.8
- Chart.js v4.4.0
- chartjs-adapter-date-fns v3.0.0

## References

- [chartjs-plugin-zoom Options](https://www.chartjs.org/chartjs-plugin-zoom/latest/guide/options.html)
- [GitHub Issue #940: Pan not working](https://github.com/chartjs/chartjs-plugin-zoom/issues/940)
- [GitHub Discussion #871: Time scale min/max](https://github.com/chartjs/chartjs-plugin-zoom/discussions/871)
- [GitHub Issue #95: resetZoom not restoring original](https://github.com/chartjs/chartjs-plugin-zoom/issues/95)
