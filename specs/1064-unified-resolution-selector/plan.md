# Implementation Plan: Unified Resolution Selector

**Branch**: `1064-unified-resolution-selector` | **Date**: 2025-12-26 | **Spec**: [spec.md](./spec.md)

## Summary

Create a single unified resolution selector that controls both OHLC price chart and sentiment trend chart. Remove duplicate resolution selectors from individual charts and add intelligent fallback mapping for non-overlapping resolutions.

## Technical Context

**Language/Version**: JavaScript ES6+ (vanilla JS dashboard)
**Primary Dependencies**: Chart.js 4.4.0
**Storage**: sessionStorage for resolution persistence
**Target Platform**: AWS Lambda (static file serving)
**Project Type**: Web application (frontend-only change)

## Files to Modify

```text
src/dashboard/
├── config.js              # MODIFY: Add UNIFIED_RESOLUTIONS config
├── unified-resolution.js  # NEW: Unified resolution selector component
├── ohlc.js               # MODIFY: Remove local selector, add resolution callback
├── timeseries.js         # MODIFY: Remove local selector, add resolution callback
├── app.js                # MODIFY: Initialize unified selector
├── index.html            # MODIFY: Add unified selector container
└── styles.css            # MODIFY: Add unified selector styles
```

## Implementation Tasks

### Task 1: Add Unified Resolution Config (config.js)

Add the resolution mapping configuration to `config.js`:

```javascript
// Unified resolution mapping - maps user selection to chart-specific values
UNIFIED_RESOLUTIONS: [
  { key: '1m', label: '1m', ohlc: '1', sentiment: '1m' },
  { key: '5m', label: '5m', ohlc: '5', sentiment: '5m' },
  { key: '10m', label: '10m', ohlc: '15', sentiment: '10m' },
  { key: '15m', label: '15m', ohlc: '15', sentiment: '10m' },
  { key: '30m', label: '30m', ohlc: '30', sentiment: '1h' },
  { key: '1h', label: '1h', ohlc: '60', sentiment: '1h' },
  { key: '3h', label: '3h', ohlc: '60', sentiment: '3h' },
  { key: '6h', label: '6h', ohlc: 'D', sentiment: '6h' },
  { key: '12h', label: '12h', ohlc: 'D', sentiment: '12h' },
  { key: 'D', label: 'Day', ohlc: 'D', sentiment: '24h' },
],
DEFAULT_UNIFIED_RESOLUTION: '1h',
```

### Task 2: Create Unified Resolution Component (unified-resolution.js)

Create new component with:
- Render resolution button group
- Handle click events
- Persist to sessionStorage
- Fire callbacks to update both charts
- Show fallback indicators when mappings differ

### Task 3: Modify OHLC Chart (ohlc.js)

- Remove internal resolution selector rendering
- Export `setResolution(ohlcResolution)` method
- Add fallback indicator display when resolution was mapped
- Update initialization to accept external resolution

### Task 4: Modify Timeseries Chart (timeseries.js)

- Remove internal resolution selector rendering (currently at lines 160-181)
- Export `setResolution(sentimentResolution)` method
- Keep ticker input (not part of unification)
- Update initialization to accept external resolution

### Task 5: Update HTML (index.html)

Add unified resolution selector container above charts:

```html
<section id="unified-controls" class="unified-controls">
  <div id="unified-resolution-selector" class="unified-resolution-selector">
    <!-- Populated by unified-resolution.js -->
  </div>
</section>
```

### Task 6: Update Styles (styles.css)

Add styles for:
- Unified controls section
- Resolution button group
- Active button state
- Fallback indicator badge

### Task 7: Update App Initialization (app.js)

- Initialize unified resolution selector first
- Pass resolution callbacks to OHLC and Timeseries initializers
- Remove any old resolution selector initialization

## Testing Checklist

- [ ] Single resolution selector visible on page load
- [ ] Clicking 5m updates both charts to 5-minute data
- [ ] Clicking 1h updates both charts to 1-hour data
- [ ] Clicking 15m shows OHLC 15m, sentiment 10m with indicator
- [ ] Resolution persists across page refresh
- [ ] No console errors during resolution switching
- [ ] Charts load within 3 seconds of resolution change
