# Tasks: OHLC Resolution Selector

**Input**: Design documents from `/specs/1035-ohlc-resolution-selector/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ohlc-api.yaml

**Tests**: Unit tests are required per Constitution Section 7 (Implementation Accompaniment Rule).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `src/lambdas/` (Lambda handlers), `src/lambdas/shared/` (shared code)
- **Frontend**: `frontend/src/` (Next.js/React)
- **Tests**: `tests/unit/` (backend), `frontend/src/__tests__/` (frontend)

---

## Phase 1: Setup (No Changes Needed)

**Purpose**: Project structure already exists. No setup tasks required.

**Status**: ✅ SKIPPED - Existing project, all infrastructure in place

---

## Phase 2: Foundational (Backend Resolution Support)

**Purpose**: Backend changes that MUST be complete before ANY frontend work can begin

**⚠️ CRITICAL**: Frontend user story work depends on backend API supporting resolution parameter

### Backend Model & Adapter Changes

- [x] T001 [P] Add OHLCResolution enum with max_days property in src/lambdas/shared/models/ohlc.py
- [x] T002 [P] Add resolution parameter to Finnhub adapter get_ohlc() method in src/lambdas/shared/adapters/finnhub.py
- [x] T003 Update OHLC endpoint to accept resolution query parameter in src/lambdas/dashboard/ohlc.py
- [x] T004 Add time range limiting logic based on resolution in src/lambdas/dashboard/ohlc.py
- [x] T005 Add resolution field to OHLCResponse in src/lambdas/shared/models/ohlc.py
- [x] T006 Add fallback logic when intraday data unavailable in src/lambdas/dashboard/ohlc.py

### Backend Unit Tests

- [x] T007 [P] Add unit tests for OHLCResolution enum validation in tests/unit/lambdas/shared/models/test_ohlc.py
- [x] T008 [P] Add unit tests for Finnhub adapter resolution parameter in tests/unit/lambdas/shared/adapters/test_finnhub.py
- [x] T009 Add unit tests for OHLC endpoint resolution handling in tests/unit/lambdas/dashboard/test_ohlc.py

**Checkpoint**: Backend API accepts resolution parameter and returns data at specified granularity

---

## Phase 3: User Story 1 - View Intraday Price Candles (Priority: P1) 🎯 MVP

**Goal**: Users can select different time resolutions and see candles update accordingly

**Independent Test**: Load chart for AAPL, select "5 min" from dropdown, verify 5-minute candles display

### Frontend Type Definitions

- [x] T010 [P] [US1] Add OHLCResolution type union in frontend/src/types/chart.ts
- [x] T011 [P] [US1] Update OHLCParams interface to include resolution in frontend/src/types/chart.ts
- [x] T012 [P] [US1] Update OHLCResponse interface to include resolution in frontend/src/types/chart.ts

### Frontend API Client

- [x] T013 [US1] Add resolution parameter to fetchOHLCData function in frontend/src/lib/api/ohlc.ts
- [x] T014 [US1] Include resolution in API request URL query params in frontend/src/lib/api/ohlc.ts

### Frontend Hook Updates

- [x] T015 [US1] Add resolution parameter to useChartData hook signature in frontend/src/hooks/use-chart-data.ts
- [x] T016 [US1] Include resolution in React Query cache key in frontend/src/hooks/use-chart-data.ts
- [x] T017 [US1] Pass resolution to fetchOHLCData call in frontend/src/hooks/use-chart-data.ts

### Frontend UI Component

- [x] T018 [US1] Add resolution state with default "D" (daily) in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T019 [US1] Create ResolutionSelector button group component (matches time range pattern) in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T020 [US1] Wire resolution state to useChartData hook in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T021 [US1] Add loading indicator during resolution change in frontend/src/components/charts/price-sentiment-chart.tsx

### Frontend Unit Tests

- [ ] T022 [P] [US1] Add test for resolution selector rendering in frontend/src/__tests__/price-sentiment-chart.test.tsx
- [ ] T023 [P] [US1] Add test for resolution change triggers data refetch in frontend/src/__tests__/price-sentiment-chart.test.tsx

**Checkpoint**: User Story 1 complete - users can select resolutions and see chart update with intraday candles

---

## Phase 4: User Story 2 - Remember Resolution Preference (Priority: P2)

**Goal**: Chart remembers user's last-selected resolution across ticker changes and page navigations

**Independent Test**: Select "15 min" for AAPL, navigate to MSFT, verify "15 min" is pre-selected

### Session Storage Implementation

- [x] T024 [US2] Add sessionStorage read for initial resolution state in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T025 [US2] Add sessionStorage write when resolution changes in frontend/src/components/charts/price-sentiment-chart.tsx
- [x] T026 [US2] Use storage key "ohlc_preferred_resolution" per data model in frontend/src/components/charts/price-sentiment-chart.tsx

### Frontend Unit Tests

- [ ] T027 [P] [US2] Add test for resolution preference persistence in frontend/src/__tests__/price-sentiment-chart.test.tsx
- [ ] T028 [P] [US2] Add test for initial resolution read from sessionStorage in frontend/src/__tests__/price-sentiment-chart.test.tsx

**Checkpoint**: User Story 2 complete - resolution preference persists across navigation

---

## Phase 5: User Story 3 - Synchronized Sentiment and Price Time Axes (Priority: P3)

**Goal**: Price candles and sentiment overlay share the same time axis at selected resolution

**Independent Test**: Enable both price and sentiment layers, select 5m resolution, verify both update together

### Sentiment Resolution Support

- [x] T029 [US3] Pass resolution to sentiment history fetch in frontend/src/hooks/use-chart-data.ts
- [x] T030 [US3] Update tooltip to show aligned OHLC + sentiment values in frontend/src/components/charts/price-sentiment-chart.tsx

### Frontend Unit Tests

- [ ] T031 [P] [US3] Add test for synchronized resolution between price and sentiment in frontend/src/__tests__/price-sentiment-chart.test.tsx

**Checkpoint**: User Story 3 complete - price and sentiment data synchronized on time axis

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple components

- [x] T032 Add error message display when resolution unavailable (fallback to daily) in frontend/src/components/charts/price-sentiment-chart.tsx
- [ ] T033 [P] Run make validate to ensure code quality in project root
- [ ] T034 [P] Verify quickstart.md examples work with new resolution parameter

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: SKIPPED - existing project
- **Phase 2 (Foundational)**: No dependencies - start immediately, BLOCKS all frontend work
- **Phase 3 (US1)**: Depends on Phase 2 completion
- **Phase 4 (US2)**: Depends on Phase 3 completion (needs resolution state to persist)
- **Phase 5 (US3)**: Depends on Phase 3 completion (needs resolution selector working)
- **Phase 6 (Polish)**: Depends on US1-US3 completion

### User Story Dependencies

- **User Story 1 (P1)**: Depends only on Foundational (Phase 2) - MVP deliverable
- **User Story 2 (P2)**: Depends on US1 (needs resolution state to exist)
- **User Story 3 (P3)**: Depends on US1 (needs resolution selection working), integrates with sentiment

### Within Each Phase

- Backend: Models → Adapters → Endpoints → Tests
- Frontend: Types → API Client → Hooks → Components → Tests
- Tests can run in parallel within their phase

### Parallel Opportunities

**Phase 2 (Foundational)**:
- T001, T002 can run in parallel (different files)
- T007, T008 can run in parallel (different test files)

**Phase 3 (US1)**:
- T010, T011, T012 can run in parallel (all in chart.ts but different exports)
- T022, T023 can run in parallel (same test file but independent tests)

**Phase 4 (US2)**:
- T027, T028 can run in parallel (independent tests)

---

## Parallel Example: Phase 2 Backend

```bash
# Launch model and adapter changes together:
Task: "Add OHLCResolution enum in src/lambdas/shared/models/ohlc.py"
Task: "Add resolution parameter to Finnhub adapter in src/lambdas/shared/adapters/finnhub.py"

# After above complete, launch tests together:
Task: "Unit tests for OHLCResolution enum in tests/unit/lambdas/shared/models/test_ohlc.py"
Task: "Unit tests for Finnhub adapter in tests/unit/lambdas/shared/adapters/test_finnhub.py"
```

## Parallel Example: Phase 3 Frontend Types

```bash
# Launch all type changes together:
Task: "Add OHLCResolution type in frontend/src/types/chart.ts"
Task: "Update OHLCParams interface in frontend/src/types/chart.ts"
Task: "Update OHLCResponse interface in frontend/src/types/chart.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (backend resolution support)
2. Complete Phase 3: User Story 1 (frontend resolution selector)
3. **STOP and VALIDATE**: Test resolution selection independently
4. Deploy/demo - feature is demo-able with US1 alone!

### Incremental Delivery

1. Backend (Phase 2) → API supports resolution → Backend tests pass
2. User Story 1 (Phase 3) → Resolution selector works → **MVP DEMO READY**
3. User Story 2 (Phase 4) → Preference persists → Enhanced UX
4. User Story 3 (Phase 5) → Sentiment synced → Full analytical value
5. Polish (Phase 6) → Error handling → Production ready

### Single Developer Sequence

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008 → T009 →
T010 → T011 → T012 → T013 → T014 → T015 → T016 → T017 →
T018 → T019 → T020 → T021 → T022 → T023 →
T024 → T025 → T026 → T027 → T028 →
T029 → T030 → T031 →
T032 → T033 → T034

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [US#] label maps task to specific user story for traceability
- Backend must complete before frontend (Phase 2 blocks Phase 3+)
- Tests are included per Constitution Section 7 (accompaniment rule)
- Commit after each task or logical group
- Stop at US1 checkpoint for demo-able MVP
- Resolution values: "1", "5", "15", "30", "60", "D" (matches Finnhub API)
