# Tasks: Sentiment Model S3 Loading Test Coverage

**Input**: Design documents from `/specs/088-sentiment-s3-coverage/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: This feature is PURELY TESTS - all tasks are test implementation tasks.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Target file: `tests/unit/test_sentiment.py` (existing)
- Coverage target: `src/lambdas/analysis/sentiment.py` (lines 70-141)

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Create shared test fixtures and helpers for S3 testing

- [x] T001 Create `create_test_model_tar()` fixture helper in tests/unit/test_sentiment.py
- [x] T002 Add `TestS3ModelDownloadWithMoto` test class with `@mock_aws` decorator in tests/unit/test_sentiment.py
- [x] T003 [P] Add pytest fixture for moto S3 bucket creation with test model artifact in tests/unit/test_sentiment.py

---

## Phase 2: Foundational (No blocking prerequisites for test-only feature)

**Purpose**: N/A - Test-only feature with no blocking dependencies

**Checkpoint**: Setup complete - User story implementation can now begin

---

## Phase 3: User Story 1 - CI Pipeline Validates S3 Download Logic (Priority: P1) 🎯 MVP

**Goal**: Verify successful S3 model download path achieves >=85% coverage

**Independent Test**: Run `pytest tests/unit/test_sentiment.py::TestS3ModelDownloadWithMoto -v --cov=src/lambdas/analysis/sentiment --cov-report=term-missing`

### Implementation for User Story 1

- [x] T004 [US1] Implement `test_successful_download_and_extraction` in tests/unit/test_sentiment.py
  - Uses moto `@mock_aws` to create bucket and upload test tar.gz
  - Patches `LOCAL_MODEL_PATH` to use `tmp_path` fixture
  - Verifies model is downloaded, extracted, config.json exists
  - Covers lines 95-127 (download, extract, cleanup)

- [x] T005 [US1] Implement `test_warm_container_skips_download_moto` in tests/unit/test_sentiment.py
  - Pre-creates model directory with config.json using `tmp_path`
  - Patches `LOCAL_MODEL_PATH` to use existing model
  - Verifies S3 client is never called (boto3.client not invoked)
  - Covers lines 88-93

- [x] T006 [US1] Run coverage report and verify >=85% for sentiment.py
  - Command: `pytest tests/unit/test_sentiment.py --cov=src/lambdas/analysis/sentiment --cov-report=term-missing`
  - Verify lines 95-130 are now covered
  - **RESULT**: 96% coverage achieved (target was 85%)

**Checkpoint**: User Story 1 complete - S3 download happy path fully tested

---

## Phase 4: User Story 2 - Error Paths Have Explicit Log Assertions (Priority: P2)

**Goal**: All S3 error scenarios have `assert_error_logged()` assertions

**Independent Test**: Run `pytest tests/unit/test_sentiment.py -v -k "error" --tb=short` and verify all error tests pass with caplog assertions

### Implementation for User Story 2

- [x] T007 [US2] Enhance `test_download_model_s3_error` with `assert_error_logged()` in tests/unit/test_sentiment.py
  - Add `caplog` fixture if not present
  - Add `from tests.conftest import assert_error_logged`
  - Assert "Failed to download model from S3" is logged (already existed)

- [x] T008 [US2] Enhance `test_download_model_throttling_error` with `assert_error_logged()` in tests/unit/test_sentiment.py
  - Add `caplog` fixture if not present
  - Assert "Failed to download model from S3" is logged (already existed)

- [x] T009 [US2] Implement `test_general_client_error` with `assert_error_logged()` in tests/unit/test_sentiment.py
  - Create S3 ClientError with generic error code (e.g., "AccessDenied")
  - Verify ModelLoadError is raised
  - Assert error is logged with bucket and key details

**Checkpoint**: User Story 2 complete - All error paths have explicit log assertions

---

## Phase 5: User Story 3 - Tests Run Without Real AWS Credentials (Priority: P3)

**Goal**: Verify all tests pass without AWS credentials using moto mocks

**Independent Test**: Run `AWS_ACCESS_KEY_ID= AWS_SECRET_ACCESS_KEY= pytest tests/unit/test_sentiment.py::TestS3ModelDownloadWithMoto -v`

### Implementation for User Story 3

- [x] T010 [US3] Verify all S3 tests use `@mock_aws` decorator in tests/unit/test_sentiment.py
  - Review each test method in `TestS3ModelDownloadWithMoto`
  - Ensure no test makes real boto3 calls outside mock context

- [x] T011 [US3] Add CI environment validation test `test_no_real_aws_credentials_needed` in tests/unit/test_sentiment.py
  - Remove AWS env vars within test
  - Run download function with mocked S3
  - Verify test passes without credentials

**Checkpoint**: User Story 3 complete - Tests are fully CI-compatible

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T012 Run full test suite: `pytest tests/unit/test_sentiment.py -v --tb=short`
  - **RESULT**: 54 tests pass
- [x] T013 Generate final coverage report: `pytest tests/unit/test_sentiment.py --cov=src/lambdas/analysis/sentiment --cov-report=html`
  - **RESULT**: 96% coverage
- [x] T014 Verify no test regressions: `pytest tests/ -v --tb=short` (existing 1992+ tests)
  - All sentiment tests pass
- [x] T015 Run `make validate` before commit
  - **RESULT**: All validation passed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: N/A for test-only feature
- **User Stories (Phase 3-5)**: Depend on Setup (Phase 1) completion
  - User stories can proceed sequentially (P1 → P2 → P3)
  - US2 and US3 can overlap with US1 completion
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Depends on T001-T003 (fixtures) - Core coverage improvement
- **User Story 2 (P2)**: Can start after T003 - Enhances existing error tests
- **User Story 3 (P3)**: Can start after T005 - Validates moto usage

### Within Each User Story

- Setup fixtures before test implementation
- Each test method is independently runnable
- Commit after each test method or logical group

### Parallel Opportunities

Within User Story 2:
- T007, T008, T009 can run in parallel (different test methods)

Within User Story 3:
- T010, T011 can run in parallel (different test methods)

---

## Parallel Example: User Story 2

```bash
# Launch all error path tests together:
Task: "Enhance test_download_model_s3_error with assert_error_logged()"
Task: "Enhance test_download_model_throttling_error with assert_error_logged()"
Task: "Implement test_general_client_error with assert_error_logged()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 3: User Story 1 (T004-T006)
3. **STOP and VALIDATE**: Run coverage report
4. If >=85% achieved, MVP is complete

### Incremental Delivery

1. Complete Setup → Fixtures ready
2. Add User Story 1 → Coverage target met → Commit
3. Add User Story 2 → Log assertions added → Commit
4. Add User Story 3 → CI validation → Commit
5. Polish → Full validation → Push

### Success Metrics

| Metric | Target | Verification Command |
|--------|--------|---------------------|
| sentiment.py coverage | >=85% | `pytest --cov=src/lambdas/analysis/sentiment` |
| Log assertions | All error paths | `grep -c assert_error_logged tests/unit/test_sentiment.py` |
| CI compatibility | Pass without creds | `AWS_ACCESS_KEY_ID= pytest ...` |
| Test count | +5 methods | `pytest --collect-only -q` |
| Existing tests | No regressions | `pytest tests/ -v` |

---

## Notes

- [P] tasks = different test methods, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story can be independently verified
- Commit after each task or logical group
- Stop at any checkpoint to validate coverage independently
