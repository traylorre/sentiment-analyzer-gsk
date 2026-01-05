# Tasks: Remove X-User-ID Header Fallback

**Input**: Design documents from `/specs/1146-remove-xuserid-fallback/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: This feature REQUIRES new security tests to verify the vulnerability is closed. Existing tests must be updated to use Bearer tokens.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=Security Fix, US2=Application Stability)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `src/lambdas/shared/middleware/`, `src/lambdas/dashboard/`
- **Frontend**: `frontend/src/lib/api/`, `frontend/src/stores/`
- **Tests**: `tests/unit/`, `tests/e2e/`
- **CI/CD**: `.github/workflows/`

---

## Phase 1: Setup (No Setup Required)

**Purpose**: This is a security fix removing existing code - no new project setup needed.

**Checkpoint**: Proceed directly to Foundational phase.

---

## Phase 2: Foundational (Test Infrastructure Update)

**Purpose**: Update test infrastructure to use Bearer tokens instead of X-User-ID headers. MUST complete before user story implementation to prevent test failures.

**⚠️ CRITICAL**: These test updates are blocking - the security fix will cause all X-User-ID tests to fail.

- [X] T001 [P] Update AUTH_HEADERS constant from X-User-ID to Bearer in tests/unit/dashboard/test_sentiment_history.py
- [X] T002 [P] Update all X-User-ID headers to Bearer format in tests/unit/dashboard/test_ohlc.py (~17 occurrences)
- [X] T003 [P] Update X-User-ID headers to Bearer format in tests/unit/dashboard/test_sse.py
- [X] T004 [P] Update 6 X-User-ID test cases in tests/unit/lambdas/shared/auth/test_session_consistency.py to use Bearer
- [X] T005 [P] Review and update tests/e2e/test_metrics_auth.py for Bearer authentication (uses API client abstraction - no changes needed)
- [X] T006 [P] Review and update tests/e2e/test_anonymous_restrictions.py for Bearer authentication (uses API client abstraction - no changes needed)
- [X] T007 Update warmup requests in .github/workflows/deploy.yml from X-User-ID to Bearer format (lines 1252-1280)

**Checkpoint**: All tests should still pass with existing code (X-User-ID fallback still exists). Tests are now ready for the security fix.

---

## Phase 3: User Story 1 - Security Fix (Priority: P1) 🎯 MVP

**Goal**: Close CVSS 9.1 Critical vulnerability by removing X-User-ID header fallback from auth middleware.

**Independent Test**: Send request with X-User-ID header only (no Bearer token) → expect 401 Unauthorized.

### New Security Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before removing the fallback**

- [X] T008 [P] [US1] Add test_x_user_id_header_ignored() in tests/unit/dashboard/test_auth.py - verify X-User-ID with valid Bearer still uses Bearer identity
- [X] T009 [P] [US1] Add test_x_user_id_without_bearer_returns_401() in tests/unit/dashboard/test_auth.py - verify X-User-ID alone gets 401
- [X] T010 [P] [US1] Add test_bearer_only_authentication() in tests/unit/dashboard/test_auth.py - verify only Bearer accepted

### Implementation for User Story 1

- [X] T011 [US1] Remove X-User-ID fallback from extract_user_id() in src/lambdas/shared/middleware/auth_middleware.py (lines 204-212)
- [X] T012 [US1] Remove X-User-ID fallback from extract_auth_context_typed() in src/lambdas/shared/middleware/auth_middleware.py (lines 314-325)
- [X] T013 [US1] Update docstrings in auth_middleware.py to document Bearer-only authentication
- [X] T014 [P] [US1] Review and remove X-User-ID reads from router_v2.py (lines 283, 321, 420) - refactored to use get_user_id_from_request()
- [X] T015 [US1] Run unit tests to verify security tests now pass (T008-T010) - All 39 tests passed

**Checkpoint**: Security vulnerability closed. Requests with only X-User-ID header return 401. All unit tests pass.

---

## Phase 4: User Story 2 - Application Stability (Priority: P2)

**Goal**: Ensure all legitimate authentication flows continue working after the security fix.

**Independent Test**: Perform magic link, OAuth, and anonymous authentication flows → all should succeed with proper Bearer tokens.

### Tests for User Story 2

> **NOTE: Existing tests should pass - these verify no regression**

- [X] T016 [US2] Run existing auth flow tests to verify magic link still works (covered by auth tests)
- [X] T017 [US2] Run existing auth flow tests to verify OAuth still works (covered by auth tests)
- [X] T018 [US2] Run existing auth flow tests to verify anonymous session still works (covered by auth tests)

### Implementation for User Story 2 (Frontend Updates)

- [X] T019 [P] [US2] Remove X-User-ID header fallback from frontend/src/lib/api/client.ts (lines 115-121)
- [X] T020 [P] [US2] Update setUserId in auth-store.ts to ensure Bearer token is set (lines 70-71)
- [X] T021 [US2] Verify frontend builds without errors after X-User-ID removal - TypeScript + lint pass
- [X] T022 [US2] Run frontend unit tests to verify no regressions - 414/414 tests pass

**Checkpoint**: Frontend uses Bearer-only authentication. All auth flows work correctly.

---

## Phase 5: Polish & Verification

**Purpose**: Final verification and documentation

- [X] T023 Run full test suite (make test-local) to verify zero regressions - 2588/2588 unit tests pass
- [X] T024 Grep codebase for any remaining X-User-ID references that might be missed - 417 refs found, most are comments/docs or tests verifying rejection
- [X] T025 [P] Update integration/E2E test helpers to use Bearer tokens (api_client.py, auth_headers fixtures)
- [ ] T026 Run E2E tests in preprod to verify all auth flows work end-to-end (requires deployment)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Skipped - no setup required
- **Foundational (Phase 2)**: Must complete first - updates tests to prevent failures
- **User Story 1 (Phase 3)**: Depends on Phase 2 - security fix
- **User Story 2 (Phase 4)**: Depends on Phase 3 - frontend alignment
- **Polish (Phase 5)**: Depends on Phase 3 and 4 - final verification

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2)
- **User Story 2 (P2)**: Can start after US1 complete (frontend needs backend fix deployed/tested first)

### Within Each Phase

- Security tests (T008-T010) MUST be written and FAIL before T011-T012
- Backend fix (T011-T012) before frontend update (T019-T020)
- Each task commits independently

### Parallel Opportunities

- **Phase 2**: All T001-T007 can run in parallel (different files)
- **Phase 3 Tests**: T008, T009, T010 can run in parallel
- **Phase 4 Frontend**: T019, T020 can run in parallel (different files)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all test updates in parallel (different files):
Task: "Update AUTH_HEADERS in tests/unit/dashboard/test_sentiment_history.py"
Task: "Update X-User-ID headers in tests/unit/dashboard/test_ohlc.py"
Task: "Update X-User-ID headers in tests/unit/dashboard/test_sse.py"
Task: "Update tests in tests/unit/lambdas/shared/auth/test_session_consistency.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (test updates)
2. Complete Phase 3: User Story 1 (security fix)
3. **STOP and VALIDATE**: Run unit tests, verify 401 for X-User-ID only
4. Can deploy backend independently if frontend update is delayed

### Incremental Delivery

1. Phase 2 → Test infrastructure ready
2. Phase 3 (US1) → Security vulnerability closed (MVP!)
3. Phase 4 (US2) → Frontend aligned with new auth model
4. Phase 5 → Final polish and E2E verification

### Sequential Execution (Recommended)

This feature should be executed sequentially (not parallel teams) because:
- Security fix is atomic
- Frontend depends on backend fix
- All changes must land together for consistency

---

## Notes

- [P] tasks = different files, no dependencies
- [US1] = Security Fix (CVSS 9.1 Critical)
- [US2] = Application Stability (non-breaking)
- T011-T012 are the CRITICAL security fix tasks
- All existing tests must pass after T001-T007
- Security tests (T008-T010) must fail before T011-T012, pass after
- Commit after each task or logical group
- Total tasks: 26
- US1 tasks: 8 (security focus)
- US2 tasks: 7 (stability focus)
- Foundational: 7 (test prep)
- Polish: 4 (verification)
