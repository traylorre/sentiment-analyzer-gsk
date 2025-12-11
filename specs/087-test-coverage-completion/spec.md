# Feature Specification: Test Coverage Completion

**Feature Branch**: `087-test-coverage-completion`
**Created**: 2025-12-11
**Status**: Draft
**Input**: User description: "Complete the deferred coverage improvements from 086-test-debt-burndown. Dashboard handler (71%) and sentiment model (87%) coverage targets were deferred. Add remaining log assertions for 12 error patterns."

## Clarifications

### Session 2025-12-11

- Q: Test isolation strategy for SSE/WebSocket/S3 mocks? → A: Fresh mocks per test (each test creates its own moto/mock context)
- Q: How to handle line number drift if production code changes? → A: Use function/class names as anchors (line numbers are hints) + re-run coverage at task start to discover current uncovered lines
- Q: Test execution time budget? → A: 30 seconds per test maximum (10s warmup + 20s execution); longer indicates design problem
- Q: Log assertion pattern matching strategy? → A: Substring match (resilient to minor message changes, not exact string)
- Q: Test file organization for new tests? → A: Add to existing test files; SSE Lambda gets dedicated file (test_dashboard_handler_sse.py) as logical separation; maintainability trumps fast implementation

## Scope

### In Scope

- Dashboard handler test coverage improvement (71% → ≥85%)
- Sentiment model S3 loading test coverage improvement (87% → ≥85% - already met, verify maintained)
- Remaining 12 log assertion patterns from TEST_LOG_ASSERTIONS_TODO.md
- Unit tests only (mocked dependencies)

### Out of Scope

- Other modules below 80% coverage (e.g., `dashboard/chaos.py` at 75%)
- Integration or E2E tests
- Production code changes (test-only feature)
- Performance optimization

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard Handler Coverage (Priority: P1)

As a developer, I want the dashboard handler to have ≥85% test coverage so that I can refactor SSE streaming, WebSocket handling, and error response formatting with confidence that regressions will be caught.

**Why this priority**: Dashboard handler is at 71% coverage with critical user-facing paths untested. SSE streaming (lines 548-576), WebSocket handling (lines 743-758), and error formatting are used in production. Changes to these paths could break silently without test coverage.

**Independent Test**: Can be tested by running `pytest --cov=src.lambdas.dashboard.handler --cov-fail-under=85 tests/unit/` and verifying the coverage threshold passes.

**Acceptance Scenarios**:

1. **Given** the SSE streaming endpoint code (lines 548-576), **When** unit tests run with mocked connections, **Then** streaming initialization, event generation, and client disconnect paths are covered
2. **Given** the WebSocket handling code (lines 743-758), **When** unit tests run, **Then** connection, message, and disconnection paths are covered
3. **Given** the error response formatting code (lines 835-849, 937-938), **When** unit tests trigger error conditions, **Then** all error response paths are covered
4. **Given** the static file initialization code (lines 104-118), **When** unit tests run, **Then** initialization and fallback paths are covered

---

### User Story 2 - Log Assertion Completion (Priority: P2)

As a developer, I want all 21 documented error patterns to have explicit `assert_error_logged()` calls so that unexpected error logs are caught immediately rather than silently appearing in test output.

**Why this priority**: The pre-commit hook (086) provides awareness, but 12 patterns still lack explicit assertions. Completing these ensures zero false confidence from tests that pass while emitting ERROR logs.

**Independent Test**: Can be tested by running the pre-commit hook `./scripts/check-error-log-assertions.sh --verbose` and verifying all ERROR logs have corresponding assertions.

**Acceptance Scenarios**:

1. **Given** an Analysis Handler error path test, **When** the test triggers an ERROR log, **Then** the test includes `assert_error_logged(caplog, "pattern")` for that error
2. **Given** an Ingestion Handler error path test, **When** the test triggers an ERROR log, **Then** the test includes `assert_error_logged(caplog, "pattern")` for that error
3. **Given** a Shared module error path test, **When** the test triggers an ERROR log, **Then** the test includes `assert_error_logged(caplog, "pattern")` for that error

---

### User Story 3 - Sentiment Model Coverage Verification (Priority: P3)

As a developer, I want to verify the sentiment model maintains ≥85% coverage and add tests for the S3 model download path (lines 83-141) if gaps exist.

**Why this priority**: Sentiment model is at 87% coverage (already meets target). The S3 download path (lines 83-141) is the primary uncovered section. This is lower priority since target is met, but completing coverage prevents future drift.

**Independent Test**: Can be tested by running `pytest --cov=src.lambdas.analysis.sentiment --cov-fail-under=85 tests/unit/` and verifying coverage.

**Acceptance Scenarios**:

1. **Given** the S3 model download function (lines 83-141), **When** unit tests run with mocked S3 (moto), **Then** the download, caching, and error paths are covered
2. **Given** an S3 error during download, **When** the test runs, **Then** the error handling path is covered and error is logged with assertion

---

### Edge Cases

- **SSE client disconnect mid-stream**: Test verifies graceful cleanup, logs disconnect event, releases connection slot
- **WebSocket connection timeout**: Test verifies timeout handling, proper resource cleanup
- **S3 model download throttling**: Test verifies retry/backoff behavior with mocked throttling responses
- **Multiple concurrent SSE connections at limit**: Test verifies 503 response when connection limit reached
- **Malformed error responses**: Test verifies error formatter handles edge cases (None values, empty messages)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Dashboard handler unit tests MUST achieve ≥85% line coverage
- **FR-002**: All SSE streaming code (lines 548-576, 642-656) MUST have unit test coverage
- **FR-003**: All WebSocket handling code (lines 743-758) MUST have unit test coverage
- **FR-004**: All error response formatting code (lines 835-849, 937-938) MUST have unit test coverage
- **FR-005**: Static file initialization code (lines 104-118, 131, 155-163) MUST have unit test coverage
- **FR-006**: All 21 documented error patterns from TEST_LOG_ASSERTIONS_TODO.md MUST have `assert_error_logged()` calls
- **FR-007**: Sentiment model S3 download path (lines 83-141) MUST have unit test coverage with mocked S3
- **FR-008**: All new tests MUST use moto for AWS service mocking (S3, DynamoDB)
- **FR-009**: All new tests that trigger ERROR logs MUST include corresponding `assert_error_logged()` assertions
- **FR-010**: All new tests MUST use fresh mock/moto context per test (no shared state between tests)
- **FR-011**: Implementation MUST re-run coverage at task start to identify current uncovered lines; line numbers in this spec are hints, target functions/classes by name
- **FR-012**: Each new test MUST complete within 30 seconds (10s warmup + 20s execution); longer runtime indicates test design problem
- **FR-013**: Log assertions MUST use substring matching (not exact string) for resilience to minor message changes
- **FR-014**: New tests MUST be added to existing test files; exception: SSE Lambda tests go in dedicated `test_dashboard_handler_sse.py` for logical separation

### Key Entities

- **Coverage Gap**: Uncovered lines in source code identified by pytest-cov (currently 77 lines in handler.py, 23 lines in sentiment.py)
- **Error Pattern**: A specific error message logged during test execution (21 unique patterns documented)
- **Log Assertion**: An `assert_error_logged(caplog, pattern)` call that validates expected ERROR logs
- **Test File**: pytest test module containing tests for specific source module

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Dashboard handler (`src/lambdas/dashboard/handler.py`) achieves ≥85% line coverage (currently 71%)
- **SC-002**: Sentiment model (`src/lambdas/analysis/sentiment.py`) maintains ≥85% line coverage (currently 87%)
- **SC-003**: All 21 error patterns from `docs/TEST_LOG_ASSERTIONS_TODO.md` have explicit test assertions
- **SC-004**: Running `pytest -v --tb=short tests/unit/` completes successfully with all tests passing
- **SC-005**: Overall project test coverage remains ≥80%
- **SC-006**: Pre-commit hook `./scripts/check-error-log-assertions.sh` reports zero unasserted ERROR logs

## Assumptions

- The `assert_error_logged` and `assert_warning_logged` helpers exist in `tests/conftest.py` (confirmed in 086)
- Coverage is measured using pytest-cov with standard configuration
- Unit tests use moto for AWS service mocking rather than real AWS calls
- The 21 error patterns documented in TEST_LOG_ASSERTIONS_TODO.md are accurate and complete
- Test files themselves are excluded from coverage calculation (standard pytest-cov behavior)
- SSE and WebSocket can be tested via mocked connection objects without actual network I/O

## Dependencies

- pytest-cov for coverage measurement
- moto for AWS service mocking (S3, DynamoDB, Secrets Manager)
- Existing `tests/conftest.py` fixtures for shared test utilities
- `docs/TEST_LOG_ASSERTIONS_TODO.md` as source of truth for error patterns
- Pre-commit hook from 086-test-debt-burndown for validation
