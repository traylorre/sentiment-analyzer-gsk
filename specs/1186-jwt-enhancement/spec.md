# Feature 1186: JWT Enhancement (A14-A15-A17)

**Feature**: JWT token enhancements for security
**Status**: Implementation
**Phase**: Phase 1 Backend Non-Breaking

## Summary

Enhance JWT token handling with:
- A14: Revocation ID validation to prevent TOCTOU attacks during token refresh
- A15: jti claim infrastructure for individual token identity/revocation
- A17: Clock skew leeway (already implemented - verification only)

## Requirements

### FR-1: Revocation ID Field (A14 Prerequisite)
Add `revocation_id` integer field to User model:
- Default: 0
- Increments on password change or forced revocation
- Stored in DynamoDB with atomic increment

### FR-2: Revocation ID JWT Claim Support (A14)
During token refresh, validate revocation_id:
- Extract `rev` claim from refresh token (if present)
- Compare against user's current `revocation_id`
- Reject refresh if mismatch with AUTH_013

### FR-3: JTI Claim Support (A15)
Add jti (JWT ID) claim parsing:
- Extract `jti` claim if present
- Include in JWTClaim dataclass for tracing
- Log jti in auth events for audit trail
- Prepare for future token blocklist

### FR-4: Leeway Verification (A17)
Verify existing leeway implementation:
- jwt.decode uses leeway=60 seconds
- Configurable via JWT_LEEWAY_SECONDS env var

## Success Criteria

1. User model includes `revocation_id` field
2. Token refresh checks revocation_id claim against DB
3. JWTClaim dataclass includes optional `jti` field
4. jwt.decode leeway is 60 seconds (verify existing)

## Assumptions

- Production tokens come from Cognito (not self-generated)
- Test tokens can include jti/rev claims for validation testing
- No immediate token blocklist implementation (deferred)
