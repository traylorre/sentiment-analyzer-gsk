# Feature Specification: Price Chart Interaction Fixes

**Feature Branch**: `1073-price-chart-interaction-fixes`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Fix Price Chart interaction issues discovered in Features 1070, 1071, 1072"

## Problem Statement

Three Price Chart features were implemented but not working correctly:

1. **Feature 1071 (Pan)**: Left-click-drag panning does nothing
   - **Root Cause**: Hammer.js library is required by chartjs-plugin-zoom for gesture/drag recognition but is not loaded

2. **Feature 1072 (Auto-fit)**: Chart zooms from $0 to highest value instead of lowest-to-highest
   - **Root Cause**: `limits.price.min: 0` prevents the chart from showing values below $0, forcing all zooms to floor at $0

3. **Feature 1070 (Sentiment Axis)**: Sentiment Y-axis (-1 to +1) breaks when zooming
   - **Root Cause**: The `onZoom` callback attempts to restore sentiment bounds, but the limits configuration doesn't include the sentiment scale

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pan Navigation Works (Priority: P1)

As a trader viewing the Price Chart, I want to left-click-drag to pan horizontally along the time axis so I can navigate through historical price data.

**Why this priority**: Core interaction - pan is the primary way to navigate time series data.

**Independent Test**: Load dashboard, left-click and drag on the Price Chart, chart should scroll horizontally.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed with data, **When** user left-clicks and drags horizontally, **Then** chart MUST pan along the X-axis (time)
2. **Given** user has panned the chart, **When** user releases mouse, **Then** chart MUST stay at the panned position
3. **Given** chart is panned, **When** user double-clicks, **Then** chart MUST reset to show all data

---

### User Story 2 - Auto-Fit Shows Full Data Range (Priority: P1)

As a trader switching between time resolutions, I want the chart to auto-fit to show the full price range (from lowest to highest value) so I can immediately see all price action.

**Why this priority**: Essential for demo - users need to see all data without manual adjustment.

**Independent Test**: Load dashboard or change resolution, chart Y-axis should span from slightly below lowest price to slightly above highest price.

**Acceptance Scenarios**:

1. **Given** OHLC data with prices between $100-$150, **When** chart loads or resolution changes, **Then** Y-axis MUST show range approximately $100-$150 (NOT $0-$150)
2. **Given** OHLC data with prices between $0.50-$1.00 (penny stock), **When** chart loads, **Then** Y-axis MUST show range approximately $0.50-$1.00
3. **Given** chart is zoomed in, **When** user changes resolution, **Then** chart MUST reset zoom and auto-fit to new data range

---

### User Story 3 - Sentiment Axis Stays Fixed (Priority: P2)

As a trader using the sentiment overlay, I want the right Y-axis (Sentiment) to always stay fixed at -1.0 to +1.0 so I can accurately interpret sentiment values regardless of zoom level.

**Why this priority**: Visual accuracy - sentiment values only make sense in -1 to +1 context.

**Independent Test**: Zoom in/out on Price Chart, right Y-axis should always show -1.0 to +1.0.

**Acceptance Scenarios**:

1. **Given** Price Chart with sentiment overlay, **When** user zooms via scroll wheel, **Then** sentiment axis MUST remain at -1.0 to +1.0
2. **Given** user has zoomed multiple times, **When** viewing sentiment axis, **Then** axis MUST still show -1.0 to +1.0
3. **Given** chart is zoomed, **When** user double-clicks to reset, **Then** sentiment axis MUST still be -1.0 to +1.0

---

### Edge Cases

- What if price data has only one value (flat line)? Auto-fit should show a reasonable range around that value
- What if all prices are exactly $0 (unlikely but possible test case)? Chart should handle gracefully
- What if user zooms very aggressively on price axis? Should respect minRange: 5 limit

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load Hammer.js library before chartjs-plugin-zoom for gesture recognition
- **FR-002**: System MUST configure pan with mode 'x' for horizontal time navigation
- **FR-003**: System MUST NOT set a hard minimum of $0 on the price axis limits
- **FR-004**: System MUST use 'original' keyword or remove min limit to allow auto-fit to data range
- **FR-005**: System MUST configure sentiment axis limits to fixed min: -1, max: 1
- **FR-006**: System MUST call chart.resetZoom() on data load to auto-fit
- **FR-007**: System MUST preserve double-click reset functionality

### Key Entities

- **Hammer.js**: Touch/gesture recognition library required by chartjs-plugin-zoom for pan
- **chartjs-plugin-zoom limits**: Configuration for min/max per scale axis
- **Chart.js scales**: price (left Y-axis) and sentiment (right Y-axis)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Left-click-drag on Price Chart results in visible horizontal panning
- **SC-002**: Chart Y-axis on load shows data range (lowest-highest), not $0-highest
- **SC-003**: Sentiment axis shows -1.0 to +1.0 at all times regardless of zoom level
- **SC-004**: Double-click resets zoom and shows full data range
- **SC-005**: No JavaScript console errors related to chart interactions
- **SC-006**: All existing chart functionality (tooltip, resolution selector) continues to work

## Technical Approach

### Changes Required

1. **index.html** - Add Hammer.js CDN before chartjs-plugin-zoom:
```html
<script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8/hammer.min.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

2. **ohlc.js** - Fix limits configuration:
```javascript
limits: {
    price: {
        min: 'original',  // Use original data range, not $0
        minRange: 5       // Keep minimum $5 range when zoomed in
    },
    sentiment: {
        min: -1,
        max: 1,
        minRange: 2       // Full -1 to 1 range always
    }
}
```

### Dependencies

- Hammer.js v2.0.8 (CDN)
- chartjs-plugin-zoom v2.0.1 (already loaded)
