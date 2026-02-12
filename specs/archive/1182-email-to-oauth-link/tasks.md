# Tasks: Email-to-OAuth Link (Flow 4)

**Input**: Design documents from `/specs/1182-email-to-oauth-link/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (No Setup Required)

**Purpose**: This feature adds to existing infrastructure - no setup needed

- [x] T001 Existing auth.py infrastructure is ready
- [x] T002 Existing User model has federation fields (pending_email, linked_providers)
- [x] T003 Existing magic link infrastructure available

---

## Phase 2: User Story 1 - OAuth User Initiates Email Linking (Priority: P1) 🎯 MVP

**Goal**: OAuth user can initiate email linking and receive magic link

**Independent Test**: OAuth user clicks "Add Email", enters email, magic link is sent

### Tests for User Story 1

- [x] T010 [P] [US1] Unit test: link initiation success in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T011 [P] [US1] Unit test: reject if email already linked in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T012 [P] [US1] Unit test: pending_email set correctly in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T013 [P] [US1] Unit test: magic link generated with user_id claim in tests/unit/dashboard/test_email_to_oauth_link.py

### Implementation for User Story 1

- [x] T014 [US1] Implement link_email_to_oauth_user() function in src/lambdas/dashboard/auth.py
- [x] T015 [US1] Token generation includes user_id claim (inline in link_email_to_oauth_user)
- [x] T016 [US1] Add LinkEmailRequest pydantic model in src/lambdas/dashboard/auth.py
- [x] T017 [US1] Add LinkEmailResponse pydantic model in src/lambdas/dashboard/auth.py

**Checkpoint**: OAuth user can initiate email linking and receive magic link ✅

---

## Phase 3: User Story 2 - User Completes Email Verification (Priority: P1)

**Goal**: User clicking magic link successfully adds email to linked_providers

**Independent Test**: Click valid magic link, email appears in linked_providers

### Tests for User Story 2

- [x] T020 [P] [US2] Unit test: complete link success in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T021 [P] [US2] Unit test: linked_providers updated in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T022 [P] [US2] Unit test: provider_metadata created in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T023 [P] [US2] Unit test: pending_email cleared in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T024 [P] [US2] Unit test: AUTH_METHOD_LINKED event logged in tests/unit/dashboard/test_email_to_oauth_link.py

### Implementation for User Story 2

- [x] T025 [US2] Implement complete_email_link() function in src/lambdas/dashboard/auth.py
- [x] T026 [US2] Add user_id validation in complete_email_link() token verification
- [x] T027 [US2] Add CompleteEmailLinkRequest pydantic model in src/lambdas/dashboard/auth.py
- [ ] T028 [US2] Add /v2/auth/complete-email-link endpoint in router_v2.py (deferred - frontend not ready)

**Checkpoint**: Full email linking flow works end-to-end ✅

---

## Phase 4: User Story 3 - Error Handling for Invalid Links (Priority: P2)

**Goal**: User receives clear error messages for expired/used links

**Independent Test**: Click expired link, see error message with guidance

### Tests for User Story 3

- [x] T030 [P] [US3] Unit test: expired token returns AUTH_010 in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T031 [P] [US3] Unit test: already used token returns AUTH_010 in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T032 [P] [US3] Unit test: wrong user_id token returns AUTH_010 in tests/unit/dashboard/test_email_to_oauth_link.py
- [x] T033 [P] [US3] Unit test: generic error message (no enumeration) in tests/unit/dashboard/test_email_to_oauth_link.py

### Implementation for User Story 3

- [x] T034 [US3] Add error handling to complete_email_link() for all failure cases
- [x] T035 [US3] Atomic token consumption with ConditionExpression prevents race conditions

**Checkpoint**: All error scenarios handled with generic AUTH_010 responses ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: Already complete - existing infrastructure
- **Phase 2 (US1)**: Can start immediately - initiation flow
- **Phase 3 (US2)**: Depends on T015 (magic link with user_id)
- **Phase 4 (US3)**: Depends on T025 (complete_email_link exists)

### Within Each Phase

1. Write tests FIRST (verify they fail)
2. Implement function in auth.py
3. Add endpoint in router_v2.py
4. Add request models
5. Verify tests pass

### Parallel Opportunities

- All tests within a phase marked [P] can run in parallel
- T010-T013 (US1 tests) can all run in parallel
- T020-T024 (US2 tests) can all run in parallel
- T030-T033 (US3 tests) can all run in parallel

---

## Notes

- Tests use freezegun for time-dependent scenarios (token expiry)
- Tests use moto for DynamoDB mocking
- All error responses use generic AUTH_010 to prevent enumeration
- Frontend "Add Email" UI is out of scope (separate feature)
