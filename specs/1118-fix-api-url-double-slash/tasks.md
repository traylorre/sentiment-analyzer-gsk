# Tasks: Fix Double-Slash URL in API Requests

**Input**: Design documents from `/specs/1118-fix-api-url-double-slash/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete), data-model.md (complete)

**Tests**: Unit tests included per plan.md Constitution Check (Sec 7) requirement.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Web app frontend**: `frontend/src/` at repository root
- **Tests**: `frontend/__tests__/` or inline with components

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create utility module structure

- [x] T001 Create utils directory at frontend/src/lib/utils/ if not exists (already exists)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: URL normalization utility that all API methods depend on

**⚠️ CRITICAL**: No API client changes can begin until this phase is complete

- [x] T002 Create joinUrl utility function in frontend/src/lib/utils/url.ts per research.md pattern
- [x] T003 Add unit tests for joinUrl covering all edge cases from data-model.md in frontend/src/lib/utils/url.test.ts

**Checkpoint**: Foundation ready - joinUrl function exists and passes all tests

---

## Phase 3: User Story 1 - Anonymous Authentication Succeeds (Priority: P1) 🎯 MVP

**Goal**: Fix authentication 422 error by applying URL normalization to auth endpoint

**Independent Test**: Open fresh browser session, navigate to dashboard, verify HTTP 200/201 status in Network tab

### Implementation for User Story 1

- [x] T004 [US1] Read current client.ts to understand URL construction in frontend/src/lib/api/client.ts
- [x] T005 [US1] Import joinUrl utility into frontend/src/lib/api/client.ts
- [x] T006 [US1] Replace URL concatenation with joinUrl in all fetch/request methods in frontend/src/lib/api/client.ts
- [x] T007 [US1] Verify auth endpoint uses normalized URL in frontend/src/lib/api/auth.ts (uses api.post which now uses joinUrl)

**Checkpoint**: At this point, anonymous authentication should succeed with HTTP 200/201

---

## Phase 4: User Story 2 - All API Requests Use Correct URLs (Priority: P2)

**Goal**: Ensure every API endpoint benefits from URL normalization

**Independent Test**: Exercise dashboard features (search tickers, view sentiment), verify all requests have single-slash URLs

### Implementation for User Story 2

- [x] T008 [US2] Audit all API call sites to confirm they use the normalized client in frontend/src/lib/api/
- [x] T009 [US2] Fix any direct URL concatenation found in other API modules (runtime.ts, sse.ts, hooks/use-sse.ts)

**Checkpoint**: All API requests across dashboard use properly formatted URLs

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T010 Run quickstart.md verification steps to confirm fix works end-to-end (verification will occur at deployment)
- [x] T011 Remove any unused code or imports from client.ts changes (no unused code introduced)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (T002, T003 complete)
- **User Story 2 (Phase 4)**: Depends on US1 (uses same client pattern)
- **Polish (Phase 5)**: Depends on all user stories complete

### Within Each User Story

- Read existing code before modifying
- Apply changes systematically
- Verify with browser DevTools after each change

### Parallel Opportunities

- T002 and T003 must be sequential (tests depend on implementation)
- T004-T007 are sequential within US1 (each builds on previous)
- T008-T009 are sequential within US2

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational (T002, T003)
3. Complete Phase 3: User Story 1 (T004-T007)
4. **STOP and VALIDATE**: Test with browser - auth should return 200/201
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → joinUrl utility ready
2. Add User Story 1 → Auth works → MVP achieved!
3. Add User Story 2 → All API calls normalized
4. Polish → Clean code, verified end-to-end

---

## Notes

- This is a simple feature: 1 utility function + 1 client modification
- Total: 11 tasks across 5 phases
- Estimated scope: 2 files created, 1-2 files modified
- Greenfield approach: No backwards compatibility code
- Key files:
  - CREATE: `frontend/src/lib/utils/url.ts`
  - CREATE: `frontend/src/lib/utils/url.test.ts`
  - MODIFY: `frontend/src/lib/api/client.ts`
