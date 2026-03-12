# Implementation Plan: Test Coverage Completion

**Branch**: `087-test-coverage-completion` | **Date**: 2025-12-11 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/087-test-coverage-completion/spec.md`

## Summary

Complete deferred test coverage improvements from 086-test-debt-burndown. Dashboard handler coverage must increase from 71% to ≥85% by adding tests for SSE streaming, WebSocket handling, error response formatting, and static file initialization. All 21 error patterns must have explicit `assert_error_logged()` assertions. Sentiment model coverage (87%) already meets target but S3 download path should be verified.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: pytest 8.0+, pytest-cov, moto (AWS mocking), unittest.mock
**Storage**: N/A (test-only feature, no new storage)
**Testing**: pytest with moto for AWS service mocking (S3, DynamoDB, Secrets Manager)
**Target Platform**: Linux server (CI/CD), local development
**Project Type**: Single project (existing Lambda-based serverless architecture)
**Performance Goals**: Each test ≤30 seconds (10s warmup + 20s execution)
**Constraints**: Fresh mocks per test (no shared state), substring matching for log assertions
**Scale/Scope**: ~50-80 new test cases across 2-3 test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Unit tests mock ALL external dependencies | ✅ PASS | FR-008 mandates moto for AWS mocking |
| Implementation accompanied by unit tests | ✅ PASS | This feature IS unit tests |
| 80% coverage threshold for new code | ✅ PASS | Target is 85% for affected modules |
| Fresh mocks per test | ✅ PASS | FR-010 mandates fresh mock/moto context per test |
| No flaky dates (date.today(), datetime.now()) | ✅ PASS | Test-only feature, no date dependencies expected |
| Deterministic test data | ✅ PASS | Tests use controlled mock responses |
| Pre-push requirements (lint, format, GPG sign) | ✅ PASS | Standard workflow applies |
| Error logs have assertions | ✅ PASS | FR-009/FR-013 mandate assert_error_logged() |

**Constitution Verdict**: All gates pass. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/087-test-coverage-completion/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (minimal for test-only feature)
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (test files to modify/create)

```text
tests/unit/
├── dashboard/
│   ├── test_sse.py              # Existing - add coverage tests
│   └── test_dashboard_handler_sse.py  # NEW - dedicated SSE Lambda tests (FR-014)
├── test_dashboard_handler.py    # Existing - add WebSocket, error formatting tests
├── test_analysis_handler.py     # Existing - add log assertions
├── test_ingestion_handler.py    # Existing - add log assertions
├── test_sentiment.py            # Existing - add S3 download tests, log assertions
├── test_errors.py               # Existing - add log assertions
├── test_secrets.py              # Existing - add log assertions
├── test_metrics.py              # Existing - add log assertions
└── test_newsapi_adapter.py      # Existing - add log assertions
```

**Structure Decision**: Add tests to existing files per FR-014, with exception of dedicated `test_dashboard_handler_sse.py` for SSE Lambda streaming tests (logical separation for different Lambda invocation mode).

## Complexity Tracking

No constitution violations requiring justification. This is a test-only feature that follows standard patterns.

## Phase 0: Research Summary

### Research Tasks Identified

1. **SSE Streaming Mocking**: How to mock SSE connections in unit tests
2. **WebSocket Mocking**: How to mock WebSocket connections in unit tests
3. **S3 Model Download Mocking**: Best practices for moto S3 mocking with model files
4. **Uncovered Line Mapping**: Map current uncovered lines to function/class names

### Research Findings

See [research.md](./research.md) for detailed findings. Summary:

1. **SSE Streaming**: Use `AsyncMock` to mock streaming generators; test with `httpx` AsyncClient
2. **WebSocket Mocking**: Not needed - uncovered lines are error handlers in trend endpoint, not WebSocket
3. **S3 Model Download**: Use `@mock_aws` with moto; create mock tar.gz with config.json
4. **Line Mapping**: 77 uncovered lines in handler.py mapped to 12 functions; 23 in sentiment.py mapped to S3 download path

## Phase 1: Design Artifacts

**Generated**:
- [data-model.md](./data-model.md) - Test data structures and mock patterns
- [quickstart.md](./quickstart.md) - Developer guide for adding coverage tests

**No contracts/ directory** - Test-only feature with no API changes

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| Unit tests mock ALL external dependencies | ✅ PASS | moto for S3, DynamoDB; AsyncMock for SSE |
| Implementation accompanied by unit tests | ✅ PASS | This feature IS unit tests |
| 80% coverage threshold for new code | ✅ PASS | Target is 85% for affected modules |
| Fresh mocks per test | ✅ PASS | Documented in quickstart.md |
| No flaky dates | ✅ PASS | No date dependencies in test patterns |
| Deterministic test data | ✅ PASS | Mock patterns use fixed data |
| Pre-push requirements | ✅ PASS | Standard workflow |
| Error logs have assertions | ✅ PASS | All 21 patterns documented |

**Post-Design Verdict**: All gates pass. Ready for `/speckit.tasks`
