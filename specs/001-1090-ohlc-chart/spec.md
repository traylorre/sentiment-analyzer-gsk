# Feature Specification: OHLC Chart Time Axis Fixes

**Feature Branch**: `001-1090-ohlc-chart`
**Created**: 2025-12-28
**Status**: Draft
**Input**: Fix 6 chart issues: 1hr x-axis gaps, 1d weekday display, 5min/1min invisible candlesticks, zoom reset console error, x-axis panning not working

## Root Cause Analysis

All 6 issues stem from **improper time type handling** in `price-sentiment-chart.tsx`:

| Issue | Symptom | Root Cause |
|-------|---------|------------|
| 1hr gaps | X-axis shows "00:00" repeatedly | Lightweight-charts Time type mismatch - datetime strings not converted to Unix timestamps |
| 1d weekdays | Shows Sun-Thu instead of Mon-Fri | Data is correct (market hours), but no business-day filtering or resolution-aware date formatting |
| 5min invisible | Candlesticks exist but not visible | X-axis range spans too many days; `fitContent()` auto-fit doesn't account for intraday density |
| 1min invisible | Same as 5min | Same cause - x-axis bounds not set appropriately for high-frequency data |
| Console error | `value.toFixed is not a function` | Line 212: `(param.time as number) * 1000` fails when param.time is ISO string (daily data) |
| Panning broken | X-axis scroll doesn't work | Likely `handleScroll` config issue or conflicting event handlers |

**Core Technical Issue**: The chart passes `candle.date as Time` (line 263) where `candle.date` is an ISO string. Lightweight-charts expects either:
- Unix timestamp (number) for intraday
- Date string "YYYY-MM-DD" for daily

The current code doesn't convert based on resolution, causing all 6 issues.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Hourly OHLC Data (Priority: P1)

As a trader, I want to see hourly price data with correct time labels so I can analyze intraday price movements over multiple days.

**Why this priority**: This is the most commonly used resolution and the gaps make the chart unusable.

**Independent Test**: Select 1h resolution, verify x-axis shows date+time labels (e.g., "Dec 23 14:00") with proper spacing between candles.

**Acceptance Scenarios**:

1. **Given** user selects AAPL with 1h resolution, **When** chart loads, **Then** x-axis shows date+hour labels without gaps between trading sessions
2. **Given** 1h resolution data spans 5 days, **When** chart renders, **Then** candles are evenly spaced with clear day boundaries
3. **Given** user hovers over 1h candle, **When** tooltip appears, **Then** timestamp shows "Mon 12/23 14:00" format (weekday + date + time)

---

### User Story 2 - View High-Frequency Data (1min/5min) (Priority: P1)

As a day trader, I want to see minute-level candlestick data clearly visible so I can analyze rapid price movements.

**Why this priority**: Currently unusable - candlesticks exist (tooltip works) but are invisible due to x-axis bounds.

**Independent Test**: Select 1m resolution, verify candlesticks are clearly visible and x-axis shows appropriate time labels.

**Acceptance Scenarios**:

1. **Given** user selects AAPL with 5m resolution, **When** chart loads, **Then** candlesticks are visible with clear OHLC patterns
2. **Given** user selects 1m resolution, **When** chart loads, **Then** x-axis range is limited to show ~100-200 candles initially (auto-fit to recent data)
3. **Given** 1m data for 7 days, **When** chart renders, **Then** visible range shows most recent trading day by default with zoom-out capability

---

### User Story 3 - Zoom Reset Without Errors (Priority: P2)

As a user, I want to double-click to reset zoom without console errors so the application feels stable and professional.

**Why this priority**: Functional (zoom works) but console errors indicate underlying type issues that could cause other bugs.

**Independent Test**: Load any resolution, zoom in via scroll wheel, double-click to reset, verify no console errors.

**Acceptance Scenarios**:

1. **Given** user has zoomed into chart, **When** user double-clicks, **Then** chart resets to default view with no console errors
2. **Given** daily resolution (string dates), **When** tooltip/crosshair activates, **Then** date formatting handles string Time type correctly
3. **Given** intraday resolution (Unix timestamps), **When** tooltip activates, **Then** date formatting handles numeric Time type correctly

---

### User Story 4 - Pan X-Axis to Navigate History (Priority: P2)

As a user, I want to drag the chart left/right to see historical data so I can explore price movements outside the initial view.

**Why this priority**: Essential navigation feature that has never worked - limits data exploration capability.

**Independent Test**: Load 1h resolution, drag chart horizontally, verify viewport scrolls through time.

**Acceptance Scenarios**:

1. **Given** chart shows recent data, **When** user drags left (touch or mouse), **Then** chart scrolls to show older data
2. **Given** chart is at oldest data, **When** user drags left further, **Then** chart stops at data boundary (no infinite scroll into empty space)
3. **Given** user is panning, **When** user releases drag, **Then** chart maintains position without snapping back

---

### User Story 5 - Daily View Business Day Formatting (Priority: P3)

As an investor, I want daily candles to show weekday labels correctly (Mon-Fri) so the chart reflects actual trading days.

**Why this priority**: Lower priority as data is technically correct (shows actual market data), just formatting preference.

**Independent Test**: Select Day resolution, verify x-axis shows Mon-Fri labels corresponding to actual trading days.

**Acceptance Scenarios**:

1. **Given** user selects Day resolution, **When** chart loads, **Then** x-axis shows Monday-Friday labels (no weekend gaps shown)
2. **Given** daily data includes holiday closure, **When** chart renders, **Then** holiday gap is visually consistent with weekend gaps

---

### Edge Cases

- What happens when market is closed (weekend/holiday)? X-axis should show gap or skip non-trading periods
- How does system handle pre-market/after-hours data? Should be included for intraday, excluded for daily
- What happens when zooming past data boundaries? Should stop at first/last candle
- How does panning work with touch devices? Same drag behavior as mouse

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST convert ISO datetime strings to Unix timestamps (seconds) for intraday resolutions (1m, 5m, 15m, 30m, 1h)
- **FR-002**: System MUST keep date strings in "YYYY-MM-DD" format for daily resolution
- **FR-003**: System MUST set initial visible range based on resolution:
  - 1m: ~120 candles (2 hours of trading)
  - 5m: ~80 candles (trading day)
  - 1h: ~40 candles (5 trading days)
  - Day: All data (fitContent)
- **FR-004**: System MUST handle both string and number Time types in tooltip/crosshair handler without errors
- **FR-005**: System MUST enable horizontal scrolling/panning for all resolutions
- **FR-006**: Tooltip date format MUST adapt to resolution:
  - Intraday: "Mon 12/23 14:00"
  - Daily: "Mon Dec 23"
- **FR-007**: System MUST preserve zoom/pan position when resolution changes (reset to fitContent only)

### Key Entities

- **Time (lightweight-charts)**: Either Unix timestamp (number, seconds since epoch) or date string "YYYY-MM-DD"
- **Resolution**: Maps to time format and visible range settings
- **VisibleRange**: { from: Time, to: Time } - controls x-axis bounds

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 6 reported issues resolved - verified by visual inspection at each resolution
- **SC-002**: Zero console errors during chart interaction (zoom, pan, hover, resolution change)
- **SC-003**: Candlesticks visible at all resolutions without manual zoom adjustment
- **SC-004**: X-axis labels show appropriate date/time format for each resolution
- **SC-005**: Panning works in both directions at all resolutions

## Technical Approach

### File Changes

1. **`frontend/src/components/charts/price-sentiment-chart.tsx`**:
   - Add resolution prop to component
   - Create `convertToChartTime(date: string, resolution: OHLCResolution): Time` utility
   - Update data mapping (lines 262-268, 277-280) to use converter
   - Fix crosshair handler (line 212) to detect Time type before formatting
   - Add `setVisibleRange()` call after `fitContent()` for intraday resolutions
   - Verify `handleScroll` configuration

2. **`frontend/src/lib/utils/format.ts`**:
   - Add `formatChartDate(time: Time, resolution: OHLCResolution): string` function
   - Resolution-aware formatting for tooltips

3. **`frontend/src/hooks/use-chart-data.ts`**:
   - Pass resolution to chart component

### No Backend Changes Required

The backend correctly returns datetime for intraday and date for daily. The frontend needs to convert appropriately.

## Out of Scope

- Market hours filtering (showing only trading hours) - separate feature
- Gap-filling for market closed periods - separate feature
- Touch gesture optimization - works same as mouse, just needs testing
