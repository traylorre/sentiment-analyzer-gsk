# Tasks: Remove Zustand Persist Middleware

**Input**: Design documents from `/specs/1131-remove-zustand-persist/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md

**Tests**: Unit tests requested to verify token non-persistence behavior.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new project initialization needed - this is a modification to existing codebase

- [x] T001 Verify current zustand persist configuration in frontend/src/stores/auth-store.ts

**Checkpoint**: Existing code reviewed, ready for implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: No foundational tasks needed - this feature modifies existing infrastructure

**⚠️ NOTE**: This is a surgical modification to existing persist() middleware. No new infrastructure required.

**Checkpoint**: Foundation ready - user story implementation can begin

---

## Phase 3: User Story 1 - Secure Token Storage (Priority: P1) 🎯 MVP

**Goal**: Remove authentication tokens from localStorage persistence to prevent XSS attacks

**Independent Test**: After implementation, inspect browser localStorage using DevTools and verify no `tokens` (accessToken, refreshToken, idToken) appear. Verify the application still functions correctly for authenticated users.

### Tests for User Story 1

- [x] T002 [P] [US1] Create unit test for token non-persistence in frontend/tests/unit/stores/auth-store.test.ts

### Implementation for User Story 1

- [x] T003 [US1] Remove `tokens` from partialize function in frontend/src/stores/auth-store.ts
- [x] T004 [US1] Add onRehydrate migration to clear existing tokens from localStorage in frontend/src/stores/auth-store.ts

**Checkpoint**: At this point, tokens are no longer persisted and existing tokens are cleared on app load

---

## Phase 4: User Story 2 - Preserve Non-Sensitive Session State (Priority: P2)

**Goal**: Ensure non-sensitive session flags (isAuthenticated, isAnonymous, sessionExpiresAt, user) continue to persist

**Independent Test**: Verify that after page refresh, the application correctly identifies whether the user was previously authenticated (even if they need to re-authenticate).

### Implementation for User Story 2

- [x] T005 [US2] Verify partialize still includes non-sensitive fields (user, sessionExpiresAt, isAuthenticated, isAnonymous) in frontend/src/stores/auth-store.ts

**Checkpoint**: Non-sensitive session state persists correctly while tokens remain in memory only

---

## Phase 5: Polish & Cross-Cutting Concerns

**Purpose**: Verification and cleanup

- [x] T006 [P] Run existing frontend unit tests to verify no regressions (npm run test in frontend/)
- [x] T007 Run TypeScript type check (npm run typecheck in frontend/)
- [x] T008 Run linting (npm run lint in frontend/)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Review existing code
- **Foundational (Phase 2)**: No new infrastructure needed
- **User Story 1 (Phase 3)**: Core security fix - remove tokens from persistence
- **User Story 2 (Phase 4)**: Verify non-sensitive fields still persist
- **Polish (Phase 5)**: Final verification

### User Story Dependencies

- **User Story 1 (P1)**: Independent - core security fix
- **User Story 2 (P2)**: Depends on US1 completion - verification of remaining persistence

### Within Each User Story

- T002 (test) should be written to verify expected behavior
- T003 and T004 implement the core change
- T005 verifies non-breaking behavior

### Parallel Opportunities

- T002 and T003 can be developed in parallel (test-first)
- T006, T007, T008 can run in parallel (different tools)

---

## Parallel Example: User Story 1

```bash
# Write test first, then implement:
Task: "Create unit test for token non-persistence in frontend/tests/unit/stores/auth-store-persist.test.ts"

# Then implement both changes:
Task: "Remove tokens from partialize function in frontend/src/stores/auth-store.ts"
Task: "Add onRehydrate migration to clear existing tokens from localStorage in frontend/src/stores/auth-store.ts"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Review existing code
2. Complete Phase 3: User Story 1 (core security fix)
3. **STOP and VALIDATE**: Test token non-persistence independently
4. Continue to Phase 4 and 5 for full validation

### Key Files Modified

| File | Change |
|------|--------|
| `frontend/src/stores/auth-store.ts` | Remove `tokens` from partialize, add onRehydrate migration |
| `frontend/tests/unit/stores/auth-store-persist.test.ts` | NEW - Unit tests for persistence behavior |

### Expected Code Changes

**partialize modification** (remove one line):
```typescript
// BEFORE
partialize: (state) => ({
  user: state.user,
  tokens: state.tokens,           // REMOVE THIS LINE
  sessionExpiresAt: state.sessionExpiresAt,
  isAuthenticated: state.isAuthenticated,
  isAnonymous: state.isAnonymous,
}),

// AFTER
partialize: (state) => ({
  user: state.user,
  sessionExpiresAt: state.sessionExpiresAt,
  isAuthenticated: state.isAuthenticated,
  isAnonymous: state.isAnonymous,
}),
```

**onRehydrate migration** (add cleanup logic):
```typescript
onRehydrate: (state) => {
  // Migration: Clear any existing tokens from localStorage
  if (typeof window !== 'undefined') {
    const stored = localStorage.getItem('auth-store');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        if (parsed.state?.tokens) {
          delete parsed.state.tokens;
          localStorage.setItem('auth-store', JSON.stringify(parsed));
        }
      } catch {
        // Ignore parse errors
      }
    }
  }
}
```

---

## Notes

- This is a security fix with CVSS 8.6
- The change is minimal - one line removal from partialize + migration cleanup
- Existing tests should continue to pass
- Users may need to re-authenticate after page refresh (acceptable tradeoff)
- httpOnly cookies provide session continuity if implemented
