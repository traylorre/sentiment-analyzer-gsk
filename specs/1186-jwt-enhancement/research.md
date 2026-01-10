# Research: JWT Enhancement (A14-A15-A17)

**Feature**: 1186-jwt-enhancement
**Date**: 2026-01-10

## Summary

Research into existing JWT implementation to determine implementation path.

## Findings

### F1: A17 (Leeway) Already Implemented
- Location: `src/lambdas/shared/middleware/auth_middleware.py:96,156`
- Default: 60 seconds
- Configurable via `JWT_LEEWAY_SECONDS` env var
- Applied in jwt.decode() call

### F2: No revocation_id Field Exists
- User model has session-level revocation (`revoked`, `revoked_at`, `revoked_reason`)
- No `revocation_id` counter for atomic rotation detection
- Need to add field and increment on password change

### F3: No jti Claim Extraction
- JWTClaim dataclass has: subject, expiration, issued_at, issuer, roles
- Does NOT have: jti (token ID)
- jwt.decode doesn't require or extract jti

### F4: Production Uses Cognito Tokens
- Lambda JWT creation is blocked by security guard
- Production tokens come from Cognito
- Cognito tokens may not include custom claims (rev, jti)

## Decisions

### D1: Add revocation_id to User Model
- **Decision**: Add `revocation_id: int = 0` field
- **Rationale**: Required for A14 TOCTOU protection
- **Implementation**: Field in User model, atomic increment operation

### D2: Add jti to JWTClaim
- **Decision**: Add optional `jti: str | None` field
- **Rationale**: Enable future token blocklist, immediate audit trail value
- **Implementation**: Parse from payload if present, include in logs

### D3: Skip A17 Implementation
- **Decision**: Verify only, no code changes needed
- **Rationale**: Already implemented correctly
- **Implementation**: Add unit test asserting leeway=60

### D4: Graceful Degradation for Missing Claims
- **Decision**: rev/jti claims optional for backward compatibility
- **Rationale**: Cognito tokens won't have these initially
- **Implementation**: Check if present, skip validation if absent

## Files to Update

```
src/lambdas/shared/models/user.py       # Add revocation_id field
src/lambdas/shared/middleware/auth_middleware.py  # Add jti extraction
src/lambdas/dashboard/auth.py           # Add revocation_id check in refresh
tests/unit/middleware/test_jwt_validation.py  # Test jti extraction
tests/unit/test_user_model.py           # Test revocation_id field
```
