# Implementation Tasks: OHLC Pan-to-Load

**Feature**: 1101-ohlc-pan-to-load
**Generated**: 2025-12-29

## Overview

Implement bidirectional infinite scroll for OHLC chart using lightweight-charts API.

**Total Tasks**: 7

## Phase 1: Setup

- [ ] T001 Verify backend OHLC API supports `startDate`/`endDate` pagination in `src/lambdas/dashboard/ohlc.py`

## Phase 2: Foundational

- [ ] T002 [P] Create `frontend/src/hooks/use-pan-to-load.ts` with edge detection logic
- [ ] T003 [P] Add pagination params to `frontend/src/lib/api/ohlc.ts` fetchOHLCData function

## Phase 3: User Story 1 - Pan Left for History (P1)

- [ ] T004 [US1] Modify `frontend/src/hooks/use-chart-data.ts` to support `loadMoreHistory(beforeDate)`
- [ ] T005 [US1] Integrate pan-to-load hook in `frontend/src/components/charts/price-sentiment-chart.tsx`

## Phase 4: User Story 2 - Pan Right for Recent (P2)

- [ ] T006 [US2] Add `loadMoreRecent(afterDate)` to `frontend/src/hooks/use-chart-data.ts`

## Phase 5: Polish

- [ ] T007 Add loading indicator at chart edge when fetching

## Acceptance Criteria

1. ✅ Pan left loads older data automatically
2. ✅ Pan right returns to recent data
3. ✅ No duplicate requests during rapid panning
4. ✅ Scroll position maintained when data prepended
