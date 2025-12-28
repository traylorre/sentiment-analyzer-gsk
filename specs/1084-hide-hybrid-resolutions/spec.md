# Feature Specification: Hide Hybrid Resolution Buckets

**Feature Branch**: `1084-hide-hybrid-resolutions`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Hide hybrid resolution buckets from unified resolution selector. The resolution selector shows non-exact mappings like 30min->1h that confuse users. Only show resolutions where OHLC and sentiment resolutions have exact 1:1 correspondence (e.g., 1min, 5min, 1h, Day)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Clean Resolution Selector (Priority: P1)

A user viewing the dashboard sees only resolution options that display consistent data across both the price chart and sentiment overlay. The selector shows 1m, 5m, 1h, and Day buttons - resolutions where OHLC candle size matches the sentiment aggregation bucket exactly. Hybrid mappings like "30m" (which maps to 30-minute OHLC but 1-hour sentiment) are hidden.

**Why this priority**: Users reported the hybrid buckets as "trashy-looking" because the OHLC candle timeframe doesn't match the sentiment bucket, leading to visual misalignment and confusion about what the data represents.

**Independent Test**: Load dashboard, verify only 4 resolution buttons appear (1m, 5m, 1h, Day). Click each button and verify both charts update with matching time granularity.

**Acceptance Scenarios**:

1. **Given** the dashboard loads, **When** the resolution selector renders, **Then** only resolutions with `exact: true` are shown (1m, 5m, 1h, Day)
2. **Given** the user clicks a resolution button, **When** the charts update, **Then** both OHLC and sentiment show data at the same time granularity

---

### Edge Cases

- If all resolutions are hidden (configuration error), show at least "Day" as fallback
- Default resolution should be updated if current default is a hybrid resolution
- Saved user preference for a hybrid resolution should fallback to nearest exact resolution

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST filter UNIFIED_RESOLUTIONS to only display items with `exact: true`
- **FR-002**: Resolution selector buttons MUST only render for exact-match resolutions
- **FR-003**: System MUST preserve existing resolution switching behavior for shown resolutions
- **FR-004**: System MUST update default resolution if current default is hybrid (fallback to '1h')
- **FR-005**: System MUST handle saved preferences for hidden resolutions by falling back to default

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Resolution selector displays exactly 4 buttons: 1m, 5m, 1h, Day
- **SC-002**: No visual misalignment between OHLC candles and sentiment overlay
- **SC-003**: All existing resolution functionality continues to work for shown resolutions
- **SC-004**: No console errors or warnings related to hidden resolutions

## Technical Notes

The UNIFIED_RESOLUTIONS array in config.js already has the `exact` property:
- `exact: true`: 1m, 5m, 1h, Day - OHLC and sentiment resolutions match
- `exact: false`: 10m, 15m, 30m, 3h, 6h, 12h - hybrid mappings that should be hidden

Implementation involves filtering in unified-resolution.js where buttons are rendered.
