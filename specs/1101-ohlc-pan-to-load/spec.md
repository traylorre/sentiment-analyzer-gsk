# Feature Specification: OHLC Chart Bidirectional Pan-to-Load

**Feature Branch**: `1101-ohlc-pan-to-load`
**Created**: 2025-12-29
**Status**: Draft
**Input**: User description: "OHLC chart bidirectional pan-to-load: panning left loads older data, panning right loads newer data, infinite scroll pattern"

## Problem Statement

Currently, the OHLC chart loads a fixed time range of data (e.g., 1 month) and users cannot access historical data beyond that window. When users pan the chart to explore price history, they hit the edge of loaded data and cannot continue. This limits the chart's usefulness for technical analysis that requires viewing longer price history.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pan Left for Historical Data (Priority: P1)

As a user viewing the OHLC chart, I want to pan left to see older price data so that I can analyze historical trends without manually changing time range settings.

**Why this priority**: Core value proposition - enables continuous exploration of price history, the most common chart interaction pattern in financial applications.

**Independent Test**: Load chart with 1 month of data, pan left past the initial data boundary, verify older data loads seamlessly.

**Acceptance Scenarios**:

1. **Given** I am viewing AAPL daily chart with 1 month of data, **When** I pan left and approach the left edge (within 50 bars), **Then** older data begins loading automatically
2. **Given** older data is loading, **When** the data arrives, **Then** new candlesticks appear on the left without disrupting my current view position
3. **Given** I have panned to load 3 months of data, **When** I continue panning left, **Then** data continues loading until I reach the earliest available data

---

### User Story 2 - Pan Right for Recent Data (Priority: P2)

As a user who has panned into historical data, I want to pan right to return to recent/live data so that I can see current prices.

**Why this priority**: Complements P1 - users need to navigate back to present after exploring history.

**Independent Test**: After panning left into history, pan right and verify chart returns to most recent data.

**Acceptance Scenarios**:

1. **Given** I have panned left into historical data, **When** I pan right toward present, **Then** the chart scrolls back toward recent data
2. **Given** I am viewing historical data and new live data has arrived, **When** I pan right to the edge, **Then** the latest data is visible

---

### User Story 3 - Loading Indicator (Priority: P3)

As a user panning through the chart, I want to see a visual indicator when data is loading so that I understand the system is fetching more data.

**Why this priority**: UX polish - prevents user confusion when there's a delay in data loading.

**Independent Test**: Pan to edge, observe loading indicator appears and disappears when data loads.

**Acceptance Scenarios**:

1. **Given** I pan to the edge of loaded data, **When** a fetch is triggered, **Then** a subtle loading indicator appears (e.g., spinner at chart edge or status text)
2. **Given** data is loading, **When** the fetch completes, **Then** the loading indicator disappears

---

### Edge Cases

- What happens when user pans to earliest available data (no more history)?
  - System stops trying to load and optionally shows "No earlier data available" indicator
- What happens when network request fails?
  - Show error toast, allow retry on next pan, do not disrupt existing data display
- What happens during rapid panning (multiple edge hits)?
  - Debounce/throttle requests, only one fetch in-flight at a time
- What happens when user changes resolution while data is loading?
  - Cancel pending fetch, load fresh data for new resolution

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Chart MUST detect when user pans within threshold of loaded data boundary (e.g., 50 bars)
- **FR-002**: Chart MUST automatically fetch older data when user approaches left boundary
- **FR-003**: Chart MUST automatically fetch newer data when user approaches right boundary (if newer data exists)
- **FR-004**: Chart MUST prepend/append new data to existing dataset without view disruption
- **FR-005**: System MUST prevent duplicate concurrent fetch requests (debounce/throttle)
- **FR-006**: System MUST track loaded data range to avoid re-fetching already-loaded data
- **FR-007**: Chart MUST maintain scroll position when new data is added
- **FR-008**: System MUST gracefully handle reaching end of available data (earliest/latest)

### Key Entities

- **LoadedDataRange**: Tracks start/end timestamps of currently loaded OHLC data
- **FetchState**: Loading status (idle, fetching, error), prevents concurrent requests
- **ViewportRange**: Current visible range in the chart (bar indices or timestamps)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can access at least 1 year of historical data through pan-to-load without manual time range changes
- **SC-002**: Data loading completes within 2 seconds of triggering (under normal network conditions)
- **SC-003**: No visible "jump" or position reset when new data is prepended/appended
- **SC-004**: Zero duplicate network requests during rapid panning (verified in Network tab)

## Assumptions

- Backend OHLC API supports pagination via `startDate`/`endDate` or `before`/`after` parameters
- Tiingo/Finnhub APIs have sufficient historical data (1+ years for daily, 30+ days for intraday)
- lightweight-charts library supports dynamic data updates via `setData()` or `update()` methods
