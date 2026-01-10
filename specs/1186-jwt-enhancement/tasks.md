# Tasks: JWT Enhancement (A14-A15-A17)

**Feature**: 1186-jwt-enhancement
**Created**: 2026-01-10

## Phase 1: Setup

- [x] T001 Create feature branch and spec directory

## Phase 2: User Model (A14 Prerequisite)

- [x] T002 Add `revocation_id: int = 0` field to User model in `src/lambdas/shared/models/user.py`
- [x] T003 Add `to_dynamodb_item()` serialization for revocation_id
- [x] T004 [P] Add unit test for revocation_id field in `tests/unit/lambdas/shared/models/test_user_revocation_id.py`

## Phase 3: JWTClaim Enhancement (A15)

- [x] T005 Add `jti: str | None = None` field to JWTClaim dataclass in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T006 Update validate_jwt() to extract jti from payload
- [x] T007 [P] Add unit test for jti extraction in `tests/unit/middleware/test_jwt_validation.py`

## Phase 4: Revocation ID Check (A14)

- [x] T008 Add `rev` claim extraction in validate_jwt()
- [x] T009 Add check_revocation_id() helper in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T010 [P] Add unit test for revocation ID check

## Phase 5: Verification (A17)

- [x] T011 Add unit test asserting leeway=60 default
- [x] T012 Add unit test for JWT_LEEWAY_SECONDS env override

## Phase 6: Polish

- [x] T013 Run ruff check/format on all modified files
- [x] T014 Run full unit test suite

## Dependencies

```
T001 -> T002-T004 (parallel)
T002 -> T008-T010 (revocation_id needed first)
T005 -> T006 -> T007
T008 -> T009 -> T010
```

## Completion Criteria

- [x] All unit tests pass (61 tests)
- [x] No lint errors
- [x] revocation_id field added to User
- [x] jti extracted in validate_jwt
- [x] check_revocation_id() available for validation

## Implementation Notes

T009 was adjusted: Original plan called for check in refresh_tokens(), but Cognito
handles refresh flow with opaque tokens. Instead, we added check_revocation_id()
helper function that can be called when validating self-issued JWTs that contain
the 'rev' claim. This is infrastructure for when we need it.
