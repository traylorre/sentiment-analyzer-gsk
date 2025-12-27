# Plan: Feature 1066 - Fix Missing Window Exports in ohlc.js

## Overview

Add missing window exports for `initOHLCChart` and `updateOHLCTicker` functions in `src/dashboard/ohlc.js`.

## Implementation Steps

### Step 1: Add Missing Window Exports

**File**: `src/dashboard/ohlc.js`
**Location**: After line 724

**Change**:
```javascript
// Export functions for external use
window.setOHLCResolution = setOHLCResolution;
window.hideOHLCResolutionSelector = hideOHLCResolutionSelector;
window.loadOHLCSentimentOverlay = loadOHLCSentimentOverlay;
window.initOHLCChart = initOHLCChart;           // NEW
window.updateOHLCTicker = updateOHLCTicker;     // NEW
```

### Step 2: Verify app.js Integration

**File**: `src/dashboard/app.js`
**Lines**: 283, 321

Confirm these typeof guards will now pass:
- Line 283: `if (typeof initOHLCChart === 'function')` → true after fix
- Line 321: `if (typeof updateOHLCTicker === 'function')` → true after fix

No changes needed to app.js - the guards are correct.

## Files Changed

| File | Change |
|------|--------|
| `src/dashboard/ohlc.js` | Add 2 window exports at end of file |

## Testing

1. **Unit**: Verify window exports exist (future Feature 1067)
2. **Manual**: Load dashboard, verify OHLC chart renders
3. **Manual**: Verify resolution buttons change chart
4. **Manual**: Verify ticker input updates chart

## Risk Assessment

- **Low risk**: Simple additive change (2 lines)
- **No API changes**: Only window exports added
- **Backward compatible**: Existing functionality unchanged

## Definition of Done

- [ ] `window.initOHLCChart` is exported
- [ ] `window.updateOHLCTicker` is exported
- [ ] OHLC chart renders on dashboard load
- [ ] Resolution buttons update the chart
- [ ] All existing tests pass
