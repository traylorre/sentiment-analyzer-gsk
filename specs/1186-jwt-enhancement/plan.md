# Implementation Plan: JWT Enhancement (A14-A15-A17)

**Feature**: 1186-jwt-enhancement
**Phase**: Phase 1 Backend Non-Breaking
**Date**: 2026-01-10

## Technical Context

- **Framework**: Python 3.13, PyJWT, pydantic
- **Database**: DynamoDB with single-table design
- **Auth**: Cognito for production, test tokens for unit tests

## Constitution Check

- [x] No destructive git commands
- [x] Uses speckit workflow
- [x] Principal engineer thinking
- [x] No quick fixes

## Implementation Phases

### Phase 1: User Model Enhancement (A14 Prerequisite)

1. Add `revocation_id` field to User model
2. Add `increment_revocation_id()` helper function
3. Call increment on password change/force revocation

### Phase 2: JWT Claim Enhancement (A15)

1. Add `jti: str | None` to JWTClaim dataclass
2. Extract jti from payload in validate_jwt()
3. Include jti in auth event logging

### Phase 3: Revocation ID Validation (A14)

1. Extract `rev` claim from tokens if present
2. In refresh flow, compare against user's revocation_id
3. Return AUTH_013 if mismatch

### Phase 4: Verification (A17)

1. Add unit test asserting leeway=60 default
2. Add unit test for leeway from env var

## File Changes

| File | Changes |
|------|---------|
| `src/lambdas/shared/models/user.py` | Add revocation_id field |
| `src/lambdas/shared/middleware/auth_middleware.py` | Add jti extraction |
| `src/lambdas/dashboard/auth.py` | Add rev check in refresh_tokens() |
| `tests/unit/` | New tests for all changes |

## Dependencies

- None (self-contained)

## Risks

- Cognito tokens may not include jti/rev claims
- Mitigation: Graceful skip if claims absent

## Test Plan

1. Unit test: User.revocation_id defaults to 0
2. Unit test: increment_revocation_id atomically increments
3. Unit test: JWTClaim parses jti when present
4. Unit test: validate_jwt extracts jti
5. Unit test: refresh_tokens rejects mismatched rev
6. Unit test: leeway defaults to 60
