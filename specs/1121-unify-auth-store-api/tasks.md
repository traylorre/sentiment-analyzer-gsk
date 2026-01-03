# Tasks: Unify Auth-Store API Client

**Input**: Design documents from `/specs/1121-unify-auth-store-api/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, quickstart.md

**Tests**: Not explicitly requested - focusing on implementation only.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `frontend/src/` (this feature affects frontend only)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify existing authApi client and understand current implementation

- [x] T001 Verify authApi methods exist in frontend/src/lib/api/auth.ts
- [x] T002 Review current auth-store.ts implementation in frontend/src/stores/auth-store.ts

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ensure authApi import is available and types are compatible

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Verify authApi is already imported in frontend/src/stores/auth-store.ts (used by signInAnonymous)
- [x] T004 Review authApi response types match store expectations in frontend/src/lib/api/auth.ts

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - OAuth Sign-In Flow (Priority: P1) 🎯 MVP

**Goal**: Fix "Continue with Google/GitHub" button to fetch OAuth URLs from backend without 404

**Independent Test**: Click "Continue with Google" → should redirect to Google consent screen (not 404)

### Implementation for User Story 1

- [x] T005 [US1] Replace fetch('/api/v2/auth/oauth/urls') with authApi.getOAuthUrls() in signInWithOAuth method in frontend/src/stores/auth-store.ts
- [x] T006 [US1] Update response handling to access urls[provider] from authApi response in frontend/src/stores/auth-store.ts

**Checkpoint**: OAuth URL fetching works - users see Google/GitHub consent screen

---

## Phase 4: User Story 2 - OAuth Callback Processing (Priority: P1)

**Goal**: Fix OAuth callback to exchange authorization code for tokens without 404

**Independent Test**: Complete OAuth flow → should create authenticated session

### Implementation for User Story 2

- [x] T007 [US2] Replace fetch('/api/v2/auth/oauth/callback') with authApi.exchangeOAuthCode(provider, code) in handleOAuthCallback method in frontend/src/stores/auth-store.ts
- [x] T008 [US2] Map AuthResponse to store state (setUser, setTokens, setSession) in frontend/src/stores/auth-store.ts

**Checkpoint**: Complete OAuth flow works end-to-end

---

## Phase 5: User Story 3 - Magic Link Authentication (Priority: P2)

**Goal**: Fix magic link request and verification without 404

**Independent Test**: Request magic link → click link → should authenticate user

### Implementation for User Story 3

- [x] T009 [US3] Replace fetch('/api/v2/auth/magic-link') with authApi.requestMagicLink(email) in signInWithMagicLink method in frontend/src/stores/auth-store.ts
- [x] T010 [US3] Replace fetch('/api/v2/auth/magic-link/verify') with authApi.verifyMagicLink(token, sig) in verifyMagicLink method in frontend/src/stores/auth-store.ts
- [x] T011 [US3] Update verifyMagicLink method signature to accept sig parameter in frontend/src/stores/auth-store.ts

**Checkpoint**: Magic link flow works end-to-end

---

## Phase 6: User Story 4 - Session Refresh (Priority: P2)

**Goal**: Fix automatic token refresh without 404

**Independent Test**: Let token expire → should auto-refresh without errors

### Implementation for User Story 4

- [x] T012 [US4] Replace fetch('/api/v2/auth/refresh') with authApi.refreshToken(refreshToken) in refreshSession method in frontend/src/stores/auth-store.ts
- [x] T013 [US4] Map RefreshTokenResponse to existing tokens in frontend/src/stores/auth-store.ts

**Checkpoint**: Token refresh works automatically

---

## Phase 7: User Story 5 - Sign Out (Priority: P3)

**Goal**: Fix sign out to notify backend without 404

**Independent Test**: Click sign out → should clear session both locally and server-side

### Implementation for User Story 5

- [x] T014 [US5] Replace fetch('/api/v2/auth/signout') with authApi.signOut() in signOut method in frontend/src/stores/auth-store.ts
- [x] T015 [US5] Remove manual Authorization header (authApi handles it) in frontend/src/stores/auth-store.ts

**Checkpoint**: Sign out works - session invalidated everywhere

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Verify all changes work together and build succeeds

- [x] T016 Run TypeScript build to verify no type errors (npm run build in frontend/)
- [x] T017 Run linter to verify code quality (npm run lint in frontend/)
- [ ] T018 Manual smoke test: OAuth flow, magic link, refresh, sign out

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories CAN proceed in parallel (all modify same file but different methods)
  - Recommended: sequential to avoid merge conflicts
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: OAuth URLs - No dependencies on other stories
- **User Story 2 (P1)**: OAuth Callback - Can test independently but typically follows US1
- **User Story 3 (P2)**: Magic Link - Independent of OAuth stories
- **User Story 4 (P2)**: Session Refresh - Independent of auth method stories
- **User Story 5 (P3)**: Sign Out - Independent of other stories

### Within Each User Story

- Replace fetch() call first
- Then update response handling
- Stories are independent and can be tested separately

### Parallel Opportunities

Since all tasks modify the same file (auth-store.ts), parallel execution would cause conflicts.
**Recommended**: Execute stories sequentially in priority order (P1 → P2 → P3).

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (OAuth URLs)
4. Complete Phase 4: User Story 2 (OAuth Callback)
5. **STOP and VALIDATE**: Test complete OAuth flow
6. Deploy if OAuth is primary auth method

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 + 2 → OAuth works → Deploy (MVP!)
3. Add User Story 3 → Magic link works → Deploy
4. Add User Story 4 → Token refresh works → Deploy
5. Add User Story 5 → Sign out works → Deploy

---

## Notes

- All tasks modify the same file: `frontend/src/stores/auth-store.ts`
- The `authApi` client already exists and handles URL construction
- Error handling patterns (try/catch/setError) should be preserved
- Each story can be tested independently after implementation
- Commit after each story completion for easy rollback
