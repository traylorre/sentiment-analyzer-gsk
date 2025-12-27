# Feature Specification: Price Chart Zoom Refinements

**Feature Branch**: `1072-price-chart-zoom-refinements`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Price Chart zoom refinements: 1) Auto-fit data on resolution change, 2) Remove legend, 3) Set min price to $0 when zooming out"

## Problem Statement

The Price Chart has vertical zoom (Feature 1070) and horizontal pan (Feature 1071), but needs refinements for a polished demo experience:

1. When switching resolutions or on first load, the chart should auto-fit all data in the visible area
2. The chart legend takes up space and is unnecessary since the chart title already shows the ticker
3. When zooming out, users can currently zoom past $0 which shows negative prices (impossible for stocks)

### Current State

- Chart loads with Chart.js default scale behavior
- Legend is displayed at the top showing "Price" and "Sentiment" labels
- No minimum price limit when zooming out (can show negative values)

### Desired State

- Chart auto-fits to show all data within the visible area on load and resolution change
- No legend displayed (cleaner, more professional appearance)
- Price Y-axis cannot go below $0 when zooming out

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Auto-Fit on Resolution Change (Priority: P1)

As a trader switching between time resolutions (1m, 5m, 1h, etc.), I want the chart to automatically fit all data in view so I can immediately see the full price range.

**Why this priority**: Core demo experience - users should see all data without manual zoom adjustments.

**Independent Test**: Select a different resolution, chart should display full price range of new data.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed, **When** user selects a new resolution, **Then** chart MUST auto-fit Y-axis to show full price range of new data
2. **Given** dashboard first loads, **When** OHLC data is fetched, **Then** chart MUST auto-fit Y-axis to show all candles
3. **Given** chart is zoomed in, **When** user changes resolution, **Then** zoom MUST reset and chart auto-fits new data

---

### User Story 2 - Remove Legend (Priority: P2)

As a dashboard user, I want a cleaner chart without the legend taking up space, since the chart title already shows what I'm viewing.

**Why this priority**: Visual polish - legend is redundant with chart title "Price Chart AAPL".

**Independent Test**: Load dashboard, chart should display without legend at the top.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed, **When** user views the chart, **Then** no legend should be visible
2. **Given** legend is hidden, **When** user hovers over data, **Then** tooltip should still show Price and Sentiment values

---

### User Story 3 - $0 Price Floor on Zoom Out (Priority: P2)

As a trader zooming out to see more price context, I want the chart to stop at $0 since stock prices cannot be negative.

**Why this priority**: Prevents confusing display of impossible price values.

**Independent Test**: Zoom out fully on Price Chart, Y-axis minimum should be $0.

**Acceptance Scenarios**:

1. **Given** Price Chart is zoomed to show price data, **When** user zooms out via scroll wheel, **Then** Y-axis minimum MUST NOT go below $0
2. **Given** price data range is $100-$150, **When** user zooms out fully, **Then** Y-axis should show range like $0-$200 (not -$50 to $200)

---

### Edge Cases

- What if price data is very low (e.g., penny stock at $0.50)? Y-axis should still start at $0
- What if all candles have same price? Auto-fit should show a reasonable range around that price

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST auto-fit chart Y-axis to data range on initial load
- **FR-002**: System MUST auto-fit chart Y-axis when resolution changes
- **FR-003**: System MUST reset zoom when loading new data
- **FR-004**: System MUST NOT display chart legend
- **FR-005**: System MUST maintain tooltip functionality showing Price and Sentiment values
- **FR-006**: System MUST enforce $0 as minimum Y-axis value when zooming out
- **FR-007**: Sentiment Y-axis MUST remain fixed at -1 to 1 (already implemented in Feature 1070)

### Key Entities

- **Chart.js legend plugin**: Disabled via `display: false`
- **Chart.js price scale limits**: Configure `min: 0` in zoom limits
- **Chart.resetZoom()**: Called after data load to reset view

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Chart displays full data range on initial load without manual zoom
- **SC-002**: Resolution change resets zoom and shows full new data range
- **SC-003**: No legend visible on Price Chart
- **SC-004**: Tooltip still works when hovering over chart
- **SC-005**: Y-axis never shows negative price values when zooming out
- **SC-006**: No JavaScript console errors related to chart operations

## Technical Approach

### Implementation Location

`src/dashboard/ohlc.js` - Update chart configuration

### Proposed Changes

1. **Disable legend**:
```javascript
legend: {
    display: false  // Feature 1072: Remove legend for cleaner display
}
```

2. **Add $0 floor to zoom limits**:
```javascript
limits: {
    price: {
        min: 0,        // Feature 1072: Price cannot go below $0
        minRange: 5    // Existing: Minimum $5 range when zoomed in
    }
}
```

3. **Reset zoom on data load** (in `updateChart` method):
```javascript
// Reset zoom to show all new data
if (this.chart) {
    this.chart.resetZoom();
}
```

### Dependencies

- chartjs-plugin-zoom v2.0.1 (already loaded)
