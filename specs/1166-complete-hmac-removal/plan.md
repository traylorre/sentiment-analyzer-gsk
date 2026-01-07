# Feature 1166: Implementation Plan

## Overview

Complete the HMAC removal that was started in Feature 1164. Delete signature generation functions and update magic link flow to use random tokens only.

## Implementation Steps

### Step 1: Update MagicLinkToken Model

File: `src/lambdas/shared/models/magic_link_token.py`

Make `signature` field optional for backwards compatibility with any existing tokens in database:

```python
signature: str | None = None  # Deprecated, kept for backwards compat
```

### Step 2: Delete HMAC Functions from auth.py

File: `src/lambdas/dashboard/auth.py`

Delete these functions entirely:
- `_get_magic_link_secret()` (lines 1104-1116)
- `_generate_magic_link_signature()` (lines 1119-1126)

### Step 3: Update request_magic_link()

File: `src/lambdas/dashboard/auth.py`

In `request_magic_link()`:
- Remove: `signature = _generate_magic_link_signature(token_id, email)`
- Remove: `signature=signature` from MagicLinkToken instantiation
- Remove: signature from email callback if present

### Step 4: Update Tests

File: `tests/unit/lambdas/dashboard/test_auth_us2.py`

- Remove `MAGIC_LINK_SECRET` from test fixtures
- Remove tests that specifically test signature generation
- Keep tests for token creation, expiry, atomic consumption

## Risk Assessment

**Low Risk**:
- HMAC verification was already dead code
- Token security comes from randomness + atomic DB operations
- No breaking changes to API contracts

## Rollback Plan

If issues arise:
1. Revert commit
2. Add `MAGIC_LINK_SECRET` to Lambda env vars as temporary fix

## Testing Strategy

1. Unit tests: Verify token creation without HMAC
2. Integration tests: Verify full magic link flow
3. E2E tests: `test_auth_magic_link.py` should pass
