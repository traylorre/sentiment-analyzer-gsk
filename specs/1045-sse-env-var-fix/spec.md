# Feature Specification: Fix SSE Lambda Environment Variable Mismatch

**Feature Branch**: `1045-sse-env-var-fix`
**Created**: 2025-12-24
**Status**: Draft
**Input**: Pipeline failure - SSE Lambda fails with `ValueError: DYNAMODB_TABLE environment variable is required`

## Problem Statement

The SSE Lambda (`preprod-sentiment-sse-streaming`) is failing all streaming endpoint calls with:

```
ValueError: DYNAMODB_TABLE environment variable is required (no fallback - Amendment 1.15)
```

**Root Cause**: PR #495 renamed environment variables from `DATABASE_TABLE`/`DYNAMODB_TABLE` to `USERS_TABLE`/`SENTIMENTS_TABLE` across the dashboard Lambda and Terraform, but the SSE Lambda's `polling.py` was not updated.

**Current State**:
- Terraform sets: `SENTIMENTS_TABLE = "preprod-sentiment-items"`
- SSE Lambda reads: `os.environ.get("DYNAMODB_TABLE")` → returns `None` → raises `ValueError`

**Impact**:
- All SSE streaming endpoints return 500 errors
- 9 E2E tests failing in CI pipeline
- Main branch deployment blocked

## User Scenarios & Testing

### User Story 1 - SSE Streaming Works (Priority: P0)

As a dashboard user, I want SSE streaming to connect successfully so that I receive real-time sentiment updates.

**Acceptance Scenarios**:

1. **Given** the SSE Lambda is deployed, **When** I connect to `/api/v2/stream`, **Then** I receive heartbeat events within 30 seconds
2. **Given** the SSE Lambda is deployed, **When** I request stream status at `/api/v2/stream/status`, **Then** I receive a valid connection status response

### Edge Cases

- What happens if `SENTIMENTS_TABLE` is not set? The existing ValueError is raised (per Amendment 1.15 - no silent fallbacks)

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | SSE Lambda must read sentiment items table from `SENTIMENTS_TABLE` env var | P0 |
| FR-002 | Error message must reflect new env var name if missing | P0 |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | Change must not affect behavior when env var is correctly set | P0 |

## Technical Approach

### Files to Modify

1. `src/lambdas/sse_streaming/polling.py:42` - Change `DYNAMODB_TABLE` to `SENTIMENTS_TABLE`
2. `src/lambdas/sse_streaming/polling.py:44-47` - Update error message to reference `SENTIMENTS_TABLE`

### Changes Required

```python
# Before (line 42)
self._table_name = table_name or os.environ.get("DYNAMODB_TABLE")

# After
self._table_name = table_name or os.environ.get("SENTIMENTS_TABLE")
```

```python
# Before (lines 44-47)
raise ValueError(
    "DYNAMODB_TABLE environment variable is required "
    "(no fallback - Amendment 1.15)"
)

# After
raise ValueError(
    "SENTIMENTS_TABLE environment variable is required "
    "(no fallback - Amendment 1.15)"
)
```

## Verification

1. Run SSE Lambda unit tests
2. Verify Terraform config still provides `SENTIMENTS_TABLE`
3. E2E tests should pass after deployment

## Dependencies

- PR #495 (env var rename) - Already merged
- No other dependencies

## Risks

- **Low Risk**: This is a 2-line change with clear semantics
- **Mitigation**: Unit tests will verify behavior
