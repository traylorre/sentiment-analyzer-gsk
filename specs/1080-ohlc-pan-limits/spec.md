# Feature Specification: OHLC Pan Limits Fix

**Feature Branch**: `1080-ohlc-pan-limits`
**Created**: 2025-12-28
**Status**: Draft

## Problem Statement

Pan functionality on the OHLC Price Chart doesn't work despite cursor changing to grab/grabbing:

1. **Left-right pan doesn't work**: X-axis (time) has no limits configuration in zoom plugin
2. **Up-down pan doesn't work after zoom**: Pan mode is `'x'` only, restricting to horizontal

**Root Cause Analysis**:

Current zoom.limits config (ohlc.js ~line 476):
```javascript
limits: {
    price: { min: 'original', minRange: 5 },
    sentiment: { min: -1, max: 1, minRange: 2 }
}
// MISSING: x: { ... } for time axis limits
```

Current pan mode (ohlc.js ~line 446):
```javascript
pan: {
    enabled: true,
    mode: 'x',  // Only allows horizontal, blocks vertical
    ...
}
```

## User Scenarios & Testing

### User Story 1 - Horizontal Pan (Left-Right Time Navigation) (Priority: P1)

As a user viewing the Price Chart, I want to left-click and drag horizontally to navigate through time.

**Why this priority**: Core pan functionality that users expect from any chart.

**Independent Test**: Load chart, left-click-drag horizontally, verify chart pans through time.

**Acceptance Scenarios**:

1. **Given** OHLC chart displays data, **When** user left-click-drags left, **Then** chart shows earlier candles
2. **Given** OHLC chart displays data, **When** user left-click-drags right, **Then** chart shows later candles
3. **Given** user is at data boundary, **When** user tries to pan beyond data, **Then** pan stops at boundary

---

### User Story 2 - Vertical Pan After Zoom (Priority: P1)

As a user who has zoomed into price data, I want to pan vertically to see candles that went out of view.

**Why this priority**: After zooming, candlesticks often go out of view and users need to pan to see them.

**Independent Test**: Zoom into chart, then left-click-drag vertically, verify chart pans up/down.

**Acceptance Scenarios**:

1. **Given** user has zoomed in on price axis, **When** user left-click-drags up, **Then** chart shows higher prices
2. **Given** user has zoomed in on price axis, **When** user left-click-drags down, **Then** chart shows lower prices
3. **Given** user pans vertically, **When** sentiment axis is visible, **Then** sentiment axis remains fixed at -1 to 1

---

### Edge Cases

- What happens when panning beyond data range? (Stop at data boundaries)
- What happens to sentiment axis during vertical pan? (Remains fixed per design)
- What happens with diagonal drag? (Both axes pan simultaneously)

## Requirements

### Functional Requirements

- **FR-001**: System MUST add X-axis limits to zoom plugin configuration
- **FR-002**: System MUST use 'original' data range for X-axis limits
- **FR-003**: System MUST change pan mode from 'x' to 'xy' for bi-directional panning
- **FR-004**: System MUST keep sentiment axis fixed during vertical pan (min: -1, max: 1)
- **FR-005**: System MUST maintain grab/grabbing cursor feedback during pan

## Success Criteria

### Measurable Outcomes

- **SC-001**: Left-click-drag horizontally pans chart through time
- **SC-002**: Left-click-drag vertically pans chart through price range (after zoom)
- **SC-003**: Pan stops at data boundaries (cannot pan beyond available data)
- **SC-004**: Sentiment axis (-1 to 1) remains fixed during vertical pan
