# Feature Specification: OHLC Market Gap Visualization

**Feature Branch**: `1102-ohlc-market-gap-viz`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "OHLC chart market gap visualization: show date gaps with red shaded rectangles, continuous x-axis labels showing real dates, equal-width candlesticks regardless of time gaps"

## Problem Statement

Currently, the OHLC chart uses a category scale that hides date gaps (weekends, holidays). While this provides equal-width candlesticks, users cannot tell when the market was closed. For example, viewing daily data from December 23 to December 26 shows 3 consecutive candlesticks without indicating that December 25 (Christmas) was a market closure.

Users need to understand when the market was closed to properly interpret price movements. A gap between Friday's close and Monday's open is significant and should be visually clear.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Visualize Market Closures (Priority: P1)

As a user viewing the OHLC chart, I want to see red-shaded rectangles for dates when the market was closed so that I can understand price gaps in context.

**Why this priority**: Core value - provides essential market context that affects price interpretation.

**Independent Test**: View daily OHLC data that includes a weekend. Verify red shading appears for Saturday and Sunday.

**Acceptance Scenarios**:

1. **Given** I am viewing AAPL daily chart, **When** the data includes a weekend (Sat-Sun), **Then** red-shaded rectangles appear for those non-trading days
2. **Given** I am viewing daily chart around Christmas 2025, **When** Dec 25 is displayed, **Then** a red-shaded rectangle appears for Christmas Day
3. **Given** I hover over a red-shaded gap, **When** the tooltip appears, **Then** it shows "Market Closed - [date]" or similar indicator

---

### User Story 2 - Equal-Width Candlesticks with Gaps (Priority: P1)

As a user viewing the OHLC chart, I want all candlesticks to have equal width even when gaps are shown so that visual comparison of price movements remains consistent.

**Why this priority**: Equal width is essential for pattern recognition in technical analysis.

**Independent Test**: View chart with weekend gap, verify candlesticks before and after gap have identical widths.

**Acceptance Scenarios**:

1. **Given** I am viewing a chart with a 2-day weekend gap, **When** I compare candlestick widths, **Then** all candlesticks have identical width
2. **Given** the chart has both trading days and gap markers, **When** rendered, **Then** gap markers occupy the same horizontal space as candlesticks

---

### User Story 3 - Continuous X-Axis Labels (Priority: P2)

As a user viewing the OHLC chart, I want the x-axis to show dates continuously (including closed days) so that I can understand the true time progression.

**Why this priority**: Supports understanding of time gaps, but secondary to visual gap indication.

**Independent Test**: Check x-axis labels include weekend dates (Sat, Sun) between Friday and Monday labels.

**Acceptance Scenarios**:

1. **Given** I am viewing daily chart with a weekend, **When** I look at x-axis labels, **Then** dates progress continuously (Fri → Sat → Sun → Mon)
2. **Given** I zoom into the chart, **When** more labels become visible, **Then** gap dates are included in labeling

---

### Edge Cases

- What happens with consecutive holidays (e.g., Thanksgiving + day after)?
  - Multiple consecutive red-shaded rectangles are shown
- What happens at market early closes (e.g., Christmas Eve half-day)?
  - Partial trading day shows as normal candlestick, not a gap
- What happens with intraday charts (1hr, 5min)?
  - After-hours periods (evenings, weekends) show as red-shaded gaps between sessions
- What happens if we can't determine market calendar?
  - Fall back to showing only weekend gaps (Sat-Sun for daily charts)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Chart MUST display red-shaded rectangles for all dates with no trading data
- **FR-002**: Red shading MUST span the full y-axis height of the chart
- **FR-003**: Red shading MUST occupy equal horizontal width as regular candlesticks
- **FR-004**: All candlesticks MUST have equal width regardless of adjacent gaps
- **FR-005**: X-axis labels MUST show continuous dates including market closure days
- **FR-006**: Hovering over gap area MUST show tooltip indicating market closure
- **FR-007**: System MUST identify gaps for: weekends (daily), after-hours (intraday), and major US holidays

### Visual Design

- **VD-001**: Gap rectangle color: Light red (`rgba(255, 0, 0, 0.1)` or similar subtle shade)
- **VD-002**: Gap rectangle spans from chart top to bottom
- **VD-003**: No candlestick or price line drawn in gap areas
- **VD-004**: Tooltip for gaps: "Market Closed - [Day, Date]"

### Key Entities

- **GapMarker**: Represents a date/time with no trading data; has `date`, `isGap: true`, display metadata
- **MarketCalendar**: Logic to determine if a given date/time is a trading period
- **GapShaderPrimitive**: Custom drawing primitive to render red rectangles

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of weekend days (Sat-Sun) in daily charts display red shading
- **SC-002**: All candlesticks maintain equal width (within 1px tolerance)
- **SC-003**: X-axis shows continuous date progression with no label skips
- **SC-004**: Gap areas are visually distinct and immediately noticeable

## Assumptions

- US market calendar is the reference (NYSE/NASDAQ hours)
- Daily resolution gaps are: weekends + federal market holidays
- Intraday gaps are: outside 9:30 AM - 4:00 PM ET + weekends + holidays
- Frontend can determine gaps from missing data timestamps
