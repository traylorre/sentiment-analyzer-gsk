# Tasks: Delete Cookies.ts Security Fix

**Input**: Design documents from `/specs/1145-delete-cookies-ts/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Tests**: No new tests required - this is a deletion task. Existing tests must pass after deletion.

**Organization**: Tasks are combined since both user stories (Security Fix + Application Stability) are interdependent and must be done together.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1=Security Fix, US2=App Stability)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `frontend/src/` for source, `frontend/tests/` for tests

---

## Phase 1: File Deletions (Security Vulnerability Removal)

**Purpose**: Remove XSS-vulnerable code (CVSS 8.6)

- [ ] T001 [P] [US1] Delete frontend/src/lib/cookies.ts (XSS vulnerability source)
- [ ] T002 [P] [US1] Delete frontend/tests/unit/lib/cookies.test.ts (tests deleted code)

**Checkpoint**: Vulnerable code removed from codebase

---

## Phase 2: Dependency Updates (Application Stability)

**Purpose**: Update files that depend on deleted code

- [ ] T003 [US2] Remove import statement from frontend/src/stores/auth-store.ts: `import { setAuthCookies, clearAuthCookies } from '@/lib/cookies';`
- [ ] T004 [US2] Remove all calls to setAuthCookies() in frontend/src/stores/auth-store.ts
- [ ] T005 [US2] Remove all calls to clearAuthCookies() in frontend/src/stores/auth-store.ts

**Checkpoint**: All imports and function calls removed

---

## Phase 3: Verification

**Purpose**: Ensure application still works after changes

- [ ] T006 Run TypeScript compilation check: `cd frontend && npm run typecheck`
- [ ] T007 Run frontend unit tests: `cd frontend && npm run test`
- [ ] T008 Verify build succeeds: `cd frontend && npm run build`

**Checkpoint**: All verification passes - feature complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Deletions)**: No dependencies - can start immediately
- **Phase 2 (Updates)**: Can run in parallel with Phase 1 (different files)
- **Phase 3 (Verification)**: Depends on Phase 1 and Phase 2 completion

### Parallel Opportunities

```bash
# Phase 1 tasks can run in parallel:
Task T001: Delete frontend/src/lib/cookies.ts
Task T002: Delete frontend/tests/unit/lib/cookies.test.ts

# Phase 2 tasks are sequential (same file):
Task T003 → T004 → T005 (all in auth-store.ts)

# Or combined as single edit (T003-T005 together)
```

---

## Implementation Strategy

### All-at-Once (Recommended for this feature)

1. Delete both files (T001, T002) in parallel
2. Edit auth-store.ts to remove imports/calls (T003-T005)
3. Run verification (T006-T008)
4. Commit and push

### Task Consolidation Note

For this simple feature, T003-T005 can be done as a single edit operation:
- Open `frontend/src/stores/auth-store.ts`
- Remove the import line
- Remove all `setAuthCookies()` calls
- Remove all `clearAuthCookies()` calls
- Save file

---

## Notes

- Total tasks: 8
- Deletions: 2 files
- Edits: 1 file
- Verification: 3 checks
- No new code written - this is a removal task
- All user stories (US1 + US2) must complete together
- Commit after all changes for atomic security fix
