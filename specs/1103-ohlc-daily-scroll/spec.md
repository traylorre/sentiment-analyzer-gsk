# Feature Specification: OHLC Daily Resolution Scrollable View

**Feature Branch**: `1103-ohlc-daily-scroll`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "1D view does not scroll, shows all data at once via fitContent() instead of a scrollable window"

## Problem Statement

The OHLC chart at daily (D) resolution uses `VISIBLE_CANDLES['D'] = 0`, which triggers `fitContent()` to show all data at once. This prevents users from scrolling/panning through historical daily data because the entire dataset is compressed into the viewport. Other resolutions (1m, 5m, 15m, 30m, 60m) have proper visible candle counts that enable scrolling.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pan Daily Chart (Priority: P1)

As a user viewing the daily OHLC chart, I want to scroll/pan left and right through price history so that I can analyze trends over different time periods.

**Why this priority**: Core functionality - daily resolution is the most common view for long-term analysis.

**Independent Test**: Load daily chart, verify initial view shows ~40 days, pan left to see older data.

**Acceptance Scenarios**:

1. **Given** I am viewing AAPL daily chart, **When** the chart loads, **Then** I see approximately 40 trading days of candlesticks with the most recent data on the right
2. **Given** I am viewing 40 days of data, **When** I pan left (drag or scroll), **Then** older candlesticks become visible
3. **Given** I have panned into historical data, **When** I pan right, **Then** I return toward recent data

---

### User Story 2 - Consistent UX Across Resolutions (Priority: P2)

As a user switching between resolutions, I want consistent panning behavior whether I'm viewing 5-minute or daily data.

**Why this priority**: UX consistency - users should not be confused by different interaction patterns.

**Independent Test**: Switch from 60m to D resolution, verify both allow panning.

**Acceptance Scenarios**:

1. **Given** I switch from 60m to D resolution, **When** the chart updates, **Then** I can still pan left/right as expected
2. **Given** daily chart shows 40 days, **When** compared to 60m showing 40 candles, **Then** panning behavior feels similar

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Daily resolution MUST show a fixed visible window of ~40 trading days initially (not fitContent)
- **FR-002**: Daily chart MUST support horizontal panning to view older/newer data
- **FR-003**: Initial view MUST be scrolled to show most recent data (right edge)

### Non-Functional Requirements

- **NFR-001**: Change must not break existing intraday resolutions
- **NFR-002**: No new dependencies required

### Key Entities

- **VISIBLE_CANDLES**: Configuration map in price-sentiment-chart.tsx
- **setVisibleLogicalRange**: lightweight-charts API for viewport control

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Daily chart initially shows ~40 candles, not all data
- **SC-002**: Users can pan to see data beyond the initial 40-day window
- **SC-003**: No regression in other resolution behaviors

## Implementation

### Change Required

In `frontend/src/components/charts/price-sentiment-chart.tsx`:

```typescript
const VISIBLE_CANDLES: Record<OHLCResolution, number> = {
  '1': 120,   // 2 hours of 1-min candles
  '5': 78,    // 1 trading day of 5-min candles
  '15': 52,   // 2 trading days
  '30': 26,   // 2 trading days
  '60': 40,   // 5 trading days
  'D': 40,    // ~2 months of trading days (was 0)
};
```

This enables the `setVisibleLogicalRange()` call at lines 414-417 to constrain the viewport for daily data.

## Assumptions

- 40 trading days provides good balance between context and candlestick visibility
- Backend already returns sufficient historical daily data (verified: 20+ days available)
