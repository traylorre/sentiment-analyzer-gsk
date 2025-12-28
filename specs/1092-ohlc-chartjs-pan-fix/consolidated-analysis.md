# Consolidated Analysis: OHLC Chart.js Issues

## Issue Summary

| # | Issue | Resolution | Status |
|---|-------|------------|--------|
| 1 | 1hr resolution gaps | Time unit config | To investigate |
| 2 | 1d shows Sun-Thu | Weekday format/data | To investigate |
| 3 | 5min invisible candlesticks | Scale min/max | To investigate |
| 4 | 1min invisible candlesticks | Same as #3 | To investigate |
| 5 | Double-click reset error | Console error | To investigate |
| 6 | X-axis pan not working | Plugin limits | Root cause found |

## Issue 1: 1hr Resolution X-Axis Gaps

### Symptoms
- Chart shows gaps/empty space between hourly candlesticks
- X-axis labels may be misaligned

### Potential Causes
1. **Time unit mismatch**: Time scale set to `minute` when data is hourly
2. **Missing data points**: Market closed periods showing as gaps
3. **Spacing calculation**: `offset: true` combined with `source: 'data'` may cause issues

### To Investigate
- Check if `time.unit` is correctly set to `'hour'` for 60-minute resolution
- Verify data points are at consistent 1-hour intervals

## Issue 2: 1D View Shows Sunday-Thursday

### Symptoms
- Daily chart shows weekdays Sun-Thu instead of Mon-Fri
- This is backwards from normal trading week

### Potential Causes
1. **Timezone conversion**: Tiingo API returns UTC dates, browser displays in local time
   - If user is in UTC-8 (PST), a date like "2024-12-27T00:00:00Z" (Friday UTC) displays as "Dec 26 Thu" (Thursday PST)
2. **Date formatting**: The `EEE` format in `displayFormats.day` uses local timezone
3. **Data ordering**: Candles might be coming in reverse order

### To Investigate
- Check how dates are parsed: `new Date(c.date).getTime()`
- Check if ISO strings include timezone offset
- Verify Tiingo API date format

### Likely Root Cause
When Tiingo returns `"2024-12-27T00:00:00Z"` (Friday in UTC), JavaScript's `new Date()` converts to local time:
- UTC-8: Dec 26 16:00 (Thursday display)
- This explains Sun-Thu instead of Mon-Fri

## Issue 3 & 4: 5min/1min Invisible Candlesticks

### Symptoms
- Candlestick bars not visible at all
- Hovering shows values in tooltip, but no visual bars

### Potential Causes
1. **Scale min/max too wide**: Price scale range is much larger than data range
2. **barThickness too small**: Pixels allocated per bar approaches zero
3. **X-axis range too wide**: All candles crammed into tiny area
4. **Data loading timing**: Chart renders before data arrives

### Analysis
The current code sets:
```javascript
this.chart.options.scales.x.min = xMin;
this.chart.options.scales.x.max = xMax;
```

But for 1min data (e.g., 120 candles over 2 hours), the time range is:
- 2 hours = 7,200,000 ms
- Each candle = 60,000 ms

If the scale is set correctly, 120 candles at `barThickness: 'flex'` should be visible.

### To Investigate
- Check actual data length for 1min/5min resolutions
- Verify `xMin` and `xMax` values
- Check if `minBarLength: 2` is being applied

## Issue 5: Double-Click Reset Zoom Console Error

### Symptoms
- Double-clicking to reset zoom works (chart resets)
- Console shows an error (only in 1D view, clicking outside data points)

### Potential Causes
1. **Tooltip callback error**: Accessing undefined property
2. **Scale access error**: Trying to read scale during reset
3. **Event handling**: Double-click fires event on empty area

### To Investigate
- Get exact error message from browser console
- Check if error is in `resetZoom()` or in Chart.js event handler
- Check tooltip label callback for null handling

## Issue 6: X-Axis Pan Not Working

### Root Cause (Confirmed)
The `limits.x` config uses `'original'` keyword which evaluates at chart creation when no data exists, resulting in invalid (undefined/0) limits that block pan operations.

### Solution
Remove `'original'` keyword from initial config. Set explicit limits only in `updateChart()` after data loads.

## Recommended Approach

### Phase 1: Fix Pan (Issue 6)
1. Remove `'original'` from limits.x config
2. Keep `minRange: 60000` for minimum zoom level
3. Set explicit min/max in updateChart with buffer

### Phase 2: Fix Visibility (Issues 3 & 4)
1. Verify data is loading correctly
2. Ensure scale.x.min/max are set appropriately for data range
3. Test with console logging to verify values

### Phase 3: Fix Timezone (Issue 2)
1. Parse dates with explicit UTC handling
2. Use `toLocaleDateString` with UTC timezone for consistent display
3. Or: Adjust Tiingo response to use trading date, not timestamp

### Phase 4: Fix Time Unit (Issue 1)
1. Verify `time.unit` is correctly set per resolution
2. Check if gaps are in data or just in display

### Phase 5: Fix Console Error (Issue 5)
1. Get exact error message
2. Add null checks to relevant callbacks
