# Feature Specification: OHLC Plugin API Fix

**Feature Branch**: `1079-ohlc-plugin-api-fix`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Fix OHLC chart initialization error - Chart.js plugin registration check uses wrong API. Error: 'registeredPlugins.some is not a function' at ohlc.js:348. Root cause: Feature 1077 incorrectly accesses Chart.registry.plugins.items (doesn't exist in Chart.js v4.x). Fix: Use Chart.registry.getPlugin('zoom') method to check if plugin is registered."

## Problem Statement

The OHLC Price Chart fails to initialize with the error:
```
TypeError: registeredPlugins.some is not a function
    at OHLCChart.initChart (ohlc.js:348:52)
```

**Root Cause**: Feature 1077 added plugin registration check code that incorrectly assumes `Chart.registry.plugins.items` is an array. In Chart.js v4.x, the registry uses a different internal structure (Map-based), so `.items` is undefined and the fallback `|| []` doesn't work correctly.

**Buggy Code (ohlc.js:347-348)**:
```javascript
const registeredPlugins = Chart.registry?.plugins?.items || [];
const isRegistered = registeredPlugins.some(p => p.id === 'zoom');
```

## User Scenarios & Testing

### User Story 1 - OHLC Chart Renders Successfully (Priority: P1)

As a user, I want the OHLC Price Chart to load without errors, so I can view price data for selected tickers.

**Why this priority**: Without fixing this bug, the entire OHLC chart is broken and users cannot see any price data.

**Independent Test**: Load the ONE URL dashboard and verify the OHLC chart renders without console errors.

**Acceptance Scenarios**:

1. **Given** user loads the dashboard URL, **When** the page initializes, **Then** the OHLC chart renders without JavaScript errors
2. **Given** user views the browser console, **When** the page loads, **Then** no "registeredPlugins.some is not a function" error appears
3. **Given** the dashboard is loaded, **When** user selects a ticker, **Then** OHLC candles display correctly

---

### User Story 2 - Pan Functionality Works (Priority: P2)

As a user, I want to left-click and drag to pan the chart horizontally, so I can navigate through time periods.

**Why this priority**: Pan was the original goal of Feature 1077, but it was broken by the registration bug.

**Independent Test**: After chart loads, left-click-drag horizontally and verify chart pans through time.

**Acceptance Scenarios**:

1. **Given** the OHLC chart is displaying data, **When** user left-click-drags horizontally, **Then** the chart pans left/right through time
2. **Given** user hovers over the chart, **When** cursor is over chart canvas, **Then** cursor displays as "grab"
3. **Given** user is actively dragging, **When** mouse is held down, **Then** cursor displays as "grabbing"

---

### Edge Cases

- What happens if chartjs-plugin-zoom is not loaded? (Graceful degradation - chart loads without pan, warning logged)
- What happens if Chart.js is not available? (Chart initialization fails, appropriate error displayed)
- What happens if plugin is registered multiple times? (Should not error, Chart.register is idempotent)

## Requirements

### Functional Requirements

- **FR-001**: System MUST use Chart.js v4.x compatible API to check for plugin registration
- **FR-002**: System MUST use `Chart.registry.getPlugin('zoom')` method to check if zoom plugin exists
- **FR-003**: System MUST NOT use array methods on non-array Chart.js internal structures
- **FR-004**: System MUST handle graceful degradation when zoom plugin is unavailable
- **FR-005**: System MUST preserve pan functionality (left-click-drag, grab cursor) when plugin is available

## Success Criteria

### Measurable Outcomes

- **SC-001**: OHLC chart initializes without JavaScript errors on page load
- **SC-002**: Browser console shows no "registeredPlugins.some is not a function" error
- **SC-003**: Left-click-drag panning works after chart loads (horizontal time navigation)
- **SC-004**: Cursor changes to grab/grabbing during pan interactions
