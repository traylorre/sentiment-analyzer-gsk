# Feature Specification: Fix SRI Hash for Date Adapter

**Feature Branch**: `1086-sri-hash-fix`
**Created**: 2025-12-28
**Status**: Draft
**Input**: User description: "Fix broken SRI integrity hash for chartjs-adapter-date-fns that prevents Price Chart from loading"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Price Chart Loads Successfully (Priority: P1)

A user navigates to the dashboard and the Price Chart (OHLC) renders correctly. The chart displays candlestick data with proper time-based X-axis formatting. No console errors about blocked resources or missing date adapters.

**Why this priority**: This is a critical blocker - without the date adapter, the Price Chart is completely non-functional. The dashboard's primary visualization feature is broken.

**Independent Test**: Load dashboard, verify Price Chart canvas shows OHLC candles with formatted timestamps on X-axis. No "integrity" or "date adapter" errors in console.

**Acceptance Scenarios**:

1. **Given** dashboard loads, **When** chartjs-adapter-date-fns script loads, **Then** SRI validation passes without blocking
2. **Given** OHLC chart initializes, **When** time scale is configured, **Then** no "method not implemented" errors occur

---

### Edge Cases

- CDN unavailable: Chart.js time scale falls back gracefully (currently errors, acceptable for now)
- Hash changes on CDN: Extremely rare for versioned packages, would require new fix

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST load chartjs-adapter-date-fns@3.0.0 without SRI validation errors
- **FR-002**: Price Chart MUST initialize with time scale X-axis without errors
- **FR-003**: OHLC candles MUST display with properly formatted timestamps

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero console errors related to SRI integrity or date adapters on dashboard load
- **SC-002**: Price Chart renders within 3 seconds of page load
- **SC-003**: Time-based pan/zoom functionality works correctly

## Technical Notes

Root cause: The SHA-384 integrity hash in index.html (`sha384-0tis8mN...`) does not match the actual file on jsDelivr CDN (`sha384-cVMg8E3...`). This was introduced in Feature 1082 with an incorrect hash calculation.

Fix: Update integrity attribute to correct hash: `sha384-cVMg8E3QFwTvGCDuK+ET4PD341jF3W8nO1auiXfuZNQkzbUUiBGLsIQUE+b1mxws`
