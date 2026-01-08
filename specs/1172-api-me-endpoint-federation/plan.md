# Implementation Plan: Feature 1172

## Overview

Add federation fields to `/api/v2/auth/me` response. Backend-only, non-breaking change.

## Implementation Steps

### Step 1: Update UserMeResponse Model

**File:** `src/lambdas/shared/response_models.py`
**Location:** Lines 50-58 (UserMeResponse class)

Add four new fields:
- `role: str = "anonymous"`
- `linked_providers: list[str] = Field(default_factory=list)`
- `verification: str = "none"`
- `last_provider_used: str | None = None`

### Step 2: Update Endpoint Handler

**File:** `src/lambdas/dashboard/router_v2.py`
**Location:** Lines 1918-1923 (response construction)

Pass new fields from user object to response:
- `role=user.role`
- `linked_providers=user.linked_providers`
- `verification=user.verification`
- `last_provider_used=user.last_provider_used`

### Step 3: Add Unit Tests

**File:** `tests/unit/dashboard/test_me_endpoint_federation.py`

Create new test file following router_v2 test patterns.

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/lambdas/shared/response_models.py` | Edit | Add 4 fields to UserMeResponse |
| `src/lambdas/dashboard/router_v2.py` | Edit | Pass federation fields to response |
| `tests/unit/dashboard/test_me_endpoint_federation.py` | New | Unit tests |

## Validation

- [ ] All existing tests pass
- [ ] New tests pass
- [ ] Ruff lint passes
- [ ] Type checking passes
- [ ] Pre-commit hooks pass

## Rollback

Non-breaking change. New fields have defaults, so existing frontend code continues working until Feature 1173/1174 are deployed.
