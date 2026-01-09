# Implementation Plan: Feature 1175

## Overview

Create audit helper function for role assignment tracking.

## Implementation Steps

### Step 1: Create audit.py Module

**File:** `src/lambdas/shared/auth/audit.py` (new file)

Create module with `create_role_audit_entry()` function.

### Step 2: Add Unit Tests

**File:** `tests/unit/shared/auth/test_audit.py` (new file)

Test all source types and timestamp format.

### Step 3: (Optional) Refactor _advance_role()

Update to use the new helper for consistency.

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/lambdas/shared/auth/audit.py` | New | Audit helper function |
| `tests/unit/shared/auth/test_audit.py` | New | Unit tests |
| `src/lambdas/dashboard/auth.py` | Edit (optional) | Refactor to use helper |

## Validation

- [ ] All existing tests pass
- [ ] New tests pass
- [ ] Ruff lint passes
- [ ] Type checking passes

## Rollback

New module with no dependencies - simply delete files if needed.
