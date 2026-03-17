# Tasks: E2E Test Coverage Expansion (1223)

**Input**: Design documents from `/specs/1223-e2e-test-coverage/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: This IS a testing feature — all tasks produce test code.

**Organization**: Tasks grouped by user story (US1-US6). Each story produces independently runnable Playwright tests.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1=OAuth, US2=Magic Link, US3=Alerts, US4=Session, US5=Account Linking, US6=Cross-Browser

---

## Phase 1: Setup

**Purpose**: Create shared test helpers and directory structure

- [x] T001 Create directory structure: `frontend/tests/auth/`, `frontend/tests/alerts/`, `frontend/tests/session/`, `frontend/tests/account/`, `frontend/tests/helpers/`
- [x] T002 Create shared auth helper with anonymous session creation and test run ID generation in `frontend/tests/helpers/auth-helper.ts`
- [x] T003 [P] Create DynamoDB token query helper for magic link extraction in `frontend/tests/helpers/dynamo-helper.ts`

---

## Phase 2: Foundational

**Purpose**: OAuth route interception utility used by US1, US4, US5

- [x] T004 Create OAuth route interception utility in `frontend/tests/helpers/auth-helper.ts` — `mockOAuthRedirect(page, provider, options)` function that registers `page.route()` to intercept Cognito authorize URL and redirect to callback with mock code+state
- [x] T005 Create test data cleanup utility in `frontend/tests/helpers/auth-helper.ts` — `cleanupTestData(runId)` function for afterAll hooks

**Checkpoint**: Shared helpers ready. All user stories can proceed.

---

## Phase 3: User Story 1 — OAuth Login Flow (Priority: P1) 🎯 MVP

**Goal**: Verify complete OAuth login flow via Playwright route interception.

**Independent Test**: `npx playwright test frontend/tests/auth/oauth-flow.spec.ts`

- [x] T006 [US1] Write test: Google OAuth redirect URL contains state, code_challenge, correct scopes in `frontend/tests/auth/oauth-flow.spec.ts`
- [x] T007 [US1] Write test: successful OAuth callback creates session and loads authenticated dashboard in `frontend/tests/auth/oauth-flow.spec.ts`
- [x] T008 [US1] Write test: OAuth callback with provider denial shows friendly error in `frontend/tests/auth/oauth-flow.spec.ts`
- [x] T009 [US1] Write test: OAuth callback with stale/replayed state is rejected in `frontend/tests/auth/oauth-flow.spec.ts`
- [x] T010 [US1] Write test: GitHub OAuth flow works with same pattern as Google in `frontend/tests/auth/oauth-flow.spec.ts`

**Checkpoint**: OAuth E2E flow verified. `npx playwright test frontend/tests/auth/oauth-flow.spec.ts` passes.

---

## Phase 4: User Story 2 — Magic Link Authentication (Priority: P1)

**Goal**: Verify complete magic link flow using DynamoDB token extraction.

**Independent Test**: `npx playwright test frontend/tests/auth/magic-link.spec.ts`

- [x] T011 [US2] Write test: requesting magic link shows confirmation message in `frontend/tests/auth/magic-link.spec.ts`
- [x] T012 [US2] Write test: navigating to verification URL with valid token authenticates user in `frontend/tests/auth/magic-link.spec.ts` (uses `dynamo-helper.ts` to extract token)
- [x] T013 [US2] Write test: reusing a consumed magic link token shows "already used" error in `frontend/tests/auth/magic-link.spec.ts`
- [x] T014 [US2] Write test: expired magic link token (>1 hour) shows "expired" error in `frontend/tests/auth/magic-link.spec.ts`

**Checkpoint**: Magic link E2E flow verified. `npx playwright test frontend/tests/auth/magic-link.spec.ts` passes.

---

## Phase 5: User Story 3 — Alert Management CRUD (Priority: P2)

**Goal**: Verify complete alert lifecycle through the browser UI.

**Independent Test**: `npx playwright test frontend/tests/alerts/crud.spec.ts`

- [x] T015 [P] [US3] Write test: create alert for AAPL with price threshold, verify it appears in list in `frontend/tests/alerts/crud.spec.ts`
- [x] T016 [P] [US3] Write test: update alert threshold, verify list reflects new value in `frontend/tests/alerts/crud.spec.ts`
- [x] T017 [P] [US3] Write test: delete alert, verify it disappears from list in `frontend/tests/alerts/crud.spec.ts`
- [x] T018 [US3] Write test: creating alert beyond quota limit shows quota exceeded message in `frontend/tests/alerts/crud.spec.ts`

**Checkpoint**: Alert CRUD verified. `npx playwright test frontend/tests/alerts/crud.spec.ts` passes.

---

## Phase 6: User Story 4 — Session Lifecycle (Priority: P2)

**Goal**: Verify token refresh, sign-out, session eviction, and expired session handling.

**Independent Test**: `npx playwright test frontend/tests/session/lifecycle.spec.ts`

- [x] T019 [US4] Write test: authenticated user clicks Sign Out, session invalidated, redirected to login in `frontend/tests/session/lifecycle.spec.ts`
- [x] T020 [US4] Write test: expired session returns 401 and prompts re-authentication in `frontend/tests/session/lifecycle.spec.ts`
- [x] T021 [US4] Write test: session eviction when 6th session created (max 5 limit) in `frontend/tests/session/lifecycle.spec.ts`
- [x] T022 [US4] Write test: background token refresh extends session without interruption in `frontend/tests/session/lifecycle.spec.ts`

**Checkpoint**: Session lifecycle verified. `npx playwright test frontend/tests/session/lifecycle.spec.ts` passes.

---

## Phase 7: User Story 5 — Account Linking (Priority: P2)

**Goal**: Verify anonymous-to-authenticated migration and multi-provider linking preserve data.

**Independent Test**: `npx playwright test frontend/tests/account/linking.spec.ts`

- [x] T023 [US5] Write test: anonymous user with saved config authenticates via magic link, data migrates to authenticated account in `frontend/tests/account/linking.spec.ts`
- [x] T024 [US5] Write test: authenticated user links second OAuth provider, can see same data in `frontend/tests/account/linking.spec.ts`
- [x] T025 [US5] Write test: anonymous user authenticates with email that has existing account, accounts merge with no data loss in `frontend/tests/account/linking.spec.ts`

**Checkpoint**: Account linking verified. `npx playwright test frontend/tests/account/linking.spec.ts` passes.

---

## Phase 8: User Story 6 — Cross-Browser Compatibility (Priority: P3)

**Goal**: Existing sanity test suite passes on Firefox and WebKit.

**Independent Test**: `npx playwright test frontend/tests/sanity.spec.ts --project=firefox --project=webkit`

- [x] T026 [US6] Add Firefox desktop project to `frontend/playwright.config.ts`
- [x] T027 [US6] Add WebKit (Desktop Safari) project to `frontend/playwright.config.ts`
- [x] T028 [US6] Run existing sanity.spec.ts against Firefox, fix any browser-specific failures
- [x] T029 [US6] Run existing sanity.spec.ts against WebKit, fix any browser-specific failures
- [x] T030 [US6] Verify test report clearly identifies browser name in failure output

**Checkpoint**: Cross-browser verified. `npx playwright test --project=firefox --project=webkit` passes on sanity suite.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: CI integration, cleanup, documentation

- [x] T031 Verify all new tests produce JUnit XML reports compatible with CI artifact upload (FR-009)
- [x] T032 [P] Run all new tests 10 consecutive times to verify zero flakiness (SC-007)
- [x] T033 [P] Verify test skip rate remains below 15% after enabling new test groups (SC-006)
- [x] T034 Update `CLAUDE.md` Active Technologies section with 1223 entry
- [x] T035 Verify total E2E suite completes within existing CI timeout budget (~10 min)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — creates shared OAuth interception utility
- **User Stories (Phases 3-8)**: All depend on Foundational (Phase 2)
  - US1 + US2 can proceed in parallel (different auth flows, different files)
  - US3 is independent (no auth flow dependency beyond anonymous session)
  - US4 depends on US1 auth helper patterns
  - US5 depends on US1 + US2 patterns
  - US6 is independent (config change + existing tests)
- **Polish (Phase 9)**: Depends on all user stories

### User Story Dependencies

- **US1 (OAuth)**: Independent — foundational for US4, US5
- **US2 (Magic Link)**: Independent — foundational for US5
- **US3 (Alerts)**: Fully independent
- **US4 (Session)**: Uses US1's auth helper
- **US5 (Account Linking)**: Uses US1 + US2 patterns
- **US6 (Cross-Browser)**: Fully independent (config only)

### Parallel Opportunities

- T002 + T003: Different helper files
- US1 + US2: Different test files, different auth flows
- US3 + US6: Fully independent from auth stories
- T015 + T016 + T017: Independent alert operations (same file but independent test methods)
- T031 + T032 + T033: Independent validation checks

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T005)
3. Complete Phase 3: US1 OAuth Flow (T006-T010)
4. **STOP and VALIDATE**: `npx playwright test frontend/tests/auth/oauth-flow.spec.ts`
5. This alone fills the biggest coverage gap (OAuth success flow)

### Incremental Delivery

1. Setup + Foundational → Helpers ready
2. US1 (OAuth) → Biggest gap closed
3. US2 (Magic Link) → Second auth flow covered
4. US3 (Alerts) → CRUD coverage added (can parallel with US1/US2)
5. US4 (Session) → Session management covered
6. US5 (Account Linking) → Complex flow covered
7. US6 (Cross-Browser) → Engine coverage expanded
8. Polish → CI validation

---

## Notes

- All tests use `E2E_{runId}` prefixed data for isolation (data-model.md)
- OAuth tests use `page.route()` interception, not real provider credentials (research.md R1)
- Magic link tests query DynamoDB directly for token (research.md R2, $0 cost)
- Cross-browser runs only the sanity suite (not all new auth tests) to stay within CI budget
- Cold start timeouts: use existing retry patterns from sanity.spec.ts (10-30s waits)
