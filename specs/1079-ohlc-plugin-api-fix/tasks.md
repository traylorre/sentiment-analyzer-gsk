# Implementation Tasks: OHLC Plugin API Fix

**Branch**: `1079-ohlc-plugin-api-fix` | **Created**: 2025-12-28

## Phase 1: Setup

- [X] T001 Review Feature 1077 code causing the error in src/dashboard/ohlc.js

## Phase 2: User Story 1 - OHLC Chart Renders Successfully (P1)

- [X] T002 [US1] Fix plugin registration check using Chart.registry.getPlugin('zoom') in src/dashboard/ohlc.js

## Phase 3: Verification

- [ ] T003 Deploy to preprod and verify no console errors on page load
- [ ] T004 Verify OHLC chart renders with candles displaying correctly
- [ ] T005 Verify left-click-drag panning works (horizontal time navigation)

## Dependencies

```text
T001 → T002 → T003 → T004 → T005
```

## Notes

- Single file change: src/dashboard/ohlc.js lines 347-348
- Fix changes 2 lines: removes `.items` array access, uses `getPlugin()` method
- No backend changes required
- No new dependencies
