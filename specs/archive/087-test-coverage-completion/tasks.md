# Tasks: Test Coverage Completion

**Input**: Design documents from `/specs/087-test-coverage-completion/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Tests**: This feature IS the tests. No separate "test tasks" - implementation tasks are test writing tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish baseline coverage and validate existing test infrastructure

- [x] T001 Run coverage analysis to capture current baseline in tests/unit/ (`pytest --cov=src.lambdas.dashboard.handler --cov=src.lambdas.analysis.sentiment --cov-report=term-missing tests/unit/`)
- [x] T002 Verify `assert_error_logged` and `assert_warning_logged` helpers exist in tests/conftest.py
- [x] T003 Run pre-commit hook to identify current unasserted ERROR logs (`./scripts/check-error-log-assertions.sh --verbose`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Create dedicated test file and shared fixtures for SSE Lambda testing

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Create tests/unit/dashboard/test_dashboard_handler_sse.py with base test class and moto fixtures per FR-014
- [x] T005 [P] Add mock_sse_generator fixture to tests/unit/dashboard/conftest.py (AsyncMock pattern from research.md)
- [x] T006 [P] Add mock_model_tar fixture (tar.gz with config.json) to tests/unit/conftest.py per quickstart.md pattern

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Dashboard Handler Coverage (Priority: P1) 🎯 MVP

**Goal**: Increase dashboard handler coverage from 71% to ≥85% by adding tests for SSE streaming, error handlers, and static file initialization

**Independent Test**: `pytest --cov=src.lambdas.dashboard.handler --cov-fail-under=85 tests/unit/`

### SSE Streaming Tests (lines 548-576, 642-656)

- [x] T007 [US1] Add test_get_dashboard_metrics_dynamodb_error() in tests/unit/test_dashboard_handler.py for lines 548-576
- [x] T008 [US1] Add test_get_dashboard_metrics_aggregation() in tests/unit/test_dashboard_handler.py for metrics calculation path
- [x] T009 [US1] Add test_get_sentiment_v2_dynamodb_error() in tests/unit/test_dashboard_handler.py for lines 642-656

### SSE Lambda Tests (dedicated file per FR-014)

- [x] T010 [P] [US1] Add TestSSEHeartbeat class in tests/unit/dashboard/test_dashboard_handler_sse.py for SSE heartbeat generation
- [x] T011 [P] [US1] Add TestSSEClientDisconnect class in tests/unit/dashboard/test_dashboard_handler_sse.py for disconnect handling
- [x] T012 [P] [US1] Add TestSSEConnectionLimit class in tests/unit/dashboard/test_dashboard_handler_sse.py for 503 at limit

### Trend Endpoint Error Handlers (lines 715-758)

- [x] T013 [US1] Add test_get_trend_v2_range_parsing_edge_cases() in tests/unit/test_dashboard_handler.py for lines 715-716, 729, 736
- [x] T014 [US1] Add test_get_trend_v2_value_error() in tests/unit/test_dashboard_handler.py for lines 743-750
- [x] T015 [US1] Add test_get_trend_v2_generic_exception() in tests/unit/test_dashboard_handler.py for lines 751-758

### Articles Endpoint Error Handlers (lines 800, 835-849)

- [x] T016 [US1] Add test_get_articles_v2_limit_validation() in tests/unit/test_dashboard_handler.py for line 800
- [x] T017 [US1] Add test_get_articles_v2_value_error() in tests/unit/test_dashboard_handler.py for lines 835-840
- [x] T018 [US1] Add test_get_articles_v2_generic_exception() in tests/unit/test_dashboard_handler.py for lines 841-849

### Static File and API Key Initialization (lines 104-163)

- [x] T019 [US1] Add test_get_api_key_secrets_manager_fallback() in tests/unit/test_dashboard_handler.py for lines 104-118
- [x] T020 [US1] Add test_lifespan_startup_shutdown_logging() in tests/unit/test_dashboard_handler.py for lines 131, 155-163
- [x] T021 [US1] Add test_verify_api_key_error_path() in tests/unit/test_dashboard_handler.py for lines 225-229

### Item Retrieval Error Handlers (lines 290-322)

- [x] T022 [P] [US1] Add test_get_items_error_handler() in tests/unit/test_dashboard_handler.py for lines 290-294
- [x] T023 [P] [US1] Add test_get_item_error_handler() in tests/unit/test_dashboard_handler.py for lines 318-322

### Static File Edge Cases (lines 352-384)

- [x] T024 [US1] Add test_static_file_serving_edge_cases() in tests/unit/test_dashboard_handler.py for lines 352-353, 368, 384

### Chaos Endpoint Error Handlers (lines 910-1136)

- [x] T025 [P] [US1] Add test_chaos_error_response_formatting() in tests/unit/test_dashboard_handler.py for lines 910-911, 937-938
- [x] T026 [P] [US1] Add test_get_chaos_experiment_fis_error() in tests/unit/test_dashboard_handler.py for lines 975-989
- [x] T027 [P] [US1] Add test_chaos_start_stop_errors() in tests/unit/test_dashboard_handler.py for lines 1029-1030, 1057-1071
- [x] T028 [P] [US1] Add test_delete_chaos_experiment_error() in tests/unit/test_dashboard_handler.py for lines 1126-1136

**Checkpoint**: At this point, dashboard handler coverage should be ≥85%. Run validation command to confirm.

---

## Phase 4: User Story 2 - Log Assertion Completion (Priority: P2)

**Goal**: Add explicit `assert_error_logged()` calls for all 21 documented error patterns

**Independent Test**: `./scripts/check-error-log-assertions.sh --verbose` reports zero unasserted ERROR logs

### Analysis Handler Assertions (6 patterns)

- [ ] T029 [P] [US2] Add assert_error_logged(caplog, "Inference error: CUDA") in tests/unit/test_analysis_handler.py
- [ ] T030 [P] [US2] Add assert_error_logged(caplog, "Invalid SNS message format") in tests/unit/test_analysis_handler.py
- [ ] T031 [P] [US2] Add assert_error_logged(caplog, "Model load error") in tests/unit/test_sentiment.py
- [ ] T032 [P] [US2] Add assert_error_logged(caplog, "Failed to load model: Model files missing") in tests/unit/test_sentiment.py
- [ ] T033 [P] [US2] Add assert_error_logged(caplog, "Failed to load model: Model not found") in tests/unit/test_sentiment.py
- [ ] T034 [P] [US2] Add assert_error_logged(caplog, "Inference failed: CUDA") in tests/unit/test_sentiment.py

### Ingestion Handler Assertions (6 patterns)

- [ ] T035 [P] [US2] Add assert_error_logged(caplog, "Circuit breaker opened") in tests/unit/test_newsapi_adapter.py
- [ ] T036 [P] [US2] Add assert_error_logged(caplog, "NewsAPI authentication failed") in tests/unit/test_ingestion_handler.py
- [ ] T037 [P] [US2] Add assert_error_logged(caplog, "Authentication error: Invalid NewsAPI key") in tests/unit/test_ingestion_handler.py
- [ ] T038 [P] [US2] Add assert_error_logged(caplog, "Authentication failed for NewsAPI") in tests/unit/test_ingestion_handler.py
- [ ] T039 [P] [US2] Add assert_error_logged(caplog, "Configuration error: WATCH_TAGS") in tests/unit/test_ingestion_handler.py
- [ ] T040 [P] [US2] Add assert_error_logged(caplog, "Unexpected error: Secret not found") in tests/unit/test_ingestion_handler.py

### Shared Module Assertions (6 patterns)

- [ ] T041 [P] [US2] Add assert_error_logged(caplog, "Database operation failed: put_item") in tests/unit/test_errors.py
- [ ] T042 [P] [US2] Add assert_error_logged(caplog, "Database operation failed: query") in tests/unit/test_errors.py
- [ ] T043 [P] [US2] Add assert_error_logged(caplog, "Failed to retrieve configuration") in tests/unit/test_errors.py
- [ ] T044 [P] [US2] Add assert_error_logged(caplog, "Internal error details") in tests/unit/test_errors.py
- [ ] T045 [P] [US2] Add assert_error_logged(caplog, "Model loading failed") in tests/unit/test_sentiment.py
- [ ] T046 [P] [US2] Add assert_error_logged(caplog, "Sentiment analysis failed") in tests/unit/test_sentiment.py

### Secrets Assertions (2 patterns)

- [ ] T047 [P] [US2] Add assert_error_logged(caplog, "Failed to parse secret as JSON") in tests/unit/test_secrets.py
- [ ] T048 [P] [US2] Add assert_error_logged(caplog, "Secret not found") in tests/unit/test_secrets.py

### Metrics Assertions (1 pattern)

- [ ] T049 [P] [US2] Add assert_error_logged(caplog, "Failed to emit metric") in tests/unit/test_metrics.py

**Checkpoint**: At this point, all 21 error patterns should have explicit assertions. Run validation command to confirm.

---

## Phase 5: User Story 3 - Sentiment Model Coverage Verification (Priority: P3)

**Goal**: Verify sentiment model maintains ≥85% coverage and add S3 download path tests

**Independent Test**: `pytest --cov=src.lambdas.analysis.sentiment --cov-fail-under=85 tests/unit/`

### S3 Model Download Tests (lines 83-141)

- [ ] T050 [US3] Add TestS3ModelDownload class in tests/unit/test_sentiment.py
- [ ] T051 [US3] Add test_download_model_from_s3_success() with moto S3 mock in tests/unit/test_sentiment.py
- [ ] T052 [US3] Add test_download_model_from_s3_not_found() for NoSuchKey error in tests/unit/test_sentiment.py
- [ ] T053 [US3] Add test_download_model_from_s3_throttling() for retry/backoff in tests/unit/test_sentiment.py
- [ ] T054 [US3] Add test_download_model_cached_skip() for warm container path in tests/unit/test_sentiment.py

### S3 Error Path Log Assertions

- [ ] T055 [US3] Add assert_error_logged(caplog, "Failed to download model from S3") in test_download_model_from_s3_not_found

**Checkpoint**: Sentiment model coverage should remain ≥85% with S3 download path now covered.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and documentation updates

- [ ] T056 Run full coverage validation: `pytest --cov=src.lambdas.dashboard.handler --cov=src.lambdas.analysis.sentiment --cov-fail-under=85 tests/unit/`
- [ ] T057 Run all unit tests: `pytest -v --tb=short tests/unit/`
- [ ] T058 Run pre-commit hook validation: `./scripts/check-error-log-assertions.sh`
- [ ] T059 Update TEST_LOG_ASSERTIONS_TODO.md to mark completed patterns
- [ ] T060 Update TECH_DEBT_REGISTRY.md to close related entries

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - establishes baseline
- **Foundational (Phase 2)**: Depends on Setup completion - creates shared fixtures
- **User Story 1 (Phase 3)**: Depends on Foundational - MUST complete before US2/US3 for coverage baseline
- **User Story 2 (Phase 4)**: Depends on US1 completion (some assertions belong to tests added in US1)
- **User Story 3 (Phase 5)**: Can start after Foundational but logically after US1
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational phase required - creates new tests that US2 may need to add assertions to
- **User Story 2 (P2)**: US1 should complete first (new tests from US1 may need log assertions)
- **User Story 3 (P3)**: Independent of US1/US2 but logically ordered last (lowest priority)

### Within Each User Story

- Tests grouped by logical area (SSE, error handlers, etc.)
- Tasks within each area can run in parallel where marked [P]
- Verify after each group before moving to next

### Parallel Opportunities

- T005 and T006 can run in parallel (different conftest.py files)
- T010, T011, T012 can run in parallel (same file, different test classes)
- T022, T023 can run in parallel (different test functions, no dependencies)
- T025, T026, T027, T028 can run in parallel (chaos endpoints are independent)
- All US2 tasks (T029-T049) can run in parallel (adding assertions to existing tests in different files)

---

## Parallel Example: User Story 1 - Chaos Endpoints

```bash
# Launch all chaos endpoint tests together (parallel):
Task: T025 test_chaos_error_response_formatting() in tests/unit/test_dashboard_handler.py
Task: T026 test_get_chaos_experiment_fis_error() in tests/unit/test_dashboard_handler.py
Task: T027 test_chaos_start_stop_errors() in tests/unit/test_dashboard_handler.py
Task: T028 test_delete_chaos_experiment_error() in tests/unit/test_dashboard_handler.py
```

---

## Parallel Example: User Story 2 - Log Assertions

```bash
# Launch all ingestion handler assertions together (parallel):
Task: T035 assert_error_logged in tests/unit/test_newsapi_adapter.py
Task: T036 assert_error_logged in tests/unit/test_ingestion_handler.py
Task: T037 assert_error_logged in tests/unit/test_ingestion_handler.py
Task: T038 assert_error_logged in tests/unit/test_ingestion_handler.py
Task: T039 assert_error_logged in tests/unit/test_ingestion_handler.py
Task: T040 assert_error_logged in tests/unit/test_ingestion_handler.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (baseline measurement)
2. Complete Phase 2: Foundational (SSE fixtures)
3. Complete Phase 3: User Story 1 (dashboard handler coverage)
4. **STOP and VALIDATE**: Run `pytest --cov=src.lambdas.dashboard.handler --cov-fail-under=85 tests/unit/`
5. If passing, MVP is complete (primary success criteria SC-001 met)

### Incremental Delivery

1. Complete Setup + Foundational → Fixtures ready
2. Add User Story 1 → Validate coverage ≥85% → SC-001 met (MVP!)
3. Add User Story 2 → Validate zero unasserted logs → SC-003/SC-006 met
4. Add User Story 3 → Validate sentiment coverage → SC-002 maintained
5. Run Polish → All success criteria met

### Task Count Summary

| Phase | Task Range | Count | Parallel Opportunities |
|-------|------------|-------|----------------------|
| Setup | T001-T003 | 3 | 0 |
| Foundational | T004-T006 | 3 | 2 (T005, T006) |
| US1 (Dashboard) | T007-T028 | 22 | 12 |
| US2 (Log Assertions) | T029-T049 | 21 | 21 (all parallel) |
| US3 (Sentiment) | T050-T055 | 6 | 0 |
| Polish | T056-T060 | 5 | 0 |
| **Total** | T001-T060 | **60** | **35** |

---

## Notes

- [P] tasks = different files or independent test functions
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable with specific commands
- Line numbers from research.md are hints - re-run coverage to find current uncovered lines
- 30-second max per test (10s warmup + 20s execution)
- Use substring matching for log assertions (not exact string)
