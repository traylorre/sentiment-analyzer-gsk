# Feature Specification: Price Chart Vertical Zoom

**Feature Branch**: `1070-price-chart-vertical-zoom`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Add vertical zoom-in and zoom-out functionality to Price Chart with mouse scroll-wheel, focused around where mouse is pointing, because it is very hard to interpret stock prices when zoomed-out. Zoom should work with Price (left Y-axis), Sentiment (right Y-axis) is normalized to -1 to 1 so can remain fixed."

## Problem Statement

The Price Chart displays OHLC candlestick data with a left Y-axis showing price values. When the price range is large (e.g., $100-$250), small price movements are difficult to see. Users cannot zoom in on specific price ranges to analyze price action in detail.

### Current State

- Chart displays full price range from min to max values
- No zoom functionality exists
- Users cannot focus on specific price regions
- Small percentage moves are invisible on charts with large ranges
- chartjs-plugin-zoom is NOT currently loaded in index.html

### Desired State

- Users can scroll mouse wheel to zoom in/out on Y-axis (price)
- Zoom centers around mouse cursor position
- Sentiment Y-axis (-1 to 1) remains fixed (already normalized)
- Double-click resets zoom to default view

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Zoom In on Price Range (Priority: P1)

As a trader analyzing price charts, I want to zoom in on the Y-axis (price) using my mouse scroll wheel so that I can see small price movements that are otherwise invisible when the full range is displayed.

**Why this priority**: Core purpose of the feature - without this, the Price Chart is hard to interpret for detailed analysis.

**Independent Test**: Open dashboard, hover over Price Chart, scroll mouse wheel up - chart Y-axis should zoom in around cursor position.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed with OHLC data, **When** user hovers over chart and scrolls wheel up, **Then** Y-axis (price) MUST zoom in, centered around cursor position
2. **Given** Price Chart is zoomed in, **When** user scrolls wheel down, **Then** Y-axis MUST zoom out toward original view
3. **Given** zoom is active, **When** cursor is at bottom of chart and user zooms in, **Then** zoom center MUST be at lower price levels
4. **Given** zoom is active, **When** cursor is at top of chart and user zooms in, **Then** zoom center MUST be at higher price levels

---

### User Story 2 - Reset Zoom to Default (Priority: P2)

As a trader who has zoomed into a specific price range, I want to quickly reset the zoom to see the full picture again.

**Why this priority**: Essential for workflow - users need to zoom out after detailed analysis.

**Independent Test**: Zoom into chart, then double-click to reset - chart should return to showing full price range.

**Acceptance Scenarios**:

1. **Given** Price Chart is zoomed in, **When** user double-clicks on chart, **Then** zoom MUST reset to original (full range) view
2. **Given** Price Chart is at default zoom, **When** user double-clicks, **Then** nothing should change (already at default)

---

### User Story 3 - Sentiment Axis Remains Fixed (Priority: P3)

As a dashboard user, I want the Sentiment Y-axis (right side) to remain fixed at -1 to 1 regardless of zoom, because sentiment values are already normalized.

**Why this priority**: Prevents confusion - zooming sentiment axis would make the scale meaningless.

**Independent Test**: Zoom price axis in/out, verify sentiment axis remains -1 to 1.

**Acceptance Scenarios**:

1. **Given** Price Chart with sentiment overlay, **When** user zooms price axis, **Then** sentiment Y-axis MUST remain fixed at -1.0 to 1.0
2. **Given** sentiment line is displayed, **When** price axis zooms, **Then** sentiment line position relative to its axis MUST not change

---

### Edge Cases

- What happens when chart has no data? (Zoom should be disabled or no-op)
- What happens when user zooms in extremely far? (Should have reasonable min/max limits)
- What happens on touch devices? (Pinch-to-zoom for mobile, but not blocking for MVP)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load chartjs-plugin-zoom library via CDN in index.html
- **FR-002**: System MUST enable Y-axis zoom on mouse wheel scroll
- **FR-003**: System MUST zoom centered around mouse cursor position (mode: 'y')
- **FR-004**: System MUST allow zoom reset on double-click
- **FR-005**: System MUST only zoom the 'price' Y-axis (left side)
- **FR-006**: System MUST NOT zoom the 'sentiment' Y-axis (right side, keep fixed -1 to 1)
- **FR-007**: System MUST set reasonable zoom limits (e.g., min 50%, max 1000% of original range)

### Key Entities

- **Chart.js Price Axis**: Left Y-axis showing dollar prices, subject to zoom
- **Chart.js Sentiment Axis**: Right Y-axis (-1 to 1), fixed and not zoomable
- **chartjs-plugin-zoom**: Chart.js plugin that provides zoom/pan functionality

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Mouse wheel scroll over Price Chart zooms Y-axis in/out
- **SC-002**: Zoom center follows mouse cursor position
- **SC-003**: Double-click resets zoom to full price range
- **SC-004**: Sentiment axis remains fixed at -1.0 to 1.0 during all zoom operations
- **SC-005**: No JavaScript errors in console related to zoom functionality

## Technical Approach

### Implementation Location

`src/dashboard/index.html` - Add chartjs-plugin-zoom CDN
`src/dashboard/ohlc.js` - Configure zoom options in `initChart()` method

### Proposed Change

1. Add to index.html (after chart.js):
```html
<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1/dist/chartjs-plugin-zoom.min.js"
        integrity="sha384-..."
        crossorigin="anonymous"></script>
```

2. Update ohlc.js `initChart()` options:
```javascript
options: {
  plugins: {
    zoom: {
      zoom: {
        wheel: { enabled: true },
        mode: 'y',
        scaleMode: 'y',
        // Only allow zooming the price axis
        overScaleMode: 'y'
      },
      limits: {
        y: { minRange: 10 }  // Minimum price range when zoomed in
      }
    }
  }
}
```

### Dependencies

- chartjs-plugin-zoom v2.0.1 (compatible with Chart.js 4.x)
