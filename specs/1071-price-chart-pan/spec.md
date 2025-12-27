# Feature Specification: Price Chart Pan

**Feature Branch**: `1071-price-chart-pan`
**Created**: 2025-12-27
**Status**: Draft
**Input**: User description: "Add left-click-drag pan functionality to Price Chart for horizontal navigation along time axis"

## Problem Statement

The Price Chart displays OHLC candlestick data across a time axis. Feature 1070 added vertical zoom (Y-axis) via mouse wheel. However, users cannot navigate horizontally along the time axis to view different periods of data. When zoomed in on a specific price range, users need to pan left/right to see earlier or later data points.

### Current State

- Vertical zoom exists (Feature 1070) - mouse wheel zooms Y-axis
- No horizontal navigation capability
- Users cannot scroll through time when viewing detailed data
- Chart shows fixed time window based on resolution

### Desired State

- Users can left-click and drag to pan horizontally along the X-axis (time)
- Pan works independently of vertical zoom
- Smooth, responsive panning interaction
- Double-click still resets zoom (from Feature 1070)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pan to View Earlier Data (Priority: P1)

As a trader viewing the Price Chart at a zoomed-in level, I want to click and drag left to see earlier price data without changing my zoom level.

**Why this priority**: Core pan functionality - enables time-based navigation which is essential for detailed price analysis.

**Independent Test**: Load chart with data, left-click and drag left - chart should scroll to show earlier time periods.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed with OHLC data, **When** user left-clicks and drags left, **Then** chart MUST scroll to show earlier time periods
2. **Given** Price Chart is at earliest data point, **When** user tries to pan further left, **Then** panning MUST stop at data boundary (no empty space)
3. **Given** user is panning, **When** mouse button is released, **Then** chart position MUST remain at new location

---

### User Story 2 - Pan to View Later Data (Priority: P1)

As a trader, I want to click and drag right to see later/more recent price data.

**Why this priority**: Complements pan-left for complete horizontal navigation.

**Independent Test**: Load chart with data, left-click and drag right - chart should scroll to show later time periods.

**Acceptance Scenarios**:

1. **Given** Price Chart is displayed with OHLC data, **When** user left-clicks and drags right, **Then** chart MUST scroll to show later time periods
2. **Given** Price Chart is at latest data point, **When** user tries to pan further right, **Then** panning MUST stop at data boundary

---

### User Story 3 - Pan with Zoom Preserved (Priority: P2)

As a trader who has zoomed into a specific price range, I want panning to preserve my zoom level while I navigate time.

**Why this priority**: Ensures zoom and pan work together without conflicting.

**Independent Test**: Zoom into chart (mouse wheel), then pan left/right - Y-axis zoom level should remain unchanged.

**Acceptance Scenarios**:

1. **Given** Price Chart is zoomed in on Y-axis, **When** user pans horizontally, **Then** Y-axis zoom level MUST remain unchanged
2. **Given** user pans then zooms, **When** double-click to reset, **Then** both zoom and pan MUST reset to default view

---

### Edge Cases

- What happens when chart has no data? (Pan should be disabled or no-op)
- What happens on touch devices? (Swipe-to-pan for mobile, but not blocking for MVP)
- What happens if user right-clicks while dragging? (Should cancel pan)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST enable X-axis panning via left-click-drag
- **FR-002**: System MUST pan only along the X-axis (time), not Y-axis
- **FR-003**: System MUST limit panning to data boundaries (no panning into empty space)
- **FR-004**: System MUST preserve Y-axis zoom level during panning
- **FR-005**: Double-click MUST reset both zoom and pan to default view
- **FR-006**: Panning MUST feel smooth and responsive (no jittering)

### Key Entities

- **chartjs-plugin-zoom pan configuration**: Controls pan behavior (mode, threshold, etc.)
- **Chart.js X-axis (time)**: The axis being panned
- **Pan limits**: Boundaries that prevent panning beyond data

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Left-click-drag pans chart horizontally along time axis
- **SC-002**: Panning stops at data boundaries (cannot pan into empty space)
- **SC-003**: Y-axis zoom level remains unchanged during pan operations
- **SC-004**: Double-click resets both pan and zoom to default view
- **SC-005**: No JavaScript errors related to pan functionality

## Technical Approach

### Implementation Location

`src/dashboard/ohlc.js` - Update zoom plugin configuration to enable pan

### Proposed Change

Update the existing zoom configuration in `initChart()` to add pan:

```javascript
zoom: {
    pan: {
        enabled: true,
        mode: 'x',           // Pan only on X-axis (time)
        threshold: 5,        // Minimum pan distance before action
        modifierKey: null    // No modifier key required (plain left-click)
    },
    zoom: {
        wheel: { enabled: true, speed: 0.1 },
        mode: 'y',
        // ... existing zoom config
    },
    limits: {
        x: { minRange: 60000 },  // Minimum 1 minute visible
        // ... existing limits
    }
}
```

### Dependencies

- chartjs-plugin-zoom v2.0.1 (already loaded via CDN in index.html)
