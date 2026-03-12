# Tasks: Price-Sentiment Overlay Chart

**Input**: Design documents from `/specs/011-price-sentiment-overlay/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ohlc-api.yaml, quickstart.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `src/lambdas/` (Python Lambda)
- **Frontend**: `frontend/src/` (Next.js)
- **Tests**: `tests/` (backend), `frontend/tests/` (frontend)

---

## Phase 1: Setup

**Purpose**: Verify project structure and dependencies are ready

- [x] T001 Verify TradingView Lightweight Charts 5.0.9 is installed in frontend/package.json
- [x] T002 [P] Verify existing Tiingo adapter has get_ohlc() method in src/lambdas/shared/adapters/tiingo.py
- [x] T003 [P] Verify existing Finnhub adapter has get_ohlc() method in src/lambdas/shared/adapters/finnhub.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared models and types that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create TimeRange enum and OHLC response models in src/lambdas/shared/models/ohlc.py
- [x] T005 [P] Create SentimentHistoryResponse model in src/lambdas/shared/models/sentiment_history.py
- [x] T006 [P] Create frontend TypeScript types in frontend/src/types/chart.ts (TimeRange, SentimentSource, PriceCandle, SentimentPoint)
- [x] T007 Implement get_cache_expiration() market-hours function in src/lambdas/shared/utils/market.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 2 - Access Historical Price Data (Priority: P1)

**Goal**: Provide OHLC endpoint so users can retrieve historical price data for any ticker

**Independent Test**: Call GET /api/v2/tickers/AAPL/ohlc and verify OHLC response with candles array

### Tests for User Story 2

- [x] T008 [P] [US2] Unit test for OHLC endpoint in tests/unit/dashboard/test_ohlc.py
- [x] T009 [P] [US2] Contract test validating OHLCResponse schema in tests/contract/test_ohlc_contract.py

### Implementation for User Story 2

- [x] T010 [US2] Create OHLC endpoint handler in src/lambdas/dashboard/ohlc.py with Tiingo primary/Finnhub fallback
- [x] T011 [US2] Register OHLC router in src/lambdas/dashboard/handler.py
- [x] T012 [US2] Add date range filtering (range param: 1W, 1M, 3M, 6M, 1Y) to OHLC endpoint
- [x] T013 [US2] Add custom start_date/end_date query param support to OHLC endpoint
- [x] T014 [US2] Implement cache expiration header using get_cache_expiration() in OHLC response

**Checkpoint**: OHLC endpoint is functional - can test via curl/Postman independently

---

## Phase 4: User Story 1 - View Price and Sentiment Together (Priority: P1)

**Goal**: Display dual-axis chart with price candlesticks (left) and sentiment line (right)

**Independent Test**: View ticker details page and verify chart renders with both series and proper axis scales

**Depends on**: User Story 2 (OHLC endpoint must be available)

### Backend: Sentiment History Endpoint

- [x] T015 [US1] Add sentiment history endpoint GET /api/v2/tickers/{ticker}/sentiment/history in src/lambdas/dashboard/ohlc.py
- [x] T016 [US1] Add source query param (tiingo, finnhub, our_model, aggregated) to sentiment history endpoint
- [x] T017 [P] [US1] Unit test for sentiment history endpoint in tests/unit/dashboard/test_sentiment_history.py

### Frontend: API Client

- [x] T018 [P] [US1] Create fetchOHLCData() function in frontend/src/lib/api/ohlc.ts
- [x] T019 [P] [US1] Create fetchSentimentHistory() function in frontend/src/lib/api/ohlc.ts

### Frontend: Data Hook

- [x] T020 [US1] Create useChartData() React Query hook in frontend/src/hooks/use-chart-data.ts

### Frontend: Chart Component

- [x] T021 [US1] Create PriceSentimentChart component shell in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T022 [US1] Initialize TradingView chart with dual price scales (left for price, right for sentiment)
- [x] T023 [US1] Add candlestick series on left axis with green/red styling
- [x] T024 [US1] Add line series on right axis for sentiment (-1 to +1 scale)
- [x] T025 [US1] Implement crosshair tooltip showing date, OHLC, and sentiment score
- [x] T026 [US1] Add loading skeleton/spinner while data is fetching
- [x] T027 [US1] Add error state with retry option
- [x] T028 [US1] Handle resize events for responsive chart

### Frontend: Integration

- [ ] T029 [US1] Integrate PriceSentimentChart into ticker detail view (replace or augment existing sentiment chart)

### Tests for User Story 1

- [ ] T030 [P] [US1] Component test for PriceSentimentChart in frontend/tests/unit/charts/price-sentiment-chart.test.tsx

**Checkpoint**: Dual-axis chart renders price candles and sentiment line together

---

## Phase 5: User Story 3 - Customize Chart Time Range (Priority: P2)

**Goal**: Allow users to select time ranges (1W, 1M, 3M, 6M, 1Y) to analyze different periods

**Independent Test**: Select "3M" button and verify chart updates to show 90 days of data

### Implementation for User Story 3

- [x] T031 [US3] Add time range selector buttons (1W, 1M, 3M, 6M, 1Y) to PriceSentimentChart
- [x] T032 [US3] Add timeRange state with default "1M" in PriceSentimentChart
- [x] T033 [US3] Update useChartData hook to refetch when timeRange changes
- [x] T034 [US3] Style active time range button with accent color

### Tests for User Story 3

- [ ] T035 [P] [US3] Test time range selection triggers data refetch in frontend/tests/unit/charts/price-sentiment-chart.test.tsx

**Checkpoint**: Time range buttons work and chart updates accordingly

---

## Phase 6: User Story 4 - Toggle Chart Layers (Priority: P3)

**Goal**: Allow users to show/hide price candles and sentiment line independently

**Independent Test**: Click "Sentiment" toggle off and verify only price candles remain visible

### Implementation for User Story 4

- [x] T036 [US4] Add showCandles and showSentiment state to PriceSentimentChart
- [x] T037 [US4] Add toggle buttons for Price and Sentiment layers
- [x] T038 [US4] Apply series visibility via applyOptions({ visible: boolean })
- [x] T039 [US4] Style toggle buttons to show active/inactive state

### Sentiment Source Selector (FR-013)

- [x] T040 [US4] Add sentimentSource state with default "aggregated" in PriceSentimentChart
- [x] T041 [US4] Add dropdown selector for sentiment source (Tiingo, Finnhub, our_model, aggregated)
- [x] T042 [US4] Update useChartData hook to refetch sentiment when source changes

### Tests for User Story 4

- [ ] T043 [P] [US4] Test layer toggles update chart visibility in frontend/tests/unit/charts/price-sentiment-chart.test.tsx

**Checkpoint**: Layer toggles and sentiment source selector work independently

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Edge cases, accessibility, and performance

- [ ] T044 Handle missing price data for certain dates (show sentiment without candles)
- [ ] T045 Handle weekends/holidays alignment (sentiment exists, price gaps)
- [x] T046 [P] Add legend showing price (left axis) and sentiment (right axis) scales
- [x] T047 [P] Ensure chart is responsive on mobile (320px+) and desktop (1024px+)
- [x] T048 Add aria-labels and keyboard navigation for chart controls
- [ ] T049 [P] Run quickstart.md validation scenarios
- [x] T050 Update component exports if needed in frontend/src/components/charts/index.ts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **US2 (Phase 3)**: Depends on Foundational - backend OHLC endpoint
- **US1 (Phase 4)**: Depends on US2 (needs OHLC endpoint) + Foundational
- **US3 (Phase 5)**: Depends on US1 (enhances chart component)
- **US4 (Phase 6)**: Depends on US1 (enhances chart component)
- **Polish (Phase 7)**: Depends on US1, US3, US4 being complete

### User Story Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (models, types)
    ↓
Phase 3: US2 - OHLC Endpoint (P1) ← Backend prerequisite
    ↓
Phase 4: US1 - Chart Visualization (P1) ← Core frontend feature
    ↓
    ├── Phase 5: US3 - Time Range (P2) ← Can run after US1
    └── Phase 6: US4 - Layer Toggles (P3) ← Can run after US1 (or parallel with US3)
            ↓
        Phase 7: Polish
```

### Parallel Opportunities

**Within Phase 2 (Foundational)**:
```
T005, T006 can run in parallel (different files)
```

**Within Phase 3 (US2)**:
```
T008, T009 can run in parallel (test files)
```

**Within Phase 4 (US1)**:
```
T017, T018, T019 can run in parallel (different files)
T030 can run parallel with other US1 tests
```

**After US1 completes**:
```
US3 and US4 can run in parallel (different aspects of same component)
```

---

## Parallel Example: User Story 1

```bash
# Launch backend sentiment endpoint and frontend API client in parallel:
Task: T015 "Add sentiment history endpoint in src/lambdas/dashboard/sentiment.py"
Task: T018 "Create fetchOHLCData() in frontend/src/services/ohlc-api.ts"
Task: T019 "Create fetchSentimentHistory() in frontend/src/services/ohlc-api.ts"

# After API client ready, launch chart implementation:
Task: T021-T028 "PriceSentimentChart component implementation"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Complete Phase 1: Setup (verify dependencies)
2. Complete Phase 2: Foundational (models, types)
3. Complete Phase 3: US2 - OHLC Endpoint
4. Complete Phase 4: US1 - Basic Chart (default 1M range, aggregated sentiment)
5. **STOP and VALIDATE**: Test chart independently with AAPL
6. Deploy/demo if ready - users can view price+sentiment correlation

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US2 → OHLC endpoint available → Can test backend independently
3. Add US1 → Chart renders → MVP complete!
4. Add US3 → Time range selection → Enhanced analytics
5. Add US4 → Layer toggles + source selector → Full feature
6. Polish → Edge cases, accessibility → Production ready

### Task Counts

| Phase | Tasks | Parallel |
|-------|-------|----------|
| Setup | 3 | 2 |
| Foundational | 4 | 2 |
| US2 (P1) | 7 | 2 |
| US1 (P1) | 16 | 5 |
| US3 (P2) | 5 | 1 |
| US4 (P3) | 9 | 1 |
| Polish | 7 | 3 |
| **Total** | **51** | **16** |

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- US2 provides backend data, US1 consumes it in frontend
- US3 and US4 can be deferred post-MVP without breaking core functionality
- All tests follow existing project patterns (pytest for backend, Vitest for frontend)
- Commit after each task or logical group
