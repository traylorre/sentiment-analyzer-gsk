# Tasks: Test Debt Burndown

**Input**: Design documents from `/specs/086-test-debt-burndown/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: This feature IS tests - all tasks are test-related.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Prerequisites)

**Purpose**: Complete external prerequisites before starting implementation

- [ ] T001 Verify template repo PR #49 (083-speckit-reverse-engineering) is merged to main
- [ ] T002 Verify template repo PR #50 (085-iam-validator-refactor) is merged to main
- [ ] T003 Sync target repo with latest main: `git fetch origin main && git rebase origin/main`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Verify prerequisites and establish baseline coverage

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T004 Verify `assert_error_logged` helper exists in tests/conftest.py
- [ ] T005 Verify `assert_warning_logged` helper exists in tests/conftest.py
- [ ] T006 Run baseline coverage report: `pytest --cov=src --cov-report=term-missing`
- [ ] T007 Document baseline coverage for dashboard handler (currently 72%)
- [ ] T008 Document baseline coverage for sentiment model (currently 74%)

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Validate Error Logging in Tests (Priority: P1) 🎯 MVP

**Goal**: Add caplog assertions for all 21 documented error patterns

**Independent Test**: Run `pytest -v 2>&1 | grep -E "^ERROR"` - should return zero unasserted ERROR logs

### Implementation for User Story 1

#### Analysis Handler (6 patterns)
- [ ] T009 [P] [US1] Add caplog assertion for "Inference error: CUDA error" in tests/unit/test_analysis_handler.py
- [ ] T010 [P] [US1] Add caplog assertion for "Invalid SNS message format: missing 'timestamp'" in tests/unit/test_analysis_handler.py
- [ ] T011 [P] [US1] Add caplog assertion for "Model load error: Model not found" in tests/unit/test_analysis_handler.py
- [ ] T012 [P] [US1] Add caplog assertion for "Failed to load model: Model files missing" in tests/unit/test_analysis_handler.py
- [ ] T013 [P] [US1] Add caplog assertion for "Failed to load model: Model not found" in tests/unit/test_analysis_handler.py
- [ ] T014 [P] [US1] Add caplog assertion for "Inference failed: CUDA error" in tests/unit/test_analysis_handler.py

#### Ingestion Handler (6 patterns)
- [ ] T015 [P] [US1] Add caplog assertion for "Circuit breaker opened" in tests/unit/test_ingestion_handler.py
- [ ] T016 [P] [US1] Add caplog assertion for "NewsAPI authentication failed" in tests/unit/test_ingestion_handler.py
- [ ] T017 [P] [US1] Add caplog assertion for "Authentication error: Invalid NewsAPI key" in tests/unit/test_ingestion_handler.py
- [ ] T018 [P] [US1] Add caplog assertion for "Authentication failed for NewsAPI" in tests/unit/test_ingestion_handler.py
- [ ] T019 [P] [US1] Add caplog assertion for "Configuration error: WATCH_TAGS" in tests/unit/test_ingestion_handler.py
- [ ] T020 [P] [US1] Add caplog assertion for "Unexpected error: Secret not found" in tests/unit/test_ingestion_handler.py

#### Shared Errors (6 patterns)
- [ ] T021 [P] [US1] Add caplog assertion for "Database operation failed: put_item" in tests/unit/test_errors.py
- [ ] T022 [P] [US1] Add caplog assertion for "Database operation failed: query" in tests/unit/test_errors.py
- [ ] T023 [P] [US1] Add caplog assertion for "Failed to retrieve configuration" in tests/unit/test_errors.py
- [ ] T024 [P] [US1] Add caplog assertion for "Internal error details" in tests/unit/test_errors.py
- [ ] T025 [P] [US1] Add caplog assertion for "Model loading failed" in tests/unit/test_errors.py
- [ ] T026 [P] [US1] Add caplog assertion for "Sentiment analysis failed" in tests/unit/test_errors.py

#### Secrets (2 patterns)
- [ ] T027 [P] [US1] Add caplog assertion for "Failed to parse secret as JSON" in tests/unit/test_secrets.py
- [ ] T028 [P] [US1] Add caplog assertion for "Secret not found" in tests/unit/test_secrets.py

#### Metrics (1 pattern)
- [ ] T029 [P] [US1] Add caplog assertion for "Failed to emit metric: InvalidClientTokenId" in tests/unit/test_metrics.py

#### Validation
- [ ] T030 [US1] Run `pytest tests/unit/ -v --tb=short` to verify all 21 assertions pass
- [ ] T031 [US1] Update docs/TEST_LOG_ASSERTIONS_TODO.md - mark all 21 patterns as complete

**Checkpoint**: User Story 1 complete - all 21 error patterns have explicit assertions (SC-004)

---

## Phase 4: User Story 2 - Improve Dashboard Handler Coverage (Priority: P2)

**Goal**: Increase dashboard handler coverage from 72% to ≥85%

**Independent Test**: Run `pytest --cov=src/lambdas/dashboard/handler --cov-fail-under=85`

### Implementation for User Story 2

#### SSE Streaming Tests (lines 557-628)
- [ ] T032 [P] [US2] Add test for SSE stream initialization in tests/unit/dashboard/test_handler.py
- [ ] T033 [P] [US2] Add test for SSE event generation in tests/unit/dashboard/test_handler.py
- [ ] T034 [P] [US2] Add test for SSE client disconnect with cleanup in tests/unit/dashboard/test_handler.py
- [ ] T035 [P] [US2] Add test for SSE client disconnect logging in tests/unit/dashboard/test_handler.py

#### WebSocket Handling Tests (lines 746-760)
- [ ] T036 [P] [US2] Add test for WebSocket connection handling in tests/unit/dashboard/test_handler.py
- [ ] T037 [P] [US2] Add test for WebSocket message handling in tests/unit/dashboard/test_handler.py
- [ ] T038 [P] [US2] Add test for WebSocket disconnect with cleanup in tests/unit/dashboard/test_handler.py

#### Static File Serving Tests (lines 115-129)
- [ ] T039 [P] [US2] Add test for static file serving initialization in tests/unit/dashboard/test_handler.py
- [ ] T040 [P] [US2] Add test for static file serving error path in tests/unit/dashboard/test_handler.py

#### Error Response Formatting Tests (lines 939-953)
- [ ] T041 [P] [US2] Add test for error response construction in tests/unit/dashboard/test_handler.py
- [ ] T042 [P] [US2] Add test for error response with different status codes in tests/unit/dashboard/test_handler.py

#### Request Validation Tests (lines 1079-1093)
- [ ] T043 [P] [US2] Add test for request validation edge cases in tests/unit/dashboard/test_handler.py

#### Validation
- [ ] T044 [US2] Run `pytest --cov=src/lambdas/dashboard/handler --cov-report=term-missing` and verify ≥85%
- [ ] T045 [US2] Update docs/TEST-DEBT.md - mark TD-005 as RESOLVED

**Checkpoint**: User Story 2 complete - dashboard handler coverage ≥85% (SC-002)

---

## Phase 5: User Story 3 - Improve S3 Model Loading Coverage (Priority: P3)

**Goal**: Increase sentiment model S3 loading coverage from 74% to ≥85%

**Independent Test**: Run `pytest --cov=src/lambdas/analysis/sentiment --cov-fail-under=85`

### Implementation for User Story 3

#### S3 Download Path Tests (lines 81-139)
- [ ] T046 [P] [US3] Add moto-based test for S3 model download success path in tests/unit/test_sentiment.py
- [ ] T047 [P] [US3] Add test for S3 model download with caching in tests/unit/test_sentiment.py
- [ ] T048 [P] [US3] Add test for S3 model validation after download in tests/unit/test_sentiment.py
- [ ] T049 [P] [US3] Add test for S3 throttling error handling in tests/unit/test_sentiment.py
- [ ] T050 [P] [US3] Add test for S3 not found error handling in tests/unit/test_sentiment.py
- [ ] T051 [P] [US3] Add test for partial download cleanup in tests/unit/test_sentiment.py

#### Model Loading Tests
- [ ] T052 [P] [US3] Add test for model loading from downloaded files in tests/unit/test_sentiment.py
- [ ] T053 [P] [US3] Add test for model loading failure with error logging in tests/unit/test_sentiment.py

#### Validation
- [ ] T054 [US3] Run `pytest --cov=src/lambdas/analysis/sentiment --cov-report=term-missing` and verify ≥85%
- [ ] T055 [US3] Update docs/TEST-DEBT.md - mark TD-006 as RESOLVED

**Checkpoint**: User Story 3 complete - sentiment model coverage ≥85% (SC-003)

---

## Phase 6: User Story 4 - Complete Observability Tests (Priority: P4)

**Goal**: Verify TD-001 (PR #112) is complete - no pytest.skip() calls remain

**Independent Test**: Run `grep -n "pytest.skip" tests/integration/test_observability_preprod.py` - should return empty

### Implementation for User Story 4

- [ ] T056 [US4] Verify PR #112 changes are present in tests/integration/test_observability_preprod.py
- [ ] T057 [US4] Check for any remaining pytest.skip() calls in tests/integration/test_observability_preprod.py
- [ ] T058 [US4] If gaps found: Add assertion-based tests to replace any remaining skips
- [ ] T059 [US4] Run observability tests locally to verify assertions work
- [ ] T060 [US4] Update docs/TEST-DEBT.md - mark TD-001 as RESOLVED

**Checkpoint**: User Story 4 complete - zero pytest.skip() in observability tests (SC-007)

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Automated enforcement and documentation updates

### Pre-commit Hook (FR-013)
- [ ] T061 Create pre-commit hook script for ERROR log validation in scripts/check-error-log-assertions.sh
- [ ] T062 Add hook configuration to .pre-commit-config.yaml
- [ ] T063 Test hook locally: run pre-commit on existing tests
- [ ] T064 Verify hook passes on all existing tests (SC-008)

### Final Validation
- [ ] T065 Run full test suite: `pytest -v --tb=short`
- [ ] T066 Verify overall coverage remains ≥85%: `pytest --cov=src --cov-fail-under=85`
- [ ] T067 Run `make validate` to verify all checks pass
- [ ] T068 Update docs/TEST-DEBT.md with final status for all items

### Documentation
- [ ] T069 [P] Update docs/TEST_LOG_ASSERTIONS_TODO.md - mark STATUS as complete
- [ ] T070 [P] Add entry to CLAUDE.md for 086-test-debt-burndown technologies

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - must complete first (external PRs)
- **Foundational (Phase 2)**: Depends on Setup - verifies prerequisites
- **User Stories (Phases 3-6)**: All depend on Foundational completion
  - US1-US4 can proceed in parallel (different files)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies on other stories - can start after Foundational
- **User Story 2 (P2)**: No dependencies on other stories - can start after Foundational
- **User Story 3 (P3)**: No dependencies on other stories - can start after Foundational
- **User Story 4 (P4)**: No dependencies on other stories - can start after Foundational

### Parallel Opportunities

Within User Story 1:
- T009-T029 can ALL run in parallel (different error patterns, same pattern)

Within User Story 2:
- T032-T043 can ALL run in parallel (different test functions in same file)

Within User Story 3:
- T046-T053 can ALL run in parallel (different test functions in same file)

Across User Stories:
- US1, US2, US3, US4 can all run in parallel (different test files)

---

## Parallel Example: User Story 1 (All Caplog Assertions)

```bash
# All 21 error pattern tasks can run in parallel:
Task: "T009 Add caplog assertion for 'CUDA error' in tests/unit/test_analysis_handler.py"
Task: "T015 Add caplog assertion for 'Circuit breaker' in tests/unit/test_ingestion_handler.py"
Task: "T021 Add caplog assertion for 'put_item' in tests/unit/test_errors.py"
Task: "T027 Add caplog assertion for 'JSON parse' in tests/unit/test_secrets.py"
Task: "T029 Add caplog assertion for 'InvalidClientTokenId' in tests/unit/test_metrics.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify PRs merged)
2. Complete Phase 2: Foundational (verify helpers exist)
3. Complete Phase 3: User Story 1 (21 caplog assertions)
4. **STOP and VALIDATE**: Run `pytest -v` - verify zero unasserted ERROR logs
5. This alone delivers SC-001 and SC-004

### Incremental Delivery

1. Setup + Foundational → Prerequisites verified
2. User Story 1 → 21 caplog assertions → SC-001, SC-004 ✓
3. User Story 2 → Dashboard handler ≥85% → SC-002 ✓
4. User Story 3 → Sentiment model ≥85% → SC-003 ✓
5. User Story 4 → Observability tests verified → SC-007 ✓
6. Polish → Pre-commit hook → SC-008 ✓

### Parallel Team Strategy

With multiple developers:
1. Team verifies Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (T009-T031)
   - Developer B: User Story 2 (T032-T045)
   - Developer C: User Story 3 (T046-T055)
   - Developer D: User Story 4 (T056-T060)
3. All complete → Move to Polish phase together

---

## Notes

- [P] tasks = different test functions or files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Test pattern: Add `caplog` parameter, add `assert_error_logged(caplog, "pattern")`
- Commit after each user story phase completes
- Stop at any checkpoint to validate story independently
