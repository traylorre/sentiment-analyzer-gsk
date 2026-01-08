# Implementation Plan: Feature 1171

## Overview

Add `_mark_email_verified()` helper function to propagate OAuth provider's email verification status to the user-level `verification` field.

## Implementation Steps

### Step 1: Add Helper Function

**File:** `src/lambdas/dashboard/auth.py`
**Location:** After `_advance_role()` function (~line 1829)

```python
def _mark_email_verified(
    table: Any,
    user: User,
    provider: str,
    email: str,
    email_verified: bool,
) -> None:
    """Mark email as verified from OAuth provider (Feature 1171).

    Updates user.verification field based on JWT email_verified claim.
    Must be called BEFORE _advance_role() to maintain state machine invariant.

    Args:
        table: DynamoDB table resource
        user: User object to update
        provider: OAuth provider name (google, github)
        email: Email from OAuth JWT
        email_verified: email_verified claim from OAuth JWT
    """
```

### Step 2: Implement Logic

1. Early return if `email_verified=False`
2. Early return if `user.verification == "verified"`
3. DynamoDB update with verification fields
4. Try/except with warning log on failure

### Step 3: Integrate in OAuth Callback

**Existing User Path (~line 1604):**
- After `_link_provider()` call
- Before `_advance_role()` call

**New User Path (~line 1629):**
- After `_link_provider()` call
- Before `_advance_role()` call

### Step 4: Add Unit Tests

**File:** `tests/unit/dashboard/test_mark_email_verified.py`

Tests following `test_role_advancement.py` pattern:
1. Happy path - provider verified
2. Skip path - provider not verified
3. Skip path - already verified
4. Audit fields populated
5. Primary email set
6. Silent failure on error
7. Integration with full OAuth flow

## File Changes

| File | Change Type | Description |
|------|-------------|-------------|
| `src/lambdas/dashboard/auth.py` | Edit | Add `_mark_email_verified()`, integrate in callback |
| `tests/unit/dashboard/test_mark_email_verified.py` | New | Unit tests |

## Validation

- [ ] All existing tests pass
- [ ] New tests pass with 100% coverage
- [ ] Ruff lint passes
- [ ] Type checking passes
- [ ] Pre-commit hooks pass

## Rollback

No rollback needed - new function with silent failure pattern. If issues arise, the OAuth flow continues working as before (email verification just isn't marked).
