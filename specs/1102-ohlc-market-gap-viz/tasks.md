# Implementation Tasks: OHLC Market Gap Visualization

**Feature**: 1102-ohlc-market-gap-viz
**Generated**: 2025-12-29

## Overview

Display market closures as red-shaded rectangles with equal-width candlesticks using Series Primitives API.

**Total Tasks**: 9

## Phase 1: Setup

- [ ] T001 Add GapMarker type to `frontend/src/types/chart.ts`

## Phase 2: Foundational - Market Calendar

- [ ] T002 [P] Create `frontend/src/lib/utils/market-calendar.ts` with US holiday list
- [ ] T003 [P] Add `isMarketOpen(date, resolution)` function to market-calendar.ts
- [ ] T004 Add `fillGaps(candles, resolution)` function to market-calendar.ts

## Phase 3: User Story 1 - Red Shaded Gaps (P1)

- [ ] T005 [US1] Create `frontend/src/components/charts/primitives/gap-shader-primitive.ts`
- [ ] T006 [US1] Implement GapShaderPaneView and GapShaderRenderer classes
- [ ] T007 [US1] Integrate GapShaderPrimitive in `price-sentiment-chart.tsx`

## Phase 4: User Story 2 - Equal Width (P1)

- [ ] T008 [US2] Modify data processing in `use-chart-data.ts` to insert gap markers

## Phase 5: User Story 3 - X-Axis Labels (P2)

- [ ] T009 [US3] Update x-axis tick formatter to display gap dates

## Acceptance Criteria

1. ✅ Weekend gaps show as light red rectangles
2. ✅ Holiday gaps (Christmas, etc.) show as red rectangles
3. ✅ All candlesticks have equal width
4. ✅ X-axis shows continuous dates
5. ✅ Tooltip shows "Market Closed" for gap areas
