# Tasks: Refresh Token Cookie-Only Request

**Feature**: 1168-refresh-cookie-only
**Branch**: `1168-refresh-cookie-only`
**Created**: 2026-01-07

## Summary

Remove refresh token from frontend request body - rely on httpOnly cookie only.

## Dependencies

```text
None - this is a standalone frontend change
Backend Feature 1160 already deployed and supports cookie extraction
```

## Phase 1: Setup

- [ ] T001 Identify all files that need modification by searching for `refreshToken` usage

## Phase 2: Implementation

### User Story 1 - Silent Token Refresh (P1)

**Goal**: Frontend refresh API sends empty body, authentication succeeds via cookie

**Independent Test**: Call refresh endpoint and verify request body is empty/undefined

- [ ] T002 [US1] Remove `refreshToken` parameter from function signature in `frontend/src/lib/api/auth.ts:87-88`
- [ ] T003 [US1] Remove request body from `api.post()` call in `frontend/src/lib/api/auth.ts:88`
- [ ] T004 [P] [US1] Remove `RefreshTokenRequest` interface if unused in `frontend/src/lib/api/auth.ts`

### User Story 2 - Secure Cookie Transmission (P1)

**Goal**: No refresh token appears in JavaScript-accessible locations

**Independent Test**: Verify via code search that no JS code stores or passes refresh token strings

- [ ] T005 [US2] Search codebase for any remaining `refreshToken` variable assignments or storage
- [ ] T006 [US2] Update any callers of `authApi.refreshToken()` to not pass arguments

## Phase 3: Testing

- [ ] T007 Update unit tests in `frontend/tests/unit/lib/api/auth.test.ts` to reflect new signature
- [ ] T008 Run `npm run typecheck` to verify no type errors
- [ ] T009 Run `npm run test` to verify all tests pass

## Phase 4: Verification

- [ ] T010 Verify FR-001: Request body is empty (manual network inspection or test assertion)
- [ ] T011 Verify FR-002: Function does not accept refreshToken parameter
- [ ] T012 Verify SC-004: No JavaScript code references refresh token string values

## Parallel Execution

Tasks T002, T003, T004 can be done in parallel (different code sections).
T005 and T006 depend on T002-T004 completion.

## Task Summary

| Phase | Task Count | Parallel Tasks |
|-------|-----------|----------------|
| Setup | 1 | 0 |
| Implementation | 5 | 1 |
| Testing | 3 | 0 |
| Verification | 3 | 0 |
| **Total** | **12** | **1** |

## MVP Scope

All tasks required - this is a minimal feature with no incremental delivery needed.

**Ready for**: `/speckit.implement`
