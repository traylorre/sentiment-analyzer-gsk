# Feature Specification: OHLC Auto-Fit Data Limits

**Feature Branch**: `1075-ohlc-autofit-limits`
**Created**: 2025-12-27
**Status**: Implementation Ready
**Input**: Fix OHLC auto-fit to use actual data min/max instead of 'original' keyword

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Price Chart Shows Actual Data Range (Priority: P1)

As a user viewing the Price Chart, I want the chart to automatically scale to show the actual price range of the data (from lowest low to highest high), so I can see meaningful price movements without the chart being distorted by a $0 floor.

**Why this priority**: Core usability issue. Without proper auto-fit, users see a compressed chart that makes price movements appear insignificant. This directly impacts the demo-ability of the dashboard.

**Independent Test**: Can be fully tested by loading the dashboard, observing the Price Chart Y-axis, and verifying it shows realistic price ranges (e.g., $170-$180 for AAPL) rather than starting at $0.

**Acceptance Scenarios**:

1. **Given** a user loads the dashboard with AAPL data ranging $170-$180, **When** the Price Chart renders, **Then** the Y-axis shows approximately $170-$180 (not $0-$180)
2. **Given** a user switches resolution from 1D to 5m, **When** the new data loads, **Then** the Y-axis adjusts to the new data's actual min/max
3. **Given** a user double-clicks to reset zoom, **When** zoom resets, **Then** the chart shows the full data range (not a stale $0-max)

---

### Edge Cases

- If all candles have the same price (flat line), add a small buffer (e.g., +/- $0.50) to prevent zero-height chart
- If data has extreme outliers, the auto-fit still shows all data (no outlier clipping)
- Sentiment axis (-1 to 1) remains fixed regardless of data range

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Price axis limits MUST be dynamically calculated from actual candle data (min of lows, max of highs)
- **FR-002**: Limits MUST update when new data is loaded (resolution change, ticker change)
- **FR-003**: `resetZoom()` MUST restore to the dynamically calculated data limits, not stale initial values
- **FR-004**: Sentiment axis limits MUST remain fixed at -1 to 1
- **FR-005**: Price limits MUST include a small buffer (5% padding) above and below data range for visual clarity

### Key Entities

- **Price Limits**: min = lowest low - 5% padding, max = highest high + 5% padding
- **Zoom Plugin Configuration**: `options.plugins.zoom.limits.price`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Price Chart Y-axis shows data range, not $0-max (verified by inspecting axis labels)
- **SC-002**: Switching resolutions updates Y-axis to new data range within 2 seconds
- **SC-003**: Double-click reset restores to data range, not initial render values
- **SC-004**: Sentiment axis remains -1 to 1 after any zoom/pan/reset operation

## Implementation Notes

The root cause: chartjs-plugin-zoom's `min: 'original'` keyword "uses whatever limits the scale had when the chart was first displayed" - it does NOT recalculate from new data. The fix is to:

1. Calculate actual min/max from candle data (low/high values)
2. Update `chart.options.plugins.zoom.limits.price` configuration before calling `resetZoom()`
3. Call `chart.update()` to apply new limits before `resetZoom()`

Reference: https://www.chartjs.org/chartjs-plugin-zoom/latest/guide/options.html
