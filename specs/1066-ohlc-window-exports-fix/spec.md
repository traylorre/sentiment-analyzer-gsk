# Feature 1066: Fix Missing Window Exports in ohlc.js

## Problem Statement

The OHLC chart and unified resolution selector are broken in production. Resolution buttons render but do not function, and the OHLC chart never initializes.

### Root Cause

In `src/dashboard/ohlc.js`, the functions `initOHLCChart` and `updateOHLCTicker` are defined (lines 628-655) but NOT exported to the window object. The window exports at lines 721-724 only export 3 of 5 required functions:

```javascript
// Currently exported (lines 721-724):
window.setOHLCResolution = setOHLCResolution;
window.hideOHLCResolutionSelector = hideOHLCResolutionSelector;
window.loadOHLCSentimentOverlay = loadOHLCSentimentOverlay;

// Missing exports:
// window.initOHLCChart = initOHLCChart;      // NOT EXPORTED
// window.updateOHLCTicker = updateOHLCTicker; // NOT EXPORTED
```

### Impact

In `app.js`, the typeof guards silently fail:
- Line 283: `if (typeof initOHLCChart === 'function')` → returns false
- Line 321: `if (typeof updateOHLCTicker === 'function')` → returns false

Result: OHLC chart never initializes, resolution buttons render but do nothing.

## Requirements

### R01: Export initOHLCChart to window
The `initOHLCChart` function must be exported to the window object so `app.js` can call it during session initialization.

### R02: Export updateOHLCTicker to window
The `updateOHLCTicker` function must be exported to the window object so `app.js` and `timeseries.js` can call it when the ticker changes.

### R03: Maintain backward compatibility
Existing exports (`setOHLCResolution`, `hideOHLCResolutionSelector`, `loadOHLCSentimentOverlay`) must continue to work.

### R04: Verify integration with app.js
After adding exports, the typeof guards in `app.js` lines 283 and 321 should evaluate to true, and the chart should initialize on page load.

## Test Requirements

### T01: Verify initOHLCChart export exists
After loading ohlc.js, `window.initOHLCChart` should be a function.

### T02: Verify updateOHLCTicker export exists
After loading ohlc.js, `window.updateOHLCTicker` should be a function.

### T03: Verify chart initialization flow
When `initOHLCChart('AAPL')` is called, it should:
- Render the OHLC chart container
- Fetch data from the API
- Display candlestick chart

### T04: Verify ticker update flow
When `updateOHLCTicker('MSFT')` is called, it should:
- Update the chart's ticker
- Fetch new data
- Re-render the chart

## Implementation

### File: src/dashboard/ohlc.js

Add the missing exports after line 724:

```javascript
// Export functions for external use
window.setOHLCResolution = setOHLCResolution;
window.hideOHLCResolutionSelector = hideOHLCResolutionSelector;
window.loadOHLCSentimentOverlay = loadOHLCSentimentOverlay;
window.initOHLCChart = initOHLCChart;           // ADD THIS
window.updateOHLCTicker = updateOHLCTicker;     // ADD THIS
```

## Verification

1. Load the dashboard in a browser
2. Open console and verify:
   - `typeof window.initOHLCChart === 'function'` → true
   - `typeof window.updateOHLCTicker === 'function'` → true
3. Verify OHLC chart renders with candlesticks
4. Verify resolution buttons update the chart
5. Verify ticker input changes the chart symbol

## Related Features

- Feature 1057: Dashboard OHLC Chart (original implementation)
- Feature 1064: Unified Resolution Selector (added window.setOHLCResolution)
- Feature 1065: Sentiment-Price Overlay (added window.loadOHLCSentimentOverlay)
