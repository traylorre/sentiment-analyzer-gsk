# Implementation Plan: Feature 1148

## Overview

Apply `@require_role("operator")` decorator to `/admin/sessions/revoke` endpoint.

## Phase Analysis

This feature is part of **Phase 1.5 (RBAC Infrastructure)** - adding authorization to admin endpoints.

## Implementation Steps

### Step 1: Add require_role Import

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add import for `require_role` decorator
- **Risk**: Low (import only)

### Step 2: Apply Decorator to Endpoint

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add `@require_role("operator")` below `@admin_router.post("/sessions/revoke")`
- **Note**: Decorator order matters - `@require_role` must be AFTER route decorator
- **Risk**: Low (pattern already proven in codebase)

### Step 3: Add Request Parameter

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add `request: Request` parameter to handler function
- **Note**: Required for `require_role` to extract auth context
- **Risk**: Low

### Step 4: Add Unit Tests

- **File**: `tests/unit/lambdas/dashboard/test_admin_sessions_revoke_auth.py`
- **Tests**:
  - `test_revoke_without_jwt_returns_401`
  - `test_revoke_without_operator_role_returns_403`
  - `test_revoke_with_operator_role_succeeds`
  - `test_revoke_error_message_does_not_enumerate_roles`
- **Risk**: Low

### Step 5: Run Existing Tests

- **Command**: `pytest tests/unit/lambdas/dashboard/ -v`
- **Verify**: No regression in existing revocation tests
- **Risk**: Low

## Dependency Check

| Dependency | Status | Verified |
|------------|--------|----------|
| `@require_role` decorator | COMPLETE | Feature 1130 |
| JWT `roles` claim | COMPLETE | Phase 1.5 |
| Role constants | COMPLETE | `shared/auth/constants.py` |

## Rollback Plan

Remove decorator and `request` parameter - single commit revert.

## Estimated Complexity

**Low** - Pattern is established, implementation is ~5 lines of code change + tests.
