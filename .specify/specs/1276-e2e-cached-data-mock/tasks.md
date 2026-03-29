# Tasks: E2E Cached Data Mock

**Input**: Design documents from `/specs/1276-e2e-cached-data-mock/`
**Prerequisites**: plan.md (required), spec.md (required)

## Phase 1: Shared Mock Data Helper

**Purpose**: Create the mock data and route interception utility

- [x] T001 [US1] Create `frontend/tests/e2e/helpers/mock-api-data.ts` with pre-canned AAPL search, OHLC, and sentiment responses
- [x] T002 [US1] Implement `mockTickerDataApis(page)` function that sets up `page.route()` for all three endpoints

**Checkpoint**: Mock helper importable and returns valid data shapes

---

## Phase 2: Update Chaos Tests

**Purpose**: Wire mock helper into failing tests

- [x] T003 [P] [US1] Update `frontend/tests/e2e/chaos-cached-data.spec.ts` to use `mockTickerDataApis()` in beforeEach
- [x] T004 [P] [US1] Update `frontend/tests/e2e/chaos-cross-browser.spec.ts` to use `mockTickerDataApis()` in "cached data persists" test

**Checkpoint**: All three failing tests pass within 10s each

---

## Phase 3: Verification

**Purpose**: Confirm no regressions

- [ ] T005 Run full chaos test suite to verify no other tests broken
- [ ] T006 Verify sanity.spec.ts still passes (unchanged, uses real API)

---

## Dependencies & Execution Order

- T001, T002 must complete before T003, T004
- T003 and T004 can run in parallel (different files)
- T005, T006 run after T003, T004
