# Implementation Plan: Test Debt Burndown

**Branch**: `086-test-debt-burndown` | **Date**: 2025-12-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/086-test-debt-burndown/spec.md`

## Summary

Burn down test debt by:
1. Adding caplog assertions for all 21 documented error patterns (FR-001, FR-010)
2. Improving dashboard handler coverage from 72% to ≥85% (FR-003 through FR-007)
3. Improving sentiment model S3 loading coverage from 74% to ≥85% (FR-008, FR-009)
4. Verifying TD-001 observability tests are complete (FR-011, FR-012 - PR #112 already merged)

This is a test-only feature with no production code changes.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: pytest, pytest-cov, moto (AWS mocking), MagicMock
**Storage**: N/A (test-only changes)
**Testing**: pytest with pytest-cov for coverage measurement
**Target Platform**: Linux CI/local development
**Project Type**: Single project with serverless Lambda functions
**Performance Goals**: N/A (test execution speed not a concern)
**Constraints**: No production code changes; unit tests only (per scope)
**Scale/Scope**: ~30-40 tests to add/modify across 7-10 test files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Constitution Requirement | Compliance | Notes |
|-------------------------|------------|-------|
| §7 Implementation Accompaniment Rule | ✅ ALIGNED | This feature IS the test accompaniment |
| §7 Unit Tests vs Integration Tests | ✅ ALIGNED | All changes are unit tests with mocks |
| §7 Functional Integrity Principle | ✅ ALIGNED | Adding missing test coverage |
| §7 Testing & Validation | ✅ ALIGNED | Following existing test patterns |
| §8 Pre-Push Requirements | ✅ ALIGNED | Will run make validate before push |

**Gate Status**: PASS - All constitutional requirements met. This feature strengthens test coverage.

## Project Structure

### Documentation (this feature)

```text
specs/086-test-debt-burndown/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A - no data model changes
├── quickstart.md        # Phase 1 output (test development guide)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (test files to modify)

```text
tests/
├── conftest.py                              # Verify assert_error_logged exists
├── unit/
│   ├── test_analysis_handler.py             # Add 4+ caplog assertions
│   ├── test_ingestion_handler.py            # Add 6+ caplog assertions
│   ├── test_sentiment.py                    # Add 3+ caplog assertions
│   ├── test_newsapi_adapter.py              # Add circuit breaker, auth failure assertions
│   ├── test_errors.py                       # Add error helper assertions
│   ├── test_secrets.py                      # Add secret failure assertions
│   ├── test_metrics.py                      # Add metric emission failure assertions
│   └── dashboard/
│       └── test_handler.py                  # NEW/EXPANDED: SSE, WebSocket, static file tests
└── integration/
    └── test_observability_preprod.py        # Verify no pytest.skip() calls remain
```

**Structure Decision**: No structural changes. All modifications are to existing test files or new tests in existing test directories.

## Complexity Tracking

No complexity violations. This feature:
- Adds no new dependencies
- Adds no new patterns
- Follows existing test conventions
- Makes no production code changes

## Decision Records

### D1: Test Pattern for caplog Assertions

**Decision**: Use existing `assert_error_logged(caplog, pattern)` helper from `tests/conftest.py`

**Rationale**:
- Helper already exists and is documented
- Consistent with existing test patterns
- Provides clear, readable assertions

**Alternative Rejected**: Raw caplog.records scanning - more verbose and less maintainable

### D2: SSE/WebSocket Test Strategy

**Decision**: Use MagicMock to simulate SSE and WebSocket connections in unit tests

**Rationale**:
- Scope explicitly limits changes to unit tests
- Integration tests would require real AWS infrastructure
- MagicMock allows testing all code paths including error handling

**Alternative Rejected**: Integration tests with LocalStack - out of scope per clarification

### D3: S3 Model Loading Test Strategy

**Decision**: Use moto to mock S3 and test the download path

**Rationale**:
- moto already used throughout project for AWS mocking
- Can test download, caching, and error paths without real S3
- Follows constitution §7 (unit tests mock all external dependencies)

**Alternative Rejected**: Integration test with real preprod S3 - out of scope per clarification

### D4: TD-001 Verification Approach

**Decision**: Verify PR #112 changes are merged and functioning; no reimplementation

**Rationale**:
- PR #112 already merged (verified during clarification)
- Avoid duplicate work
- Only extend if gaps found during verification

**Alternative Rejected**: Reimplementing TD-001 changes independently - wasteful duplication
