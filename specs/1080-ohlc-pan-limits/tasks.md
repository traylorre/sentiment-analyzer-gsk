# Implementation Tasks: OHLC Pan Limits Fix

**Branch**: `1080-ohlc-pan-limits` | **Created**: 2025-12-28

## Phase 1: Implementation

- [X] T001 [US1] [US2] Add X-axis limits to zoom plugin config in src/dashboard/ohlc.js
- [X] T002 [US2] Change pan mode from 'x' to 'xy' in src/dashboard/ohlc.js

## Phase 2: Verification

- [ ] T003 Deploy and verify horizontal pan works (left-right time navigation)
- [ ] T004 Verify vertical pan works after zoom (up-down price navigation)
- [ ] T005 Verify sentiment axis remains fixed at -1 to 1 during vertical pan

## Dependencies

```text
T001 + T002 (parallel) → T003 → T004 → T005
```

## Notes

- Both T001 and T002 modify same file but different sections
- Can be done in single edit
