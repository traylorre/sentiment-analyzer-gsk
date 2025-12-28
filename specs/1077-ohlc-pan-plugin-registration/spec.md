# Feature Specification: OHLC Pan Plugin Registration Fix

**Feature Branch**: `1077-ohlc-pan-plugin-registration`
**Created**: 2025-12-28
**Status**: Draft

## Problem Statement

Left-click-drag panning does not work on the Price Chart despite:
- Hammer.js being loaded correctly (PR #533, #534)
- Pan configuration set to `enabled: true, mode: 'x'`
- No modifier key required

**Root Cause**: Chart.js v4.x requires explicit plugin registration. The chartjs-plugin-zoom script loads globally but is never registered with Chart.js, so pan/zoom functionality is silently inactive.

## User Scenarios & Testing

### User Story 1 - Horizontal Pan with Left-Click-Drag (Priority: P1)

As a user viewing the Price Chart, I want to left-click and drag to pan the chart horizontally, so I can navigate through time without using scroll.

**Acceptance Scenarios**:

1. **Given** the chart is displaying OHLC data, **When** user left-click-drags horizontally, **Then** the chart pans in the X direction showing earlier/later candles
2. **Given** user is panning, **When** the cursor is over the chart, **Then** cursor changes to grab/grabbing cursor to indicate pan mode

---

### User Story 2 - Cursor Feedback (Priority: P2)

As a user, I want visual feedback that panning is available, so I know I can interact with the chart.

**Acceptance Scenarios**:

1. **Given** chart is loaded, **When** cursor hovers over chart, **Then** cursor shows as "grab" cursor
2. **Given** user is actively dragging, **When** dragging, **Then** cursor shows as "grabbing" cursor

---

### Edge Cases

- What happens when panning beyond data range? (Should stop at data boundaries)
- What happens if Hammer.js fails to load? (Graceful fallback, no errors)

## Requirements

### Functional Requirements

- **FR-001**: System MUST register chartjs-plugin-zoom with Chart.js before creating chart instance
- **FR-002**: System MUST display grab cursor on chart canvas hover
- **FR-003**: System MUST display grabbing cursor during active pan drag
- **FR-004**: System SHOULD log warning if zoom plugin unavailable

## Success Criteria

- **SC-001**: Left-click-drag pans the chart horizontally
- **SC-002**: Cursor changes to grab/grabbing during pan interaction
- **SC-003**: All existing chart tests continue to pass
