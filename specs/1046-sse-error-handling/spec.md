# Feature Specification: SSE Error Handling for Invalid Configurations

**Feature Branch**: `1046-sse-error-handling`
**Created**: 2024-12-24
**Status**: Draft
**Input**: Fix SSE endpoint to return 404/403 instead of 500 when invalid config ID is provided

## Problem Statement

The SSE streaming endpoint `GET /api/v2/configurations/{config_id}/stream` returns HTTP 500 when an invalid/non-existent configuration ID is provided. The expected behavior is HTTP 404 (Not Found).

**Root Cause**: In `configurations.py` line 443, the `get_configuration()` function re-raises DynamoDB exceptions instead of returning `None`. This means `sse.py` never reaches the `HTTPException(404)` code path at lines 386-400.

**Impact**: The E2E test `test_sse_invalid_config_rejected` fails, blocking the pipeline from going green.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Invalid Config Returns 404 (Priority: P1)

As an API consumer, when I request an SSE stream for a non-existent configuration ID, I should receive a clear 404 error instead of a generic 500 server error.

**Why this priority**: This is the core fix - proper error handling for the most common error case (config not found).

**Independent Test**: Run `pytest tests/e2e/test_sse.py::test_sse_invalid_config_rejected -v` - should pass

**Acceptance Scenarios**:

1. **Given** a non-existent config ID `invalid-config-xyz`, **When** GET `/api/v2/configurations/invalid-config-xyz/stream`, **Then** response is HTTP 404 with JSON error body
2. **Given** a malformed config ID `!@#$%`, **When** GET `/api/v2/configurations/!@#$%/stream`, **Then** response is HTTP 400 (Bad Request)

---

### User Story 2 - Permission Denied Returns 403 (Priority: P2)

As an API consumer, when I request an SSE stream for a configuration I don't own, I should receive a 403 Forbidden error.

**Why this priority**: Secondary case - config exists but user lacks permission.

**Independent Test**: Request stream for another user's config - should return 403

**Acceptance Scenarios**:

1. **Given** user A's config ID, **When** user B requests `/api/v2/configurations/{user_a_config}/stream`, **Then** response is HTTP 403 with "Access denied" message

---

### Edge Cases

- What happens when DynamoDB is temporarily unavailable? Return 503 (Service Unavailable)
- What happens when config ID is empty string? Return 400 (Bad Request)
- What happens when config ID contains invalid characters? Return 400 (Bad Request)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `get_configuration()` MUST return `None` when config ID does not exist in DynamoDB
- **FR-002**: `get_configuration()` MUST catch `ClientError` exceptions and handle them appropriately:
  - ResourceNotFoundException -> return `None`
  - AccessDeniedException -> raise HTTPException(403)
  - ValidationException -> raise HTTPException(400)
  - Other DynamoDB errors -> raise HTTPException(503)
- **FR-003**: SSE endpoint MUST return 404 when config is `None`
- **FR-004**: SSE endpoint MUST return 403 when access is denied
- **FR-005**: All error responses MUST include a JSON body with `error` and `detail` fields

### Files to Update

**Primary**:
- `src/lambdas/dashboard/configurations.py` - Update `get_configuration()` exception handling (around line 435-443)

**Secondary**:
- `src/lambdas/dashboard/sse.py` - Verify error handling at lines 386-400 catches all cases

### Key Entities

- **Configuration**: User-created dashboard configuration with tickers, alerts, and settings
- **DynamoDB ClientError**: AWS SDK exception for DynamoDB operation failures

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_sse_invalid_config_rejected` E2E test passes (invalid config returns 404, not 500)
- **SC-002**: All existing SSE tests continue to pass (no regression)
- **SC-003**: Deploy pipeline completes successfully through preprod integration tests
