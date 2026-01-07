# Tasks: CSRF Double-Submit Cookie Pattern

**Input**: Design documents from `/specs/1158-csrf-double-submit/`
**Prerequisites**: plan.md, spec.md, research.md

**Tests**: Included - security feature requires comprehensive test coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create CSRF module and middleware structure

- [x] T001 [P] Create CSRF token module at src/lambdas/shared/auth/csrf.py with generate_csrf_token() and validate_csrf_token() functions
- [x] T002 [P] Create CSRF middleware at src/lambdas/shared/middleware/csrf_middleware.py with require_csrf() dependency function

**Checkpoint**: CSRF module and middleware ready for router integration

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: None - this feature has no blocking prerequisites beyond Phase 1

**⚠️ CRITICAL**: Phase 1 must complete before user story implementation

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - State-Changing Request Protection (Priority: P1) 🎯 MVP

**Goal**: Protect all state-changing API requests from CSRF attacks by validating token in header matches cookie

**Independent Test**: Make POST request with/without valid CSRF token, verify appropriate accept/reject behavior

### Tests for User Story 1

- [x] T003 [P] [US1] Create CSRF unit tests at tests/unit/middleware/test_csrf.py with test_generate_csrf_token_format, test_validate_matching_tokens, test_validate_mismatched_tokens, test_validate_missing_tokens

### Implementation for User Story 1

- [x] T004 [US1] Integrate CSRF middleware into router_v2.py by adding require_csrf dependency to state-changing endpoints in auth_router
- [x] T005 [US1] Add CSRF token cookie setting in magic link verify response at src/lambdas/dashboard/router_v2.py
- [x] T006 [US1] Add CSRF token cookie setting in OAuth callback response at src/lambdas/dashboard/router_v2.py
- [x] T007 [US1] Configure exempt paths (/api/v2/auth/refresh) in csrf_middleware.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Backend CSRF protection is complete.

---

## Phase 4: User Story 2 - Frontend Token Integration (Priority: P2)

**Goal**: Frontend reads CSRF cookie and includes token in X-CSRF-Token header for all state-changing requests

**Independent Test**: Verify frontend correctly reads cookie and includes header in fetch requests

### Tests for User Story 2

- [x] T008 [P] [US2] Create frontend unit tests at frontend/tests/unit/lib/test_csrf.ts for getCsrfToken() and includesCsrfHeader()

### Implementation for User Story 2

- [x] T009 [US2] Add getCsrfToken() helper function in frontend/src/lib/api/client.ts to read csrf_token cookie
- [x] T010 [US2] Modify fetchWithAuth() in frontend/src/lib/api/client.ts to include X-CSRF-Token header for POST/PUT/PATCH/DELETE requests
- [x] T011 [US2] Add CSRF error handling in frontend to show user-friendly message on 403 CSRF rejection

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. Full frontend-backend CSRF flow is operational.

---

## Phase 5: User Story 3 - Token Lifecycle Management (Priority: P3)

**Goal**: CSRF tokens are refreshed at appropriate points in authentication lifecycle

**Independent Test**: Verify tokens are set on login/refresh and remain valid throughout session

### Implementation for User Story 3

- [x] T012 [US3] Add CSRF cookie refresh in token refresh endpoint response at src/lambdas/dashboard/router_v2.py
- [x] T013 [US3] Ensure CSRF cookie max_age aligns with session lifetime (86400 seconds)

**Checkpoint**: All user stories should now be independently functional. Complete CSRF lifecycle management is in place.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T014 Run all unit tests to verify no regressions (pytest tests/unit/middleware/test_csrf.py)
- [x] T015 Verify existing authenticated flows still work with CSRF protection enabled

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: N/A for this feature
- **User Stories (Phase 3+)**: All depend on Phase 1 completion
  - US1 (backend) can complete independently
  - US2 (frontend) can proceed in parallel with US1
  - US3 (lifecycle) depends on US1
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Phase 1 - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Phase 1 - Frontend integration independent of backend integration
- **User Story 3 (P3)**: Depends on US1 - Token refresh requires CSRF middleware to be integrated

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- T001 and T002 can run in parallel (different files)
- T003 (tests) and T008 (frontend tests) can run in parallel
- US1 implementation and US2 implementation can proceed in parallel after Phase 1

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all Phase 1 tasks together:
Task: "Create CSRF token module at src/lambdas/shared/auth/csrf.py"
Task: "Create CSRF middleware at src/lambdas/shared/middleware/csrf_middleware.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001, T002)
2. Complete Phase 3: User Story 1 (T003-T007)
3. **STOP and VALIDATE**: Test CSRF protection with curl/Postman
4. Backend protection is complete - can deploy

### Incremental Delivery

1. Complete Setup → CSRF module ready
2. Add User Story 1 → Backend protection complete → Test with API tools
3. Add User Story 2 → Frontend integration complete → Test with browser
4. Add User Story 3 → Token lifecycle complete → Full feature complete

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Security feature - all tests should validate security properties
- Use hmac.compare_digest for constant-time comparison (security critical)
- CSRF cookie must be httpOnly=False so JavaScript can read it
