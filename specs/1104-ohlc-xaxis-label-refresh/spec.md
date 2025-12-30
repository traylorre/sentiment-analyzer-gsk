# Feature Specification: OHLC Chart X-Axis Label Refresh on Pan

**Feature Branch**: `1104-ohlc-xaxis-label-refresh`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "1h view pans but x-axis labels don't update during pan"

## Problem Statement

The OHLC price chart (price-sentiment-chart.tsx) allows panning on intraday resolutions like 1h, but the x-axis labels don't update to show the new visible time range. Other charts in the codebase (sentiment-chart.tsx, atr-chart.tsx) have proper label refresh because they include explicit `textColor` in their timeScale configuration.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - X-Axis Labels Update on Pan (Priority: P1)

As a user panning the 1h OHLC chart, I want the x-axis labels to update to reflect the visible time range so I can see which hours I'm viewing.

**Why this priority**: Core UX expectation - axis labels should always reflect visible data.

**Independent Test**: Load 1h chart, pan left, verify x-axis labels change to show earlier times.

**Acceptance Scenarios**:

1. **Given** I am viewing 1h OHLC chart, **When** I pan left, **Then** x-axis labels update to show earlier hours
2. **Given** I pan right after viewing history, **When** chart moves, **Then** x-axis labels reflect current visible range
3. **Given** any resolution (1m, 5m, 15m, 30m, 1h, D), **When** I pan, **Then** x-axis labels update accordingly

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: X-axis labels MUST update during pan operations
- **FR-002**: timeScale configuration MUST include textColor property
- **FR-003**: Labels should use consistent styling with other charts (#a3a3a3)

### Key Entities

- **timeScale**: lightweight-charts time axis configuration
- **textColor**: CSS color for axis label text

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: X-axis labels visibly update when panning on all resolutions
- **SC-002**: No regression in chart rendering or pan behavior
- **SC-003**: Visual consistency with sentiment-chart and atr-chart

## Implementation

### Change Required

In `frontend/src/components/charts/price-sentiment-chart.tsx`, add `textColor` to timeScale config:

```typescript
timeScale: {
  borderColor: 'rgba(0, 255, 255, 0.1)',
  timeVisible: true,
  secondsVisible: false,
  textColor: '#a3a3a3',  // ADD: Enable label refresh on pan
},
```

## Assumptions

- Adding textColor is sufficient to enable label refresh (matches other working charts)
- No changes to time formatting logic needed
