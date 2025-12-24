# Feature Specification: Add sse-starlette Dependency to Dashboard Lambda

**Feature Branch**: `1040-add-sse-starlette-dep`
**Created**: 2025-12-24
**Status**: Implementation
**Input**: Pipeline failure - ModuleNotFoundError: No module named 'sse_starlette'

## Problem Statement

The Dashboard Lambda container image fails the smoke test with:
```
ModuleNotFoundError: No module named 'sse_starlette'
```

This blocks the entire Deploy Pipeline, preventing deployment of the OHLC resolution selector feature.

## Root Cause Analysis

1. `src/lambdas/dashboard/sse.py:45` imports `sse_starlette.sse.EventSourceResponse`
2. `src/lambdas/dashboard/router_v2.py:40` imports the sse module
3. `handler.py:183` imports router_v2
4. The Dashboard Lambda `requirements.txt` does NOT include `sse-starlette`
5. The SSE Lambda `requirements.txt` correctly includes `sse-starlette>=2.0.0,<3.0.0`

The dependency was added when SSE endpoint support was added to Dashboard Lambda (Feature 015) but the requirements.txt was not updated.

## User Scenarios & Testing

### User Story 1 - Deploy Pipeline Passes (Priority: P1)

As a developer, when I push code to main branch, the Deploy Pipeline should complete successfully so that changes are deployed to preprod.

**Acceptance Scenarios**:

1. **Given** the Dashboard Lambda container builds, **When** the smoke test runs, **Then** all imports succeed without ModuleNotFoundError

---

## Requirements

### Functional Requirements

- **FR-001**: Dashboard Lambda requirements.txt MUST include `sse-starlette>=2.0.0,<3.0.0`
- **FR-002**: Version constraint MUST match SSE Lambda for consistency

### Files to Modify

- `src/lambdas/dashboard/requirements.txt` - Add sse-starlette dependency

## Success Criteria

### Measurable Outcomes

- **SC-001**: Deploy Pipeline "Build Dashboard Lambda Image (Preprod)" job passes
- **SC-002**: Smoke test imports succeed
- **SC-003**: Deploy to Preprod proceeds
