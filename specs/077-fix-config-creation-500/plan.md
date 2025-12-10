# Implementation Plan: Fix Config Creation 500 Error

**Branch**: `077-fix-config-creation-500` | **Date**: 2025-12-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/077-fix-config-creation-500/spec.md`

## Summary

Fix the HTTP 500 error returned by the config creation endpoint (`POST /api/v2/configurations`) in preprod. The issue is environmental (unit tests pass), likely related to ticker cache S3 access, DynamoDB permissions, or unhandled exceptions. This fix will unblock ~8 E2E tests currently skipping due to this error.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: FastAPI, boto3, pydantic
**Storage**: DynamoDB (preprod-sentiment-dashboard table)
**Testing**: pytest 8.0+, moto for AWS mocks
**Target Platform**: AWS Lambda (preprod environment)
**Project Type**: Web API (Lambda + API Gateway)
**Performance Goals**: <500ms p90 latency for config creation
**Constraints**: Must maintain backward compatibility with existing API contract
**Security**: No user-generated content in logs (FR-006, CWE-117 log injection prevention)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Unit tests with mocks (moto) | PASS | All 16 config tests pass |
| E2E tests in preprod use real AWS | PASS | Will verify after fix |
| No pipeline bypass | PASS | Standard PR workflow |
| GPG-signed commits | PASS | Will sign commits |
| Proper error handling | FIX NEEDED | Current code re-raises exceptions as 500 |
| Structured logging | FIX NEEDED | Add detailed logging for debugging |
| No log injection (CWE-117) | PASS | FR-006: Never log user-generated content |
| Local SAST requirement | PASS | Will run make validate before push |

## Project Structure

### Documentation (this feature)

```text
specs/077-fix-config-creation-500/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 investigation findings
├── checklists/          # Quality checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (affected files)

```text
src/lambdas/dashboard/
├── router_v2.py              # Config endpoint handler (lines 681-700)
├── configurations.py         # Config service functions
└── ...

src/lambdas/shared/
├── cache/
│   └── ticker_cache.py       # S3-based ticker validation cache
└── models/
    └── configuration.py      # Configuration pydantic models

tests/
├── unit/dashboard/
│   └── test_configurations.py  # Unit tests (all pass)
├── contract/
│   └── test_configuration_api.py
└── e2e/
    └── test_config_crud.py     # E2E tests (currently skipping)
```

**Structure Decision**: Existing single-project structure. Bug fix touches 2-3 files in `src/lambdas/dashboard/`.

## Complexity Tracking

No constitution violations. This is a bug fix, not a new feature.

## Root Cause Analysis

### Confirmed Facts
1. Unit tests pass (16/16) - code logic is correct
2. E2E tests skip with "Config creation endpoint returning 500 - API issue"
3. CloudWatch shows errors in preprod Lambda but no config-specific errors captured

### Most Likely Root Cause: Unhandled Exception Propagation

The current exception handling pattern re-raises exceptions without proper HTTP error mapping:

```python
# Current (problematic) pattern in configurations.py:276-281
except Exception as e:
    logger.error("Failed to create configuration", extra=get_safe_error_info(e))
    raise  # This becomes HTTP 500
```

**Fix Strategy**: Catch specific exceptions and return appropriate HTTP status codes.

## Implementation Approach

### Phase 1: Add Diagnostic Logging (CodeQL-Safe)

Add detailed logging before each potential failure point to identify exact issue.
**CRITICAL**: Per FR-006, never log user-generated content (ticker symbols, config names, request payloads) to prevent CWE-117 log injection.

```python
# In create_configuration endpoint - SAFE logging (no user content)
logger.info("Config creation attempt", extra={
    "user_id_hash": hashlib.sha256(user_id.encode()).hexdigest()[:12],
    "ticker_cache_available": ticker_cache is not None,
    "ticker_count": len(body.tickers),  # Count is safe, ticker values are NOT
    "operation": "create_configuration",
    "request_id": request.state.request_id,
})
```

**Safe to log**: counts, booleans, system-generated IDs, hashes, operation names
**Never log**: ticker symbols, config names, user input strings, request body content

### Phase 2: Improve Exception Handling

Replace generic exception handler with specific error types:

| Exception Type | HTTP Status | User Message |
|---------------|-------------|--------------|
| `ClientError` (DynamoDB) | 500 | "Database error" |
| `ValueError` (validation) | 400 | Specific validation message |
| `PermissionError` | 403 | "Permission denied" |
| Default | 500 | "Internal server error" |

### Phase 3: Verify and Test

1. Deploy diagnostic logging
2. Trigger config creation via curl or E2E test
3. Check CloudWatch for detailed logs
4. Fix identified issue
5. Remove E2E test skip patterns
6. Run full E2E suite

## Files to Modify

| File | Change | Risk |
|------|--------|------|
| `src/lambdas/dashboard/configurations.py` | Add error handling, logging | Low |
| `src/lambdas/dashboard/router_v2.py` | Add try/except in endpoint | Low |
| `tests/e2e/test_config_crud.py` | Remove skip patterns | None |
| `tests/e2e/test_dashboard_buffered.py` | Remove skip patterns | None |

## Success Criteria Verification Plan

| Criterion | Verification Method |
|-----------|-------------------|
| SC-001: Returns HTTP 201 | `curl -X POST /api/v2/configurations` returns 201 |
| SC-002: E2E tests pass | `pytest tests/e2e -k config` shows 0 skipped |
| SC-003: No unit test regression | `make test-unit` passes |
| SC-004: Root cause documented | Commit message explains fix |
| SC-005: No CodeQL log injection | CodeQL analysis shows 0 new CWE-117 findings |

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Fix introduces new bug | Low | Medium | Comprehensive testing |
| Issue is in AWS infra | Medium | High | Document for ops team |
| Multiple root causes | Low | Medium | Iterative debugging |
| Log injection via diagnostics | Low | High | FR-006 compliance, no user content in logs |
