# Tasks: JWT Audience and Not-Before Claim Validation

**Feature**: 1147-jwt-aud-nbf-validation
**Generated**: 2026-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Overview

| Metric | Value |
|--------|-------|
| Total Tasks | 14 |
| User Story 1 (P1) | 4 tasks |
| User Story 2 (P1) | 4 tasks |
| User Story 3 (P2) | 2 tasks |
| Parallel Opportunities | 6 tasks |
| MVP Scope | US1 + US2 (both P1, security-critical) |

## Phase 1: Setup

*No new files or dependencies needed - modifying existing middleware.*

- [x] T001 Verify current JWTConfig structure in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T002 Verify current validate_jwt() signature and error handlers in `src/lambdas/shared/middleware/auth_middleware.py`

## Phase 2: Foundational (Blocking)

*Changes required by ALL user stories - must complete first.*

- [x] T003 Add `audience: str | None = None` field to JWTConfig dataclass in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T004 Update `JWTConfig.from_env()` to read JWT_AUDIENCE from environment in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T005 Add `"nbf"` to required claims list in jwt.decode() options in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T006 Add `audience=config.audience` parameter to jwt.decode() call in `src/lambdas/shared/middleware/auth_middleware.py`

## Phase 3: User Story 1 - Reject Cross-Service Tokens (P1)

**Goal**: Prevent cross-service token replay attacks via audience validation

**Independent Test**: Present JWT with wrong audience → verify 401 rejection

**Acceptance Criteria**:
- Tokens with `aud: "other-service"` are rejected
- Tokens with correct audience proceed to further validation
- Audience mismatch logged as WARNING (security event)

### Tasks

- [x] T007 [US1] Add InvalidAudienceError exception handler with WARNING log in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T008 [P] [US1] Add unit test `test_rejects_wrong_audience` in `tests/unit/middleware/test_jwt_validation.py`
- [x] T009 [P] [US1] Add unit test `test_accepts_correct_audience` in `tests/unit/middleware/test_jwt_validation.py`
- [x] T010 [P] [US1] Add unit test `test_rejects_missing_audience` in `tests/unit/middleware/test_jwt_validation.py`

## Phase 4: User Story 2 - Reject Pre-Dated Tokens (P1)

**Goal**: Prevent pre-generated token attacks via not-before validation

**Independent Test**: Present JWT with future nbf → verify 401 rejection

**Acceptance Criteria**:
- Tokens with `nbf` 5 minutes in future are rejected
- Tokens with `nbf` in the past are accepted
- Immature signature logged as DEBUG

### Tasks

- [x] T011 [US2] Add ImmatureSignatureError exception handler with DEBUG log in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T012 [P] [US2] Add unit test `test_rejects_future_nbf` in `tests/unit/middleware/test_jwt_validation.py`
- [x] T013 [P] [US2] Add unit test `test_accepts_past_nbf` in `tests/unit/middleware/test_jwt_validation.py`
- [x] T014 [P] [US2] Add unit test `test_rejects_missing_nbf` in `tests/unit/middleware/test_jwt_validation.py`

## Phase 5: User Story 3 - Clock Skew Tolerance (P2)

**Goal**: Allow 60-second tolerance for legitimate clock drift

**Independent Test**: Present JWT with edge-case timestamps → verify correct accept/reject

**Acceptance Criteria**:
- Existing leeway (60s) applies to nbf validation
- Tokens within tolerance are accepted
- Tokens beyond tolerance are rejected

### Tasks

- [x] T015 [US3] Add unit test `test_accepts_nbf_within_leeway` (nbf 30s in future, within 60s leeway) in `tests/unit/middleware/test_jwt_validation.py`
- [x] T016 [US3] Add unit test `test_rejects_nbf_beyond_leeway` (nbf 120s in future, beyond 60s leeway) in `tests/unit/middleware/test_jwt_validation.py`

## Phase 6: Polish & Integration

- [x] T017 Update `create_test_jwt()` to include `aud` and `nbf` parameters in `tests/e2e/conftest.py`
- [x] T018 Run full unit test suite and verify no regressions via `pytest tests/unit/middleware/test_jwt_validation.py -v`

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ─── T003, T004, T005, T006 must complete first
    ↓
Phase 3 (US1) ─┬─ T007 (handler) → T008, T009, T010 [parallel]
               │
Phase 4 (US2) ─┼─ T011 (handler) → T012, T013, T014 [parallel]
               │
Phase 5 (US3) ─┘─ T015, T016 [parallel after Phase 4]
    ↓
Phase 6 (Polish) ─── T017, T018 (sequential)
```

**Note**: US1 and US2 can be implemented in parallel after Phase 2 completes. They share no dependencies.

## Parallel Execution Examples

### After Phase 2 completes:

```bash
# Run in parallel (different test files/concerns)
T008: test_rejects_wrong_audience
T012: test_rejects_future_nbf
```

### Within Phase 3 (US1):

```bash
# After T007 completes, run in parallel:
T008, T009, T010  # All test the same handler, different scenarios
```

## Implementation Strategy

1. **MVP (Recommended First Merge)**: Phase 1-4 (US1 + US2)
   - Closes CVSS 7.8 vulnerability immediately
   - Both P1 priorities addressed
   - Can be validated independently

2. **Second Merge**: Phase 5 (US3)
   - Leeway validation edge cases
   - P2 priority, less critical

3. **Final Merge**: Phase 6 (Polish)
   - E2E test fixtures updated
   - Regression testing complete

## File Summary

| File | Changes |
|------|---------|
| `src/lambdas/shared/middleware/auth_middleware.py` | T001-T007, T011 |
| `tests/unit/middleware/test_jwt_validation.py` | T008-T010, T012-T016 |
| `tests/e2e/conftest.py` | T017 |
