# Implementation Plan: Feature 1149

## Overview

Apply `@require_role("operator")` decorator to `/users/lookup` endpoint.

## Phase Analysis

This feature is part of **Phase 1.5 (RBAC Infrastructure)**.

## Implementation Steps

### Step 1: Add require_role Import

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add import for `require_role` decorator
- **Risk**: Low (import only)

### Step 2: Apply Decorator to Endpoint

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add `@require_role("operator")` below `@users_router.get("/lookup")`
- **Risk**: Low (pattern already proven)

### Step 3: Add Request Parameter

- **File**: `src/lambdas/dashboard/router_v2.py`
- **Action**: Add `request: Request` parameter to handler function
- **Risk**: Low

### Step 4: Add Unit Tests

- **File**: `tests/unit/lambdas/dashboard/test_users_lookup_auth.py`
- **Tests**: Auth scenarios (401/403/200)
- **Risk**: Low

### Step 5: Run Unit Tests

- **Command**: `pytest tests/unit/lambdas/dashboard/ -v`
- **Risk**: Low

## Dependency Check

| Dependency | Status |
|------------|--------|
| `@require_role` decorator | COMPLETE |
| JWT `roles` claim | COMPLETE |

## Estimated Complexity

**Low** - Same pattern as Feature 1148.
