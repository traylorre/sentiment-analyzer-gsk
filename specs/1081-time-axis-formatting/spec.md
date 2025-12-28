# Feature Specification: OHLC Time Axis Formatting Fix

**Feature Branch**: `1081-time-axis-formatting`
**Created**: 2025-12-28
**Status**: Draft
**Input**: Fix OHLC time axis formatting to include date context for multi-day intraday data

## User Scenarios & Testing

### User Story 1 - Date Context in Multi-Day Time Labels (Priority: P1)

When viewing multi-day intraday OHLC data, time labels should include date context so traders can distinguish which candles belong to which trading day. Currently, times like "09:30" repeat across multiple days with no visual distinction.

**Why this priority**: Core usability issue - users cannot interpret chart correctly without knowing which day each candle represents.

**Independent Test**: Load 7-day intraday chart (1h resolution). First candle of each day should show "Mon 12/23" format, subsequent candles show "10:00" format.

**Acceptance Scenarios**:

1. **Given** 7-day intraday data at 1h resolution, **When** chart renders, **Then** each day's first candle label shows abbreviated weekday and date (e.g., "Mon 12/23")
2. **Given** 7-day intraday data, **When** user hovers over time axis, **Then** can clearly identify which candles belong to which day
3. **Given** single-day intraday data, **When** chart renders, **Then** labels show time only ("09:30", "10:00") with no date prefix

---

### User Story 2 - Day Resolution Labels (Priority: P2)

Day resolution charts should continue showing month-day format for consistency with existing behavior.

**Why this priority**: Maintains backward compatibility with existing correct behavior.

**Independent Test**: Load chart at Day resolution. Labels show "Dec 23", "Dec 24" format.

**Acceptance Scenarios**:

1. **Given** Day resolution selected, **When** chart renders, **Then** labels show "Dec 23" format (unchanged from current)

---

### Edge Cases

- What happens when market is closed (weekend/holiday)? Skip those days in formatting
- What happens at year boundary (Dec 31 to Jan 1)? Show appropriate dates
- What happens with pre-market/after-hours candles? Include in same day as regular session

## Requirements

### Functional Requirements

- **FR-001**: System MUST detect if candle data spans multiple calendar days
- **FR-002**: System MUST show abbreviated date (e.g., "Mon 12/23") for first candle of each new trading day when data spans multiple days
- **FR-003**: System MUST show time only (e.g., "09:30") for subsequent candles on the same day
- **FR-004**: System MUST preserve existing Day resolution format ("Dec 23")
- **FR-005**: System MUST use Chart.js autoSkip to prevent label overlap

## Success Criteria

### Measurable Outcomes

- **SC-001**: Multi-day intraday charts clearly show day boundaries with date labels
- **SC-002**: No label overlap or truncation at any resolution
- **SC-003**: Single-day view remains clean with time-only labels
- **SC-004**: All existing price chart unit tests pass (26+ tests)
- **SC-005**: Day resolution behavior unchanged

## Out of Scope

- Resolution mapping changes (handled by UNIFIED_RESOLUTIONS design)
- Backend API changes
- Sentiment chart time axis formatting
