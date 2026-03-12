# Tasks: Fix Anonymous Auth 422 Error

**Input**: Design documents from `/specs/1119-fix-anonymous-auth-422/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), quickstart.md (complete)

**Tests**: Unit tests REQUIRED per Constitution Check in plan.md

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Project**: `src/lambdas/dashboard/` for Lambda code, `tests/unit/` for tests

---

## Phase 1: Setup (No Changes Required)

**Purpose**: Project already initialized. No setup tasks needed.

**Checkpoint**: Project structure already exists - proceed to implementation.

---

## Phase 2: Foundational (No Changes Required)

**Purpose**: No foundational/blocking prerequisites for this fix.

**Checkpoint**: Foundation ready - proceed to User Story 1.

---

## Phase 3: User Story 1 - Anonymous Session Creation (Priority: P1) MVP

**Goal**: Fix POST /api/v2/auth/anonymous to accept requests with no body or empty body, returning 201 with defaults instead of 422.

**Independent Test**: Open dashboard in incognito browser - should load without authentication errors.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T001 [P] [US1] Add test for no-body request in tests/unit/test_dashboard_handler.py - verify 201 response with defaults
- [x] T002 [P] [US1] Add test for empty-body `{}` request in tests/unit/test_dashboard_handler.py - verify 201 response with defaults
- [x] T003 [P] [US1] Add test for body with custom timezone in tests/unit/test_dashboard_handler.py - verify 201 response with provided timezone

### Implementation for User Story 1

- [x] T004 [US1] Add `Body` import to src/lambdas/dashboard/router_v2.py
- [x] T005 [US1] Modify `create_anonymous_session` function signature in src/lambdas/dashboard/router_v2.py - change `body: auth_service.AnonymousSessionRequest` to `body: auth_service.AnonymousSessionRequest | None = Body(default=None)`
- [x] T006 [US1] Add null-check in `create_anonymous_session` in src/lambdas/dashboard/router_v2.py - if body is None, instantiate `auth_service.AnonymousSessionRequest()`

**Checkpoint**: User Story 1 complete - POST /api/v2/auth/anonymous accepts no body and returns 201.

---

## Phase 4: User Story 2 - Session Persistence (Priority: P2)

**Goal**: Verify existing session persistence behavior works with the fix (no changes expected).

**Independent Test**: Create session, refresh page, verify same user_id returned.

### Verification for User Story 2

- [x] T007 [US2] Verify existing session persistence tests pass in tests/unit/test_dashboard_handler.py - run existing X-User-ID header tests

**Checkpoint**: User Stories 1 AND 2 both work - anonymous auth is fully functional.

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and verification

- [x] T008 Run all unit tests via sub-agent to verify no regressions
- [ ] T009 Run quickstart.md validation - test all three curl scenarios (skip - requires deployed Lambda)
- [x] T010 Verify linting passes (ruff check src/lambdas/dashboard/router_v2.py)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: SKIP - no changes needed
- **Foundational (Phase 2)**: SKIP - no changes needed
- **User Story 1 (Phase 3)**: Can start immediately
- **User Story 2 (Phase 4)**: Verify after US1 complete
- **Polish (Phase 5)**: After all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - can start immediately
- **User Story 2 (P2)**: Depends on US1 completion (uses same endpoint)

### Within User Story 1

1. T001, T002, T003 (tests) - run in parallel, verify they FAIL
2. T004 (import) - no dependencies
3. T005 (signature change) - depends on T004
4. T006 (null-check) - depends on T005
5. Re-run tests - should now PASS

### Parallel Opportunities

- T001, T002, T003 can run in parallel (different test functions, same file)

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all tests together (should FAIL before implementation):
Task: "Add test for no-body request in tests/unit/test_dashboard_handler.py"
Task: "Add test for empty-body request in tests/unit/test_dashboard_handler.py"
Task: "Add test for body with custom timezone in tests/unit/test_dashboard_handler.py"
```

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Write tests T001-T003 (should fail)
2. Implement T004-T006 (fix)
3. Verify tests pass
4. **STOP and VALIDATE**: Test in browser
5. Deploy via PR

### Total Tasks

- **Test tasks**: 3 (T001-T003)
- **Implementation tasks**: 3 (T004-T006)
- **Verification tasks**: 4 (T007-T010)
- **Total**: 10 tasks

### Estimated Time

- Tests: 15 minutes
- Implementation: 10 minutes
- Verification: 15 minutes
- **Total**: ~40 minutes

---

## Notes

- This is a minimal fix - only 1 file modified (router_v2.py)
- auth.py model already has defaults - no changes needed
- Frontend code unchanged - backward compatible fix
- Constitution requires unit tests - included in T001-T003
