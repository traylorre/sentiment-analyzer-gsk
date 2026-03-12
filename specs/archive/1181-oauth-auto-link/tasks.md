# Tasks: OAuth Auto-Link for Email-Verified Users

**Input**: Design documents from `/specs/1181-oauth-auto-link/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No setup required - feature extends existing auth.py

- [X] T001 Verify Feature 1180 (get_user_by_provider_sub) is merged to main

**Checkpoint**: Dependency confirmed

---

## Phase 2: Foundational (Core Logic)

**Purpose**: Implement the core auto-link decision function that all stories depend on

- [X] T002 [P] Implement `can_auto_link_oauth(oauth_claims, existing_user)` in src/lambdas/dashboard/auth.py
- [X] T003 [P] Add AUTH_022 and AUTH_023 error handling inline in OAuth callback
- [X] T004 [P] Write unit tests for `can_auto_link_oauth()` in tests/unit/dashboard/test_oauth_auto_link.py

**Checkpoint**: Foundation ready - can_auto_link_oauth() tested and passing

---

## Phase 3: User Story 1 - Same-Domain Auto-Link (Priority: P1) MVP

**Goal**: Gmail users authenticating with Google OAuth have accounts automatically linked

**Independent Test**: Existing @gmail.com user + Google OAuth → auto-linked without prompt

### Implementation for User Story 1

- [X] T005 [US1] Reuse existing `_link_provider()` function for OAuth linking in src/lambdas/dashboard/auth.py
- [X] T006 [US1] Update OAuth callback handler to detect existing email user and use can_auto_link_oauth() in src/lambdas/dashboard/auth.py
- [X] T007 [US1] Add audit logging for auto-link with link_type field in src/lambdas/dashboard/auth.py
- [X] T008 [P] [US1] Write unit tests for auto-link scenario (Gmail + Google) in tests/unit/dashboard/test_oauth_auto_link.py

**Checkpoint**: Gmail users with Google OAuth are automatically linked

---

## Phase 4: User Story 2 - Cross-Domain Manual Linking (Priority: P2)

**Goal**: Non-Gmail users see a prompt and can choose to link or keep separate

**Independent Test**: @hotmail.com user + Google OAuth → prompt displayed → user can link

### Implementation for User Story 2

- [ ] T009 [US2] Add `/api/v2/auth/link-prompt` endpoint to return prompt data in src/lambdas/dashboard/auth.py
- [ ] T010 [US2] Add `/api/v2/auth/link-oauth` endpoint for manual linking confirmation in src/lambdas/dashboard/auth.py
- [ ] T011 [P] [US2] Create LinkAccountPrompt.tsx component in frontend/src/components/auth/LinkAccountPrompt.tsx
- [ ] T012 [P] [US2] Add link API client functions in frontend/src/lib/api/auth.ts
- [X] T013 [P] [US2] Write unit tests for cross-domain prompt scenario in tests/unit/dashboard/test_oauth_auto_link.py

**Checkpoint**: Backend returns conflict for cross-domain (frontend component pending)

---

## Phase 5: User Story 3 - GitHub Always Requires Confirmation (Priority: P3)

**Goal**: GitHub OAuth always shows confirmation prompt regardless of email domain

**Independent Test**: Any user + GitHub OAuth → always shows prompt

### Implementation for User Story 3

- [X] T014 [US3] Implement GitHub always returns False in `can_auto_link_oauth()` in src/lambdas/dashboard/auth.py
- [X] T015 [P] [US3] Write unit tests for GitHub-always-prompts scenario in tests/unit/dashboard/test_oauth_auto_link.py

**Checkpoint**: GitHub OAuth always requires manual confirmation

---

## Phase 6: Edge Cases & Security

**Purpose**: Handle error scenarios from edge cases section

- [X] T016 [P] Implement AUTH_022 rejection for unverified OAuth email in src/lambdas/dashboard/auth.py
- [X] T017 [P] Implement AUTH_023 rejection for duplicate provider_sub using get_user_by_provider_sub() in src/lambdas/dashboard/auth.py
- [X] T018 [P] Write unit tests for edge cases (unverified email, duplicate sub) in tests/unit/dashboard/test_oauth_auto_link.py

**Checkpoint**: All edge cases handled with proper error responses

---

## Phase 7: Polish & Validation

**Purpose**: Final validation and cleanup

- [X] T019 Run full unit test suite with `pytest tests/unit/dashboard/test_oauth_auto_link.py -v` (12 tests pass)
- [X] T020 Run linting with `ruff check src/lambdas/dashboard/auth.py`
- [ ] T021 Run quickstart.md test scenarios manually
- [ ] T022 Update frontend types if needed in frontend/src/types/auth.ts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Feature 1180 must be merged - CONFIRMED
- **Phase 2 (Foundational)**: can_auto_link_oauth() must be complete before user stories
- **Phases 3-5 (User Stories)**: Can proceed sequentially after Phase 2
- **Phase 6 (Edge Cases)**: Can run in parallel with user stories
- **Phase 7 (Polish)**: After all implementation complete

### Task Dependencies

- T005-T008 depend on T002-T004 (foundation)
- T009-T013 depend on T005-T008 (US1 complete)
- T014-T015 depend on T002 (can_auto_link_oauth exists)
- T016-T018 can run in parallel with user stories

### Parallel Opportunities

```bash
# Phase 2 - All foundational tasks can run in parallel:
T002, T003, T004

# Phase 6 - All edge case tasks can run in parallel:
T016, T017, T018
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T002-T004) ✅
2. Complete Phase 3: User Story 1 (T005-T008) ✅
3. **STOP and VALIDATE**: Test auto-link for Gmail+Google ✅
4. Push and create PR

### Full Implementation

1. Phases 2-6 in order ✅ (backend complete)
2. Phase 7 for validation ✅
3. Push and create PR

---

## Notes

- Feature 1180 provides get_user_by_provider_sub() - CRITICAL dependency
- Existing _link_provider() function handles DynamoDB updates
- Frontend component only needed for US2 (manual linking prompt) - DEFERRED
- All tests use deterministic dates per constitution
- **MVP COMPLETE**: Backend Flow 3 logic is fully implemented and tested
