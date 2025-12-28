# Feature Specification: Fix OHLC Pan with Numeric X-Axis

**Feature Branch**: `1082-pan-numeric-xaxis`
**Created**: 2025-12-28
**Status**: Draft
**Input**: Fix OHLC pan by converting X-axis from categorical strings to numeric timestamps

## Problem Statement

The OHLC chart has pan functionality configured (Feature 1080), and the cursor correctly changes to grab/grabbing on hover/drag, but horizontal pan (left-right) does not actually move the chart.

**Root Cause**: chartjs-plugin-zoom requires numeric X-axis values to calculate pan boundaries and offsets. The current implementation uses categorical string labels (e.g., "Mon 12/23", "10:30") which the plugin cannot process for pan calculations.

## User Scenarios & Testing

### User Story 1 - Horizontal Pan Navigation (Priority: P1)

A trader viewing multi-day OHLC data wants to pan left and right to navigate through time, seeing earlier or later candles without changing the resolution.

**Why this priority**: Core chart interaction - users expect left-click-drag to pan the chart horizontally.

**Independent Test**: Load 7-day chart, click and drag left. Chart should scroll to show earlier candles.

**Acceptance Scenarios**:

1. **Given** a multi-day OHLC chart is displayed, **When** user clicks and drags left, **Then** chart pans to show earlier time periods
2. **Given** a multi-day OHLC chart is displayed, **When** user clicks and drags right, **Then** chart pans to show later time periods
3. **Given** user has panned the chart, **When** user double-clicks, **Then** chart resets to original view

---

### User Story 2 - Vertical Pan After Zoom (Priority: P2)

A trader who has zoomed in on the Y-axis (price) wants to pan vertically to see different price ranges.

**Why this priority**: Complements horizontal pan for complete navigation.

**Independent Test**: Zoom in with mouse wheel, then drag up/down. Chart should pan vertically.

**Acceptance Scenarios**:

1. **Given** user has zoomed in on price axis, **When** user drags up, **Then** chart pans to show higher prices
2. **Given** user has zoomed in on price axis, **When** user drags down, **Then** chart pans to show lower prices

---

### Edge Cases

- Pan should stop at data boundaries (can't pan past first or last candle)
- Pan threshold (5 pixels) prevents accidental panning
- Sentiment axis (-1 to 1) should remain fixed during pan

## Requirements

### Functional Requirements

- **FR-001**: X-axis data values MUST use numeric epoch milliseconds instead of formatted strings
- **FR-002**: X-axis labels MUST continue to display formatted dates/times (visual unchanged)
- **FR-003**: Pan limits MUST use numeric boundaries based on actual data timestamps
- **FR-004**: Chart.js tick callbacks MUST format numeric values for display
- **FR-005**: Tooltip MUST display formatted date/time from numeric values

## Success Criteria

### Measurable Outcomes

- **SC-001**: Horizontal pan works - dragging left/right moves the chart through time
- **SC-002**: Vertical pan works after zoom - dragging up/down moves through price range
- **SC-003**: X-axis labels display same formatted dates as before (visual unchanged)
- **SC-004**: Tooltip displays correct date/time information
- **SC-005**: All existing price chart unit tests pass
- **SC-006**: Double-click reset still works

## Out of Scope

- Time axis label formatting changes (handled by Feature 1081)
- Resolution selector changes
- Sentiment chart modifications

## Technical Notes

- Chart.js time scale with `type: 'time'` uses numeric milliseconds internally
- X-axis data: `x: new Date(c.date).getTime()` instead of `x: this.formatTimestamp(...)`
- Tick callback: `callback: (value) => this.formatTimestamp(new Date(value).toISOString())`
