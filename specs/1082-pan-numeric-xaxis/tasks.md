# Implementation Tasks: Fix OHLC Pan with Numeric X-Axis

**Branch**: `1082-pan-numeric-xaxis` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] Check if date-fns adapter is loaded in index.html (required for time scale)
- [X] T002 [US1] Add date-fns adapter to index.html if missing
- [X] T003 [US1] Update X-axis scale config to type: 'time' in ohlc.js
- [X] T004 [US1] Convert data.x to numeric epoch ms in updateChart()
- [X] T005 [US1] Update limits.x to use numeric min/max from data array
- [X] T006 [US1] [US2] Add tick callback for custom label formatting
- [X] T007 [US1] Update tooltip title callback for full date+time display

## Phase 2: Testing

- [X] T008 Create/update static analysis tests for numeric X-axis

## Phase 3: Verification

- [ ] T009 Deploy and verify horizontal pan works
- [ ] T010 Verify vertical pan works after zoom
- [ ] T011 Verify tooltip shows full date+time
- [ ] T012 Verify double-click reset still works

## Dependencies

```text
T001 → T002 (if needed) → T003 → T004 → T005 → T006 → T007 → T008 → T009...
```

## Notes

- Chart.js time scale requires adapter (chartjs-adapter-date-fns)
- Numeric X values enable proper pan/zoom calculations
- Labels visually unchanged (tick callback formats them)
