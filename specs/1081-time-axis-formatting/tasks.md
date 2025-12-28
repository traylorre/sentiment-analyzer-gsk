# Implementation Tasks: OHLC Time Axis Formatting Fix

**Branch**: `1081-time-axis-formatting` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] Add isDifferentDay helper method in src/dashboard/ohlc.js
- [X] T002 [US1] Update formatTimestamp to accept index and candles array in src/dashboard/ohlc.js
- [X] T003 [US1] Add day boundary detection logic with abbreviated date format in src/dashboard/ohlc.js
- [X] T004 [US1] Update updateChart label generation to pass candle context in src/dashboard/ohlc.js

## Phase 2: Testing

- [X] T005 Create static analysis tests in tests/unit/dashboard/test_time_axis_formatting.py

## Phase 3: Verification

- [ ] T006 Deploy and verify multi-day intraday shows date context
- [ ] T007 Verify single-day data shows time-only labels
- [ ] T008 Verify Day resolution unchanged

## Dependencies

```text
T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008
```

## Notes

- All changes in single file (ohlc.js)
- Backward compatible - Day resolution unchanged
