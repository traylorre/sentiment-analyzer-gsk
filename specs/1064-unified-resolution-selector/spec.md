# Feature Specification: Unified Resolution Selector

**Feature Branch**: `1064-unified-resolution-selector`
**Created**: 2025-12-26
**Status**: Draft
**Input**: Create a single resolution selector that synchronizes time bucket selection between OHLC price chart and sentiment trend chart.

## Problem Statement

Currently, the dashboard has TWO separate resolution selectors:

1. **OHLC Chart** (`src/dashboard/ohlc.js`)
   - Resolutions: `['1', '5', '15', '30', '60', 'D']` (backend values)
   - Labels: `['1m', '5m', '15m', '30m', '1h', 'Day']`
   - Source: Tiingo IEX (intraday) / Tiingo Daily

2. **Sentiment Trend** (`src/dashboard/timeseries.js`)
   - Resolutions: `['1m', '5m', '10m', '1h', '3h', '6h', '12h', '24h']`
   - Source: DynamoDB sentiment-timeseries table

**Key Differences**:
| Aspect | OHLC | Sentiment |
|--------|------|-----------|
| Resolution format | Numbers + 'D' | String with unit suffix |
| Common values | 1m, 5m, 1h | 1m, 5m, 1h |
| Unique to OHLC | 15m, 30m, Day | - |
| Unique to Sentiment | 10m, 3h, 6h, 12h, 24h | - |

**Goal**: Single resolution selector that updates both charts simultaneously, using intersection of supported resolutions with intelligent fallback for non-overlapping values.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Synchronized Resolution Change (Priority: P0)

As a trader viewing the dashboard, I want to change time resolution ONCE and have both the price chart and sentiment chart update to the same granularity, so I can analyze price-sentiment correlation at the same time scale.

**Why this priority**: Core usability issue - currently users must change resolution in two places, creating confusion and making correlation analysis difficult.

**Independent Test**: Click unified resolution selector, verify both OHLC and sentiment charts update simultaneously.

**Acceptance Scenarios**:

1. **Given** unified resolution selector is displayed, **When** user clicks "5m", **Then** both OHLC chart shows 5-minute candles AND sentiment chart shows 5-minute buckets
2. **Given** user selects "1h" resolution, **When** data loads, **Then** both charts display 1-hour granularity data aligned by timestamp
3. **Given** user selected resolution persists in sessionStorage, **When** page is refreshed, **Then** both charts restore to the saved resolution

---

### User Story 2 - Intelligent Fallback for Non-Overlapping Resolutions (Priority: P1)

As a user, I want to select resolutions that one chart supports but the other doesn't, with the system intelligently falling back to the nearest supported value for the other chart.

**Why this priority**: Supports full functionality without removing useful resolutions from either system.

**Independent Test**: Select "15m" (OHLC only), verify sentiment chart falls back to 10m with indicator.

**Acceptance Scenarios**:

1. **Given** user selects "15m" (OHLC-only resolution), **When** charts update, **Then** OHLC shows 15m candles AND sentiment shows 10m buckets with fallback indicator
2. **Given** user selects "24h" (sentiment-only resolution), **When** charts update, **Then** sentiment shows 24h buckets AND OHLC shows Daily candles with fallback indicator
3. **Given** fallback is in use, **When** user hovers over chart title, **Then** tooltip explains the resolution mismatch

---

### User Story 3 - Single Selector UI (Priority: P0)

As a user, I want to see ONE clear resolution selector, not two confusing ones, so the interface is simple and intuitive.

**Why this priority**: Reduces UI clutter and cognitive load.

**Independent Test**: Page loads with single unified resolution selector visible.

**Acceptance Scenarios**:

1. **Given** page loads, **When** user looks for resolution controls, **Then** there is ONE unified selector (not two separate ones)
2. **Given** unified selector is displayed, **When** user views available options, **Then** options are clearly labeled (1m, 5m, 10m, 15m, 30m, 1h, 3h, 6h, 12h, 24h, Day)
3. **Given** old individual selectors, **When** page renders, **Then** they are hidden/removed

---

### Edge Cases

- What if sentiment API doesn't support selected resolution? Fall back to nearest supported, show indicator
- What if OHLC API returns daily fallback for intraday? Show OHLC fallback message AND use daily for both
- What happens during data loading? Show skeleton on both charts simultaneously
- What if one API fails but other succeeds? Show error on failed chart, data on successful chart

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard MUST display ONE unified resolution selector controlling both charts
- **FR-002**: Selector MUST support superset of resolutions: 1m, 5m, 10m, 15m, 30m, 1h, 3h, 6h, 12h, 24h, Day
- **FR-003**: When user changes resolution, BOTH charts MUST update simultaneously
- **FR-004**: Selected resolution MUST persist in sessionStorage (key: `unified_resolution`)
- **FR-005**: For non-overlapping resolutions, system MUST map to nearest supported value with visual indicator
- **FR-006**: Old individual resolution selectors MUST be hidden/removed
- **FR-007**: Resolution selector position MUST be prominent (above charts, not buried in individual chart sections)

### Non-Functional Requirements

- **NFR-001**: Both charts MUST complete loading within 3 seconds of resolution change
- **NFR-002**: Selector interaction MUST feel instant (< 100ms visual feedback)
- **NFR-003**: No console errors during resolution switching

### Key Entities

- **UnifiedResolution**: { key: string, label: string, ohlcMapping: string, sentimentMapping: string }
- **ResolutionMapping**: Defines how unified resolution maps to each chart's supported values

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Single resolution selector visible on page load (not two)
- **SC-002**: Changing resolution updates both charts within 3 seconds
- **SC-003**: Resolution preference persists across page reloads
- **SC-004**: Fallback indicator displays when resolution mapping occurs
- **SC-005**: No UI flicker when switching resolutions

## Technical Approach

### Resolution Mapping Strategy

```javascript
const UNIFIED_RESOLUTIONS = [
  { key: '1m', label: '1m', ohlc: '1', sentiment: '1m' },      // Both support
  { key: '5m', label: '5m', ohlc: '5', sentiment: '5m' },      // Both support
  { key: '10m', label: '10m', ohlc: '15', sentiment: '10m' },  // Sentiment native, OHLC→15m
  { key: '15m', label: '15m', ohlc: '15', sentiment: '10m' },  // OHLC native, Sentiment→10m
  { key: '30m', label: '30m', ohlc: '30', sentiment: '1h' },   // OHLC native, Sentiment→1h
  { key: '1h', label: '1h', ohlc: '60', sentiment: '1h' },     // Both support
  { key: '3h', label: '3h', ohlc: '60', sentiment: '3h' },     // Sentiment native, OHLC→1h
  { key: '6h', label: '6h', ohlc: 'D', sentiment: '6h' },      // Sentiment native, OHLC→D
  { key: '12h', label: '12h', ohlc: 'D', sentiment: '12h' },   // Sentiment native, OHLC→D
  { key: '24h', label: 'Day', ohlc: 'D', sentiment: '24h' },   // Both support (D = 24h)
];
```

### Files to Modify

1. **src/dashboard/config.js**: Add UNIFIED_RESOLUTIONS config
2. **src/dashboard/unified-resolution.js** (NEW): Unified resolution selector component
3. **src/dashboard/ohlc.js**: Remove local resolution selector, accept external resolution changes
4. **src/dashboard/timeseries.js**: Remove local resolution selector, accept external resolution changes
5. **src/dashboard/app.js**: Initialize unified resolution selector
6. **src/dashboard/index.html**: Add unified resolution selector container
7. **src/dashboard/styles.css**: Styles for unified selector

## Dependencies

- Feature 1057 (Dashboard OHLC Chart) - MERGED
- Feature 1035 (OHLC Resolution Selector) - MERGED
- Timeseries endpoint supports resolution parameter - VERIFIED

## Out of Scope

- Backend resolution unification (keeping separate APIs)
- New resolutions not currently supported by either chart
- SSE streaming resolution changes
