# Research: Test Debt Burndown

**Feature**: 086-test-debt-burndown
**Date**: 2025-12-11

## Research Tasks Completed

### R1: Verify assert_error_logged Helper Exists

**Finding**: Helper exists in `tests/conftest.py`

**Location**: `tests/conftest.py` (documented in `docs/TEST_LOG_ASSERTIONS_TODO.md`)

**Signature**:
```python
def assert_error_logged(caplog, pattern: str):
    """Assert an ERROR log was captured matching pattern."""

def assert_warning_logged(caplog, pattern: str):
    """Assert a WARNING log was captured matching pattern."""
```

**Decision**: Use existing helpers - no new implementation needed

### R2: Inventory of 21 Error Patterns

**Source**: `docs/TEST_LOG_ASSERTIONS_TODO.md`

**Categorization by Test File**:

| Category | Count | Test File | Patterns |
|----------|-------|-----------|----------|
| Analysis Handler | 6 | `test_analysis_handler.py` | CUDA error, SNS format, Model load (3 variants), Inference failed |
| Ingestion Handler | 6 | `test_ingestion_handler.py` | Circuit breaker, NewsAPI auth (3 variants), Config error, Secret error |
| Shared Errors | 6 | `test_errors.py` | DB put/query, Config retrieval, Internal error, Model loading, Sentiment failed |
| Secrets | 2 | `test_secrets.py` | JSON parse, Secret not found |
| Metrics | 1 | `test_metrics.py` | Invalid client token |

**Decision**: Organize work by test file for systematic coverage

### R3: TD-001 Verification (PR #112)

**Finding**: PR #112 is MERGED (state: MERGED, all checks passed)

**PR Title**: "feat: Add CloudWatch observability tests and Lambda warmup (TD-001)"

**What was implemented**:
1. Lambda warm-up step added to `.github/workflows/deploy.yml`
2. Tests use assertions instead of skips for missing metrics
3. Test file: `tests/integration/test_observability_preprod.py`

**Remaining Work**: Verify no `pytest.skip()` calls remain in observability tests

**Decision**: Verification task only - no new implementation needed

### R4: Dashboard Handler Uncovered Lines

**Source**: `docs/TEST-DEBT.md` (TD-005)

**Current Coverage**: 72%
**Target Coverage**: ≥85%

**Uncovered Code Sections**:

| Lines | Function | Description |
|-------|----------|-------------|
| 115-129 | Static file serving | Initialization and error paths |
| 557-628 | SSE streaming | Event generation, client disconnect |
| 746-760 | WebSocket handling | Connection, message, disconnect |
| 939-953 | Error response formatting | Response construction |
| 1079-1093 | Request validation | Edge cases |

**Coverage Gap**: ~14 percentage points = ~150-200 lines to cover

**Decision**: Focus on SSE and WebSocket paths first (largest gaps), then error formatting

### R5: Sentiment Model S3 Loading Uncovered Lines

**Source**: `docs/TEST-DEBT.md` (TD-006)

**Current Coverage**: 74%
**Target Coverage**: ≥85%

**Uncovered Code Sections**:

| Lines | Function | Description |
|-------|----------|-------------|
| 81-139 | S3 model download | Download, caching, validation paths |

**Root Cause**: Unit tests mock the model directly, never exercising S3 download

**Decision**: Add moto-based tests for S3 download path including error handling

### R6: Existing Test Patterns

**Pattern Analysis from `tests/conftest.py`**:

1. **caplog fixture**: Standard pytest fixture for log capture
2. **assert_error_logged**: Custom helper for ERROR log assertions
3. **@moto.mock_aws**: Decorator pattern for AWS mocking
4. **MagicMock**: Used for complex object mocking

**Best Practice Pattern**:
```python
def test_error_path(self, caplog):
    with patch('module.function', side_effect=ErrorType("message")):
        result = handler(event, context)

    assert result["statusCode"] == 500
    assert_error_logged(caplog, "expected pattern")
```

**Decision**: Follow established patterns exactly for consistency

## Summary

| Research Task | Status | Key Finding |
|---------------|--------|-------------|
| R1: Helper verification | ✅ Complete | Helpers exist in conftest.py |
| R2: Error pattern inventory | ✅ Complete | 21 patterns across 5 categories |
| R3: TD-001 verification | ✅ Complete | PR #112 merged, verify no skips |
| R4: Dashboard gaps | ✅ Complete | SSE/WebSocket/static file paths |
| R5: S3 loading gaps | ✅ Complete | Lines 81-139 need moto tests |
| R6: Test patterns | ✅ Complete | Follow existing caplog pattern |

All NEEDS CLARIFICATION items resolved. Ready for Phase 1.
