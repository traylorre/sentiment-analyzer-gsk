# Tasks: Timeseries Integration Test Suite

**Input**: Design documents from `/specs/1016-timeseries-integration-test/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/test-oracle.yaml, quickstart.md

**Organization**: Tasks organized by user story. This feature implements integration tests, so tests ARE the deliverables.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files/classes, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Create test module structure and shared fixtures

- [x] T001 Create `tests/integration/timeseries/__init__.py` module package
- [x] T002 Create `tests/integration/timeseries/conftest.py` with class-scoped table fixtures per RQ-001

**Checkpoint**: Test infrastructure ready for test implementation

---

## Phase 2: Foundational (Shared Test Fixtures)

**Purpose**: Fixtures that ALL test classes depend on - MUST complete before any user story tests

**⚠️ CRITICAL**: No test implementation can begin until this phase is complete

- [x] T003 Implement `timeseries_table` fixture in `tests/integration/timeseries/conftest.py` that creates/tears down DynamoDB table per class
- [x] T004 Implement `sample_score` fixture in `tests/integration/timeseries/conftest.py` returning SentimentScore with fixed timestamp 2024-01-02T10:35:47Z
- [x] T005 [P] Implement `ohlc_scores` fixture in `tests/integration/timeseries/conftest.py` returning list of 4 scores [0.6, 0.9, 0.3, 0.7] per test-oracle.yaml
- [x] T006 [P] Implement `query_timestamps` fixture in `tests/integration/timeseries/conftest.py` returning 5 timestamps for ordering tests

**Checkpoint**: Fixtures verified with `pytest tests/integration/timeseries/conftest.py --collect-only`

---

## Phase 3: User Story 1 - Validate Write Fanout (Priority: P1) 🎯 MVP

**Goal**: Verify single sentiment score correctly produces 8 DynamoDB items (one per resolution)

**Independent Test**: Run `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout -v`

### Implementation for User Story 1

- [x] T007 [US1] Create TestWriteFanout class skeleton in `tests/integration/timeseries/test_timeseries_pipeline.py`
- [x] T008 [US1] Implement `test_fanout_creates_8_resolution_items` - verify exactly 8 items after single score ingestion per FR-003
- [x] T009 [US1] Implement `test_partition_key_format` - verify PK format `{ticker}#{resolution}` per FR-004 and [CS-002]
- [x] T010 [US1] Implement `test_bucket_timestamps_aligned` - verify SK timestamps aligned to resolution boundaries per FR-005

**Checkpoint**: `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestWriteFanout -v` passes (3 tests)

---

## Phase 4: User Story 2 - Validate Query Ordering (Priority: P1)

**Goal**: Verify queries return buckets in ascending timestamp order regardless of insertion order

**Independent Test**: Run `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering -v`

### Implementation for User Story 2

- [x] T011 [US2] Create TestQueryOrdering class skeleton in `tests/integration/timeseries/test_timeseries_pipeline.py`
- [x] T012 [US2] Implement `test_query_returns_ascending_order` - verify 5 buckets return in sorted order per FR-006
- [x] T013 [US2] Implement `test_out_of_order_insert_returns_sorted` - insert out-of-order, verify sorted response
- [x] T014 [US2] Implement `test_empty_range_returns_empty_list` - verify empty list (not error) for no-match range

**Checkpoint**: `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestQueryOrdering -v` passes (3 tests)

---

## Phase 5: User Story 3 - Validate Partial Bucket Flagging (Priority: P2)

**Goal**: Verify current in-progress bucket flagged as partial with correct progress percentage

**Independent Test**: Run `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket -v`

### Implementation for User Story 3

- [x] T015 [US3] Create TestPartialBucket class skeleton in `tests/integration/timeseries/test_timeseries_pipeline.py`
- [x] T016 [US3] Implement `test_current_bucket_flagged_partial` - use freezegun mid-bucket, verify `is_partial=True` per FR-007
- [x] T017 [US3] Implement `test_progress_percentage_calculated` - verify 50% at 2.5min into 5min bucket per Amendment 1.5
- [x] T018 [US3] Implement `test_complete_bucket_not_partial` - verify completed bucket has `is_partial=False` and 100%

**Checkpoint**: `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestPartialBucket -v` passes (3 tests)

---

## Phase 6: User Story 4 - Validate OHLC Aggregation (Priority: P2)

**Goal**: Verify multiple scores aggregate correctly into OHLC values with label counts

**Independent Test**: Run `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation -v`

### Implementation for User Story 4

- [x] T019 [US4] Create TestOHLCAggregation class skeleton in `tests/integration/timeseries/test_timeseries_pipeline.py`
- [x] T020 [US4] Implement `test_ohlc_values_correct` - verify open=0.6, high=0.9, low=0.3, close=0.7 per FR-008 and test-oracle.yaml
- [x] T021 [US4] Implement `test_label_counts_aggregated` - verify {positive: 2, neutral: 1, negative: 1}
- [x] T022 [US4] Implement `test_avg_and_count_calculated` - verify avg=0.625, count=4 using pytest.approx

**Checkpoint**: `pytest tests/integration/timeseries/test_timeseries_pipeline.py::TestOHLCAggregation -v` passes (3 tests)

---

## Phase 7: Polish & Validation

**Purpose**: Final validation and documentation

- [x] T023 [P] Run full test suite: `pytest tests/integration/timeseries/ -v` - verify all 12 tests pass (tests collected OK, require LocalStack)
- [ ] T024 [P] Run 10 consecutive times: verify SC-003 (no flaky tests) - requires LocalStack
- [ ] T025 [P] Measure execution time: verify SC-002 (<60 seconds) - requires LocalStack
- [ ] T026 Run coverage: `pytest tests/integration/timeseries/ --cov=src/lib/timeseries --cov-report=term-missing` - verify SC-004 (>80%) - requires LocalStack
- [ ] T027 Regression test: temporarily break fanout logic, verify at least one test fails (SC-005) - requires LocalStack
- [x] T028 Run quickstart.md validation per spec (syntax verified, ruff passed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user story tests
- **User Stories (Phase 3-6)**: All depend on Phase 2 completion
  - US1 and US2 are P1 priority - implement first
  - US3 and US4 are P2 priority - implement after P1 complete
  - All user stories are independent within their priority tier
- **Polish (Phase 7)**: Depends on all user story phases

### User Story Dependencies

- **US1 (Write Fanout)**: No dependencies on other stories - can start after Phase 2
- **US2 (Query Ordering)**: No dependencies on other stories - can start after Phase 2
- **US3 (Partial Bucket)**: No dependencies on other stories - can start after Phase 2
- **US4 (OHLC Aggregation)**: No dependencies on other stories - can start after Phase 2

### Within Each User Story

All tests within a story use shared fixtures but can be implemented in any order.

### Parallel Opportunities

**Phase 2 (Foundational)**:
```
T005 [P] ohlc_scores fixture
T006 [P] query_timestamps fixture
```

**After Phase 2 completes - all stories can proceed in parallel**:
```
US1: T007-T010 (TestWriteFanout)
US2: T011-T014 (TestQueryOrdering)
US3: T015-T018 (TestPartialBucket)
US4: T019-T022 (TestOHLCAggregation)
```

**Phase 7 (Polish)**:
```
T023 [P] Full test suite run
T024 [P] Flaky test verification
T025 [P] Execution time measurement
```

---

## Parallel Example: All User Stories

```bash
# After Phase 2 completes, launch all user story implementations in parallel:
Task US1: "Implement TestWriteFanout in tests/integration/timeseries/test_timeseries_pipeline.py"
Task US2: "Implement TestQueryOrdering in tests/integration/timeseries/test_timeseries_pipeline.py"
Task US3: "Implement TestPartialBucket in tests/integration/timeseries/test_timeseries_pipeline.py"
Task US4: "Implement TestOHLCAggregation in tests/integration/timeseries/test_timeseries_pipeline.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 + 2 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational fixtures (T003-T006)
3. Complete Phase 3: User Story 1 - Write Fanout (T007-T010)
4. Complete Phase 4: User Story 2 - Query Ordering (T011-T014)
5. **STOP and VALIDATE**: Run `pytest tests/integration/timeseries/ -v` - 6 tests should pass
6. This proves the core pipeline works

### Incremental Delivery

1. Setup + Foundational → Test infrastructure ready
2. Add US1 (Fanout) → 3 tests passing → Core validation complete
3. Add US2 (Query) → 6 tests passing → Data retrieval validated
4. Add US3 (Partial) → 9 tests passing → Real-time indicators validated
5. Add US4 (OHLC) → 12 tests passing → Full aggregation validated
6. Polish → All success criteria verified

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 28 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 4 |
| Phase 3 (US1 - Fanout) | 4 |
| Phase 4 (US2 - Query) | 4 |
| Phase 5 (US3 - Partial) | 4 |
| Phase 6 (US4 - OHLC) | 4 |
| Phase 7 (Polish) | 6 |
| Parallel Opportunities | 10 tasks marked [P] |

**MVP Scope**: Phases 1-4 (14 tasks) delivers write fanout + query ordering validation.

---

## Notes

- [P] tasks = different files/functions, no dependencies
- [Story] label maps task to specific user story
- All test data uses fixed historical dates per Constitution Amendment 1.5
- Use pytest.approx for float comparisons per RQ-005
- Verify LocalStack is running before test execution
- Commit after each phase checkpoint
