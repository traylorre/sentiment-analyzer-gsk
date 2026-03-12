# Tasks: Require Role Decorator

**Feature**: 1130-require-role-decorator
**Branch**: `1130-require-role-decorator`
**Generated**: 2026-01-05
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 14 |
| User Story 1 (P1) Tasks | 5 |
| User Story 2 (P2) Tasks | 2 |
| User Story 3 (P3) Tasks | 2 |
| Parallel Opportunities | 4 |
| MVP Scope | Phase 1-3 (Setup + Foundational + US1) |

## Dependencies

```
Phase 1 (Setup)
    ↓
Phase 2 (Foundational) ──┬── T003 Role constants
    │                    └── T004 Auth errors
    ↓
Phase 3 (US1: Protect Admin) ──┬── T005 Extend AuthContext
    │                          ├── T006 require_role decorator
    │                          └── T007-T009 Tests
    ↓
Phase 4 (US2: Multiple Roles) ── T010-T011 (builds on US1)
    ↓
Phase 5 (US3: Composable Auth) ── T012-T013 (builds on US1)
    ↓
Phase 6 (Polish) ── T014 Final validation
```

---

## Phase 1: Setup

**Goal**: Ensure project structure and directories exist for new modules.

- [x] T001 Create auth constants directory at `src/lambdas/shared/auth/` if not exists
- [x] T002 [P] Create auth errors module at `src/lambdas/shared/errors/auth_errors.py` with empty file

---

## Phase 2: Foundational

**Goal**: Implement shared components required by all user stories (blocking prerequisites).

- [x] T003 [P] Implement Role enum with canonical values (ANONYMOUS, FREE, PAID, OPERATOR) and VALID_ROLES frozenset in `src/lambdas/shared/auth/constants.py`
- [x] T004 [P] Implement role exception classes (InvalidRoleError, MissingRolesClaimError, InsufficientRoleError) in `src/lambdas/shared/errors/auth_errors.py`

---

## Phase 3: User Story 1 - Protect Admin Endpoints (P1)

**Goal**: Operators can access admin endpoints; non-operators receive generic 403.

**Independent Test**: Decorate test endpoint with `@require_role('operator')`, verify operators pass and non-operators get 403 without role leakage.

**Acceptance Criteria**:
- Operator role grants access to decorated endpoints
- Non-operator authenticated users receive 403 "Access denied"
- Unauthenticated users receive 401 "Authentication required"
- Error messages do NOT reveal required role

### Implementation

- [x] T005 [US1] Extend AuthContext dataclass with `roles: list[str] | None = None` field in `src/lambdas/shared/middleware/auth_middleware.py`
- [x] T006 [US1] Implement `require_role(role: str)` decorator factory with startup validation, auth context extraction, and generic error messages in `src/lambdas/shared/middleware/require_role.py`
- [x] T007 [US1] Export `require_role` from middleware `__init__.py` at `src/lambdas/shared/middleware/__init__.py`

### Tests

- [x] T008 [P] [US1] Create unit tests for require_role decorator covering operator access, non-operator 403, unauthenticated 401, and generic error messages in `tests/unit/lambdas/shared/middleware/test_require_role.py`
- [x] T009 [P] [US1] Create unit tests for Role enum and VALID_ROLES validation in `tests/unit/lambdas/shared/auth/test_constants.py`

---

## Phase 4: User Story 2 - Support Multiple Role Levels (P2)

**Goal**: Decorator supports all canonical roles (anonymous, free, paid, operator).

**Independent Test**: Create endpoints with different role requirements and verify correct access control per role.

**Acceptance Criteria**:
- `@require_role('paid')` grants access to paid users
- `@require_role('free')` grants access to free users
- Role accumulation works (operator has all lower roles)

### Implementation

- [x] T010 [US2] Add test cases for paid role requirement in `tests/unit/lambdas/shared/middleware/test_require_role.py`
- [x] T011 [US2] Add test cases for free role requirement and role accumulation (operator accessing paid endpoints) in `tests/unit/lambdas/shared/middleware/test_require_role.py`

---

## Phase 5: User Story 3 - Composable with Existing Auth (P3)

**Goal**: Decorator works alongside FastAPI Depends() without conflicts.

**Independent Test**: Apply decorator to endpoint with `Depends(get_users_table)` and verify both work.

**Acceptance Criteria**:
- Decorator does not break existing dependency injection
- Multiple decorators can be combined
- Works with async handlers

### Implementation

- [x] T012 [US3] Add integration test for decorator combined with Depends() in `tests/unit/lambdas/shared/middleware/test_require_role.py`
- [x] T013 [US3] Add test for decorator on async handler with multiple dependencies in `tests/unit/lambdas/shared/middleware/test_require_role.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Goal**: Final validation and code quality checks.

- [x] T014 Run linting (ruff check) and formatting (ruff format) on all new files, verify tests pass with `pytest tests/unit/lambdas/shared/middleware/test_require_role.py tests/unit/lambdas/shared/auth/test_constants.py -v`

---

## Parallel Execution Examples

### Setup Phase (T001-T002)
```bash
# Can run in parallel - independent directories/files
T001 & T002
```

### Foundational Phase (T003-T004)
```bash
# Can run in parallel - different files
T003 & T004
```

### US1 Tests (T008-T009)
```bash
# Can run in parallel - different test files
T008 & T009
```

---

## Implementation Strategy

### MVP First (Phases 1-3)
Complete Setup, Foundational, and User Story 1 to deliver:
- Working `@require_role('operator')` decorator
- Protection for admin endpoints
- Generic error messages preventing enumeration

### Incremental Delivery
- **After Phase 3**: Deploy and protect `/admin/sessions/revoke` and `/users/lookup` endpoints
- **After Phase 4**: Enable `@require_role('paid')` for premium features
- **After Phase 5**: Full integration confidence with existing auth patterns

---

## File Manifest

| File | Action | Phase |
|------|--------|-------|
| `src/lambdas/shared/auth/__init__.py` | Create | 1 |
| `src/lambdas/shared/auth/constants.py` | Create | 2 |
| `src/lambdas/shared/errors/auth_errors.py` | Create | 2 |
| `src/lambdas/shared/middleware/auth_middleware.py` | Modify | 3 |
| `src/lambdas/shared/middleware/require_role.py` | Create | 3 |
| `src/lambdas/shared/middleware/__init__.py` | Modify | 3 |
| `tests/unit/lambdas/shared/auth/test_constants.py` | Create | 3 |
| `tests/unit/lambdas/shared/middleware/test_require_role.py` | Create | 3-5 |
