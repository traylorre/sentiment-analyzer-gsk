# Tasks: Fix Zustand Persist Hydration

**Input**: Design documents from `/specs/1122-zustand-hydration-fix/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: The spec requires unit tests per Constitution's Implementation Accompaniment Rule.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `frontend/src/` for source, `frontend/tests/` for tests
- Paths are relative to repository root: `/home/traylorre/projects/sentiment-analyzer-gsk/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and verify existing structure

- [X] T001 Verify zustand 5.x is installed with persist middleware in `frontend/package.json`
- [X] T002 Review existing auth-store structure in `frontend/src/stores/auth-store.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core hydration infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Auth Store Hydration Flag (FR-013)

- [X] T003 Add `_hasHydrated: boolean` field to AuthState interface in `frontend/src/stores/auth-store.ts`
- [X] T004 Add `onRehydrateStorage` callback to persist config to set `_hasHydrated: true` in `frontend/src/stores/auth-store.ts`
- [X] T005 Exclude `_hasHydrated` from `partialize` config to prevent persisting it in `frontend/src/stores/auth-store.ts`
- [X] T006 Export `useHasHydrated` selector hook from `frontend/src/stores/auth-store.ts`

### Unit Tests for Hydration Flag

- [ ] T007 [P] Create unit test for `_hasHydrated` starts as false in `frontend/src/stores/__tests__/auth-store.test.ts`
- [ ] T008 [P] Create unit test for `_hasHydrated` becomes true after rehydration in `frontend/src/stores/__tests__/auth-store.test.ts`
- [ ] T009 [P] Create unit test for `_hasHydrated` is NOT persisted to localStorage in `frontend/src/stores/__tests__/auth-store.test.ts`

**Checkpoint**: Foundation ready - `useHasHydrated()` hook available for all components

---

## Phase 3: User Story 1 - First-time User Dashboard Load (Priority: P1) 🎯 MVP

**Goal**: New users see dashboard UI load within 5 seconds with sign-in button visible. No infinite "Initializing session..." hang.

**Independent Test**: Open dashboard URL in incognito browser window (no localStorage), verify page loads with all UI elements visible within 5 seconds.

### Implementation for User Story 1

#### useSessionInit Refactor (FR-016)

- [X] T010 [US1] Refactor useSessionInit to wait for `_hasHydrated` before checking auth state in `frontend/src/hooks/use-session-init.ts`
- [X] T011 [US1] Add useEffect dependency on `_hasHydrated` to trigger init only after hydration in `frontend/src/hooks/use-session-init.ts`
- [X] T012 [US1] Add useRef guard to prevent multiple init attempts in `frontend/src/hooks/use-session-init.ts`

#### useAuth Hook Update

- [X] T013 [US1] Expose `hasHydrated` in useAuth return value from `frontend/src/hooks/use-auth.ts`
- [X] T014 [US1] Ensure session refresh scheduling waits for hydration in `frontend/src/hooks/use-auth.ts`

#### ProtectedRoute Update (FR-014)

- [X] T015 [US1] Import and use `useHasHydrated` hook in `frontend/src/components/auth/protected-route.tsx`
- [X] T016 [US1] Check `_hasHydrated` BEFORE evaluating `isAuthenticated` in `frontend/src/components/auth/protected-route.tsx`
- [X] T017 [US1] Show loading spinner during hydration phase (not just isLoading) in `frontend/src/components/auth/protected-route.tsx`
- [X] T018 [US1] Only redirect after hydration complete + auth check fails in `frontend/src/components/auth/protected-route.tsx`

#### UserMenu Skeleton (FR-017)

- [X] T019 [US1] Create UserMenuSkeleton component in `frontend/src/components/auth/user-menu.tsx`
- [X] T020 [US1] Render skeleton during `!hasHydrated` state in `frontend/src/components/auth/user-menu.tsx`

#### Unit Tests for User Story 1

- [ ] T021 [P] [US1] Test useSessionInit does NOT call signInAnonymous before hydration in `frontend/src/hooks/__tests__/use-session-init.test.ts`
- [ ] T022 [P] [US1] Test useSessionInit calls signInAnonymous after hydration if no session in `frontend/src/hooks/__tests__/use-session-init.test.ts`
- [ ] T023 [P] [US1] Test ProtectedRoute shows loading during hydration in `frontend/src/components/auth/__tests__/protected-route.test.tsx`
- [ ] T024 [P] [US1] Test ProtectedRoute does NOT redirect during hydration in `frontend/src/components/auth/__tests__/protected-route.test.tsx`

**Checkpoint**: At this point, new users should see dashboard load within 5 seconds with sign-in button visible

---

## Phase 4: User Story 2 - Returning User with Valid Session (Priority: P1)

**Goal**: Returning users with valid localStorage session see authenticated state immediately without API call. Dashboard interactive within 2 seconds.

**Independent Test**: Create session, close browser tab, reopen dashboard, verify instant load with session intact and user menu visible.

### Implementation for User Story 2

#### Session Restoration Logic

- [X] T025 [US2] Verify useSessionInit skips signInAnonymous when valid session exists after hydration in `frontend/src/hooks/use-session-init.ts`
- [X] T026 [US2] Verify isSessionValid check runs AFTER hydration completes in `frontend/src/hooks/use-session-init.ts`

#### React Query Hydration Awareness (FR-015)

- [X] T027 [US2] Update useChartData to include `hasHydrated` in `enabled` option in `frontend/src/hooks/use-chart-data.ts`
- [X] T028 [US2] Add refetch trigger when userId transitions from null to valid value in `frontend/src/hooks/use-chart-data.ts`

#### Unit Tests for User Story 2

- [ ] T029 [P] [US2] Test useSessionInit skips API call when valid session exists after hydration in `frontend/src/hooks/__tests__/use-session-init.test.ts`
- [ ] T030 [P] [US2] Test useChartData re-enables query when userId becomes available in `frontend/src/hooks/__tests__/use-chart-data.test.ts`
- [ ] T031 [P] [US2] Test UserMenu shows authenticated state immediately after hydration with valid session in `frontend/src/components/auth/__tests__/user-menu.test.tsx`

**Checkpoint**: Returning users should see authenticated state within 2 seconds without API call

---

## Phase 5: User Story 3 - User with Expired Session (Priority: P2)

**Goal**: Users with expired localStorage session get automatic anonymous session creation with seamless transition (no error messages).

**Independent Test**: Manually set expired session in localStorage, reload dashboard, verify new anonymous session created and dashboard loads normally.

### Implementation for User Story 3

#### Expired Session Handling

- [X] T032 [US3] Verify isSessionValid correctly identifies expired sessions in `frontend/src/hooks/use-session-init.ts`
- [X] T033 [US3] Ensure clearAuth clears expired data from localStorage before new session in `frontend/src/stores/auth-store.ts`
- [X] T034 [US3] Verify signInAnonymous called after hydration when session invalid in `frontend/src/hooks/use-session-init.ts`

#### Unit Tests for User Story 3

- [ ] T035 [P] [US3] Test expired session detection triggers signInAnonymous after hydration in `frontend/src/hooks/__tests__/use-session-init.test.ts`
- [ ] T036 [P] [US3] Test clearAuth properly clears localStorage before new session in `frontend/src/stores/__tests__/auth-store.test.ts`

**Checkpoint**: Expired session users should get new anonymous session automatically with no error messages

---

## Phase 6: Edge Cases & Error Handling

**Purpose**: Handle edge cases from spec (FR-004, FR-006)

### localStorage Unavailable (FR-004)

- [X] T037 Add graceful fallback for localStorage unavailable (private browsing) in `frontend/src/stores/auth-store.ts`

### Hydration Timeout (FR-006)

- [X] T038 Add 5-second timeout for hydration with graceful degradation in `frontend/src/hooks/use-session-init.ts`
- [X] T039 Proceed with empty state after timeout (fall through to signInAnonymous) in `frontend/src/hooks/use-session-init.ts`

### Settings Page Hydration (FR-018)

- [X] T040 Add hydration-aware rendering to prevent fallback UI flash in `frontend/src/app/(dashboard)/settings/page.tsx`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T041 Run `npm run lint` to verify no linting errors in frontend
- [X] T042 Run `npm run build` to verify TypeScript compilation succeeds
- [X] T043 Run `npm run test` to verify all unit tests pass
- [ ] T044 Validate quickstart.md scenarios work as documented
- [ ] T045 Test all three user stories manually in browser

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 priority but US1 provides the core fix
  - US2 builds on US1's hydration infrastructure
  - US3 (P2) can proceed after US1/US2
- **Edge Cases (Phase 6)**: Depends on all user stories being complete
- **Polish (Phase 7)**: Depends on all previous phases

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Provides core hydration fix
- **User Story 2 (P1)**: Can start after US1 core hooks are updated - Tests session restoration
- **User Story 3 (P2)**: Can start after US1/US2 - Tests expired session handling

### Within Each User Story

- Implementation tasks before their tests (tests verify implementation)
- Auth store changes before hooks
- Hooks before components
- Core implementation before integration

### Parallel Opportunities

- All Foundational unit tests (T007-T009) can run in parallel
- All US1 unit tests (T021-T024) can run in parallel after implementation
- All US2 unit tests (T029-T031) can run in parallel after implementation
- All US3 unit tests (T035-T036) can run in parallel after implementation

---

## Parallel Example: Foundational Phase

```bash
# After T003-T006 complete, launch all unit tests together:
Task: T007 [P] Test _hasHydrated starts as false
Task: T008 [P] Test _hasHydrated becomes true after rehydration
Task: T009 [P] Test _hasHydrated is NOT persisted
```

---

## Parallel Example: User Story 1 Tests

```bash
# After T010-T020 implementation complete, launch all US1 tests together:
Task: T021 [P] [US1] Test useSessionInit does NOT call signInAnonymous before hydration
Task: T022 [P] [US1] Test useSessionInit calls signInAnonymous after hydration
Task: T023 [P] [US1] Test ProtectedRoute shows loading during hydration
Task: T024 [P] [US1] Test ProtectedRoute does NOT redirect during hydration
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T009) - CRITICAL
3. Complete Phase 3: User Story 1 (T010-T024)
4. **STOP and VALIDATE**: Test incognito browser - dashboard loads within 5 seconds
5. This fixes the core "Initializing session..." hang for ALL users

### Incremental Delivery

1. Complete Setup + Foundational → `_hasHydrated` infrastructure ready
2. Add User Story 1 → Test incognito → Core fix deployed (MVP!)
3. Add User Story 2 → Test returning user → Session restoration verified
4. Add User Story 3 → Test expired session → Complete edge case coverage
5. Add Edge Cases + Polish → Production-ready

### File Summary

| File | Tasks | Changes |
|------|-------|---------|
| `frontend/src/stores/auth-store.ts` | T003-T006, T033, T037 | Add `_hasHydrated`, `onRehydrateStorage`, `useHasHydrated` |
| `frontend/src/hooks/use-session-init.ts` | T010-T012, T025-T026, T032, T034, T038-T039 | Wait for hydration, centralize init |
| `frontend/src/hooks/use-auth.ts` | T013-T014 | Expose `hasHydrated` |
| `frontend/src/hooks/use-chart-data.ts` | T027-T028 | Hydration-aware enabled |
| `frontend/src/components/auth/protected-route.tsx` | T015-T018 | Check hydration before auth |
| `frontend/src/components/auth/user-menu.tsx` | T019-T020 | Skeleton during hydration |
| `frontend/src/app/(dashboard)/settings/page.tsx` | T040 | Hydration-aware rendering |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 45
- Tasks per story: US1=15, US2=7, US3=5, Foundational=9, Edge=4, Polish=5
