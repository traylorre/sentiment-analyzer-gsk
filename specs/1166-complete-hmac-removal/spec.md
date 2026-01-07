# Feature 1166: Complete HMAC Removal for Magic Link Tokens

## Problem Statement

Feature 1164 removed the hardcoded `MAGIC_LINK_SECRET` fallback but left the HMAC infrastructure in place. The preprod Lambda now fails with 500 errors because `_get_magic_link_secret()` raises `RuntimeError` when the environment variable is not set.

Per spec-v2.md (lines 1755-1771), the HMAC code should have been deleted entirely. The current verification already uses atomic DynamoDB consumption - HMAC signatures are generated but never verified.

## Root Cause

- `_get_magic_link_secret()` fails at runtime (no env var)
- `_generate_magic_link_signature()` is called but result is never used for verification
- `verify_and_consume_token()` uses DynamoDB conditional update, not HMAC

## Solution

Delete all HMAC-related code since verification is already token-based:

1. Delete `_get_magic_link_secret()` function
2. Delete `_generate_magic_link_signature()` function
3. Remove signature generation from `request_magic_link()`
4. Update `MagicLinkToken` model to make `signature` optional (backwards compat)
5. Remove signature from email callback parameters

## Security Analysis

**Current security model (unchanged):**
- 256-bit random token via `secrets.token_urlsafe(32)` - cryptographically unguessable
- Atomic DynamoDB consumption via `ConditionExpression="used = :false"` - no replay
- 1-hour expiry - limited window
- Rate limiting - 5/email/hour, 20/IP/hour

HMAC provides no additional security since:
- Token is already unguessable (256-bit random)
- HMAC was never verified during consumption
- Signature just added complexity without value

## Files Changed

1. `src/lambdas/dashboard/auth.py`
   - Delete lines 1104-1126: `_get_magic_link_secret()`, `_generate_magic_link_signature()`
   - Update line 1162: Remove signature generation
   - Update lines 1166-1175: Remove signature from token creation

2. `src/lambdas/shared/models/magic_link_token.py`
   - Make `signature` field `Optional[str] = None`

3. `tests/unit/lambdas/dashboard/test_auth_us2.py`
   - Remove any tests that check signature generation
   - Remove `MAGIC_LINK_SECRET` from test fixtures

## Acceptance Criteria

- [ ] `request_magic_link()` succeeds without `MAGIC_LINK_SECRET` env var
- [ ] Magic link tokens are verified via database lookup only
- [ ] No HMAC-related functions remain in auth.py
- [ ] Unit tests pass
- [ ] Preprod E2E tests pass (no more 500 errors)

## References

- spec-v2.md lines 1755-1771: "HMAC code has been DELETED"
- Feature 1164: Partial removal (hardcoded fallback only)
- Feature 1129: Atomic token consumption implementation
