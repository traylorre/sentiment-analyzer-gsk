# Tasks: Multi-User Session Consistency

**Input**: Design documents from `/specs/014-session-consistency/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: REQUIRED - spec.md mandates full test pyramid (unit + integration + contract + E2E) with 80% coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Backend**: `src/lambdas/` (Python 3.13 + FastAPI)
- **Frontend**: `frontend/src/` (TypeScript 5 + React 18)
- **Tests**: `tests/` (pytest pyramid structure)
- **Infrastructure**: `infrastructure/terraform/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, pytest markers, shared error types

- [x] T001 Add session consistency pytest markers to pytest.ini
- [x] T002 [P] Create session error types in src/lambdas/shared/errors/session_errors.py
- [x] T003 [P] Create hybrid auth middleware in src/lambdas/shared/middleware/auth_middleware.py
- [x] T004 [P] Add entity_type attribute to User model for GSI in src/lambdas/shared/models/user.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Add email GSI to DynamoDB table in infrastructure/terraform/modules/dynamodb/main.tf (already exists as by_email GSI)
- [x] T006 Deploy GSI and wait for ACTIVE status (Terraform apply) (GSI already deployed)
- [ ] T007 Run data migration to add revoked=false and entity_type="USER" to existing users (deferred - backward compatible defaults)
- [x] T008 [P] Add revoked, revoked_at, revoked_reason fields to User model in src/lambdas/shared/models/user.py
- [x] T009 [P] Add merged_to, merged_at fields to User model in src/lambdas/shared/models/user.py
- [x] T010 [P] Add used_at, used_by_ip fields to MagicLinkToken model in src/lambdas/shared/models/magic_link_token.py
- [x] T011 Update router_v2.py to use hybrid auth middleware in src/lambdas/dashboard/router_v2.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Consistent Session Across Tabs (Priority: P1) 🎯 MVP

**Goal**: Users automatically get anonymous session on app load, shared across tabs via localStorage

**Independent Test**: Open dashboard in browser, verify anonymous session created automatically, data loads in chart, second tab uses same session

**FRs**: FR-001, FR-002, FR-003

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US1] Unit test for hybrid header extraction in tests/unit/lambdas/shared/auth/test_session_consistency.py
- [x] T013 [P] [US1] Unit test for X-User-ID header validation in tests/unit/lambdas/shared/auth/test_session_consistency.py
- [x] T014 [P] [US1] Unit test for Bearer token validation in tests/unit/lambdas/shared/auth/test_session_consistency.py
- [x] T015 [P] [US1] Contract test for POST /api/v2/auth/anonymous in tests/contract/test_session_api_v2.py
- [x] T016 [P] [US1] Contract test for GET /api/v2/auth/session in tests/contract/test_session_api_v2.py
- [x] T017 [P] [US1] Frontend vitest for auto-session creation in frontend/tests/unit/stores/auth-store.test.ts
- [x] T018 [P] [US1] Frontend vitest for SessionProvider in frontend/tests/unit/components/providers/session-provider.test.tsx

### Implementation for User Story 1

- [x] T019 [US1] Implement extract_user_id() hybrid header logic in src/lambdas/shared/middleware/auth_middleware.py
- [x] T020 [US1] Update validate_session() to check both header formats and session revocation in src/lambdas/dashboard/auth.py
- [x] T021 [P] [US1] Create useSessionInit hook in frontend/src/hooks/use-session-init.ts
- [x] T022 [P] [US1] Create SessionProvider component in frontend/src/components/providers/session-provider.tsx
- [x] T023 [US1] Wrap app layout with SessionProvider in frontend/src/app/layout.tsx
- [x] T024 [US1] Update auth-store to sync userId/accessToken with API client in frontend/src/stores/auth-store.ts
- [x] T025 [US1] Update API client to support both header formats in frontend/src/lib/api/client.ts

**Checkpoint**: User Story 1 complete - anonymous session auto-created, shared across tabs

---

## Phase 4: User Story 2 - Concurrent Magic Link Verification Safe (Priority: P1)

**Goal**: Magic link tokens can only be used exactly once, even under concurrent verification attempts

**Independent Test**: Fire 10 concurrent verification requests for same token, verify exactly 1 success and 9 failures

**FRs**: FR-004, FR-005, FR-006

### Tests for User Story 2

- [x] T026 [P] [US2] Unit test for atomic token verification in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py
- [x] T027 [P] [US2] Unit test for token already used error in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py
- [x] T028 [P] [US2] Unit test for token expired error in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py
- [x] T029 [P] [US2] Integration test for 10 concurrent verifications in tests/integration/test_session_race_conditions.py
- [x] T030 [P] [US2] Contract test for POST /api/v2/auth/magic-link/verify (409 response) in tests/contract/test_session_api_v2.py

### Implementation for User Story 2

- [x] T031 [US2] Implement verify_and_consume_token() with conditional update in src/lambdas/dashboard/auth.py
- [x] T032 [US2] Update verify_magic_link() to use atomic verification in src/lambdas/dashboard/auth.py
- [x] T033 [US2] Add TokenAlreadyUsedError and TokenExpiredError handling in src/lambdas/dashboard/auth.py
- [x] T034 [US2] Update magic link verification endpoint to return 409 on race in src/lambdas/dashboard/router_v2.py

**Checkpoint**: User Story 2 complete - magic link tokens atomically verified, race conditions prevented

---

## Phase 5: User Story 3 - Email Uniqueness Guaranteed (Priority: P1)

**Goal**: Each email maps to exactly one user account, enforced by database constraint

**Independent Test**: Fire 10 concurrent OAuth logins for same email, verify exactly 1 account created

**FRs**: FR-007, FR-008, FR-009

### Tests for User Story 3

- [x] T035 [P] [US3] Unit test for email GSI lookup in tests/unit/lambdas/shared/auth/test_email_uniqueness.py
- [x] T036 [P] [US3] Unit test for conditional write rejection in tests/unit/lambdas/shared/auth/test_email_uniqueness.py
- [x] T037 [P] [US3] Unit test for existing email returns user in tests/unit/lambdas/shared/auth/test_email_uniqueness.py
- [x] T038 [P] [US3] Integration test for 10 concurrent user creations in tests/integration/test_session_race_conditions.py
- [x] T039 [P] [US3] Contract test for GET /api/v2/users/lookup in tests/contract/test_session_api_v2.py

### Implementation for User Story 3

- [x] T040 [US3] Implement get_user_by_email_gsi() using GSI query in src/lambdas/dashboard/auth.py
- [x] T041 [US3] Implement create_user_with_email() with conditional write in src/lambdas/dashboard/auth.py
- [x] T042 [US3] Implement get_or_create_user_by_email() for atomic get-or-create in src/lambdas/dashboard/auth.py
- [x] T043 [US3] Add EmailAlreadyExistsError import to router_v2.py
- [x] T044 [US3] Add /api/v2/users/lookup endpoint in src/lambdas/dashboard/router_v2.py

**Checkpoint**: User Story 3 complete - email uniqueness enforced, GSI enables fast lookup

---

## Phase 6: User Story 4 - Session Refresh Keeps User Logged In (Priority: P2)

**Goal**: Sessions refresh on activity (sliding window), frontend syncs with backend, server-side revocation works

**Independent Test**: Make requests over simulated multi-day period, verify session extended. Trigger andon cord, verify revocation.

**FRs**: FR-010, FR-011, FR-012, FR-016, FR-017

### Tests for User Story 4

- [x] T045 [P] [US4] Unit test for session expiry extension in tests/unit/lambdas/shared/auth/test_session_lifecycle.py
- [x] T046 [P] [US4] Unit test for session revocation check in tests/unit/lambdas/shared/auth/test_session_revocation.py
- [x] T047 [P] [US4] Unit test for bulk session revocation in tests/unit/lambdas/shared/auth/test_session_revocation.py
- [x] T048 [P] [US4] Contract test for POST /api/v2/auth/session/refresh in tests/contract/test_session_api_v2.py
- [x] T049 [P] [US4] Contract test for GET /api/v2/auth/session (403 revoked) in tests/contract/test_session_api_v2.py
- [ ] T050 [P] [US4] Frontend vitest for session sync in frontend/src/stores/__tests__/auth-store.test.ts (deferred: frontend)

### Implementation for User Story 4

- [x] T051 [US4] Implement extend_session_expiry() in src/lambdas/dashboard/auth.py
- [x] T052 [US4] Add session expiry extension to validate_session() in src/lambdas/dashboard/auth.py
- [x] T053 [US4] Implement revoke_user_session() in src/lambdas/dashboard/auth.py
- [x] T054 [US4] Implement revoke_sessions_bulk() for andon cord in src/lambdas/dashboard/auth.py
- [x] T055 [US4] Add revocation check to validate_session() in src/lambdas/dashboard/auth.py
- [x] T056 [US4] Add POST /api/v2/auth/session/refresh endpoint in src/lambdas/dashboard/router_v2.py
- [x] T057 [US4] Add POST /api/v2/admin/sessions/revoke endpoint in src/lambdas/dashboard/router_v2.py
- [ ] T058 [US4] Update auth-store to call session refresh periodically in frontend/src/stores/auth-store.ts (deferred: frontend)
- [ ] T059 [US4] Handle 403 (revoked) response in frontend API client in frontend/src/lib/api/client.ts (deferred: frontend)

**Checkpoint**: User Story 4 complete - sessions refresh, revocation works, frontend syncs

---

## Phase 7: User Story 5 - Account Merge Atomic and Idempotent (Priority: P2)

**Goal**: Anonymous data merges to authenticated account without loss or duplication, idempotent on retry

**Independent Test**: Create anonymous session with 3 configs, authenticate, verify all 3 transferred. Retry merge, verify no duplicates.

**FRs**: FR-013, FR-014, FR-015

### Tests for User Story 5

- [x] T060 [P] [US5] Unit test for tombstone marking in tests/unit/lambdas/shared/auth/test_merge_idempotency.py
- [x] T061 [P] [US5] Unit test for idempotent retry in tests/unit/lambdas/shared/auth/test_merge_idempotency.py
- [x] T062 [P] [US5] Unit test for concurrent merge safety in tests/unit/lambdas/shared/auth/test_merge_idempotency.py
- [ ] T063 [P] [US5] Integration test for partial failure recovery in tests/integration/test_session_race_conditions.py (deferred: E2E)
- [x] T064 [P] [US5] Contract test for POST /api/v2/auth/merge in tests/contract/test_session_api_v2.py

### Implementation for User Story 5

- [x] T065 [US5] Add merged_to, merged_at fields to Configuration model in src/lambdas/shared/models/configuration.py (via DynamoDB item)
- [x] T066 [US5] Implement mark_item_as_merged() tombstone function in src/lambdas/shared/auth/merge.py (_transfer_items_with_tombstone)
- [x] T067 [US5] Update merge_anonymous_to_authenticated() with tombstone pattern in src/lambdas/shared/auth/merge.py
- [x] T068 [US5] Add skip logic for already-merged items in src/lambdas/shared/auth/merge.py
- [x] T069 [US5] Add POST /api/v2/auth/merge endpoint in src/lambdas/dashboard/router_v2.py
- [ ] T070 [US5] Update frontend to call merge after magic link verification in frontend/src/stores/auth-store.ts (deferred: frontend)

**Checkpoint**: User Story 5 complete - merges are atomic, idempotent, and auditable

---

## Phase 8: User Story 6 - Email Lookup Fast and Consistent (Priority: P3)

**Goal**: Email lookups use GSI for O(1) performance, return consistent results under concurrent load

**Independent Test**: Query same email 100 times, verify all complete <100ms and return consistent results

**FRs**: FR-009 (shared with US3)

### Tests for User Story 6

- [ ] T071 [P] [US6] Unit test for GSI query performance in tests/unit/lambdas/shared/auth/test_email_uniqueness.py
- [ ] T072 [P] [US6] E2E test for email lookup latency in tests/e2e/test_session_consistency_preprod.py
- [ ] T073 [P] [US6] E2E test for concurrent email lookups in tests/e2e/test_session_consistency_preprod.py

### Implementation for User Story 6

- [ ] T074 [US6] Optimize get_user_by_email() to use KEYS_ONLY projection in src/lambdas/dashboard/auth.py
- [ ] T075 [US6] Add caching layer for repeated email lookups in src/lambdas/dashboard/auth.py
- [ ] T076 [US6] Add X-Ray subsegment for email lookup timing in src/lambdas/dashboard/auth.py

**Checkpoint**: User Story 6 complete - email lookups are fast (<100ms) and consistent

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: E2E validation, documentation, final cleanup

- [ ] T077 [P] E2E test for full auth flow in tests/e2e/test_session_consistency_preprod.py
- [ ] T078 [P] E2E test for anonymous session creation in tests/e2e/test_session_consistency_preprod.py
- [ ] T079 [P] E2E test for magic link race condition (10 concurrent) in tests/e2e/test_session_consistency_preprod.py
- [ ] T080 [P] E2E test for email uniqueness race condition (10 concurrent) in tests/e2e/test_session_consistency_preprod.py
- [ ] T081 [P] E2E test for merge idempotency in tests/e2e/test_session_consistency_preprod.py
- [ ] T082 Run coverage report and verify 80%+ coverage
- [ ] T083 Update API documentation with new endpoints
- [ ] T084 Run quickstart.md validation checklist
- [ ] T085 Performance test: 100 concurrent auth requests
- [ ] T086 Security review: verify no race condition vulnerabilities remain

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup
    ↓
Phase 2: Foundational (BLOCKS all user stories)
    ↓
    ├── Phase 3: US1 (P1) 🎯 MVP
    ├── Phase 4: US2 (P1)
    ├── Phase 5: US3 (P1)
    ├── Phase 6: US4 (P2)
    ├── Phase 7: US5 (P2)
    └── Phase 8: US6 (P3)
            ↓
      Phase 9: Polish
```

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|------------|-----------------|
| US1 (P1) | Foundational only | Phase 2 complete |
| US2 (P1) | Foundational only | Phase 2 complete |
| US3 (P1) | Foundational only (GSI) | Phase 2 complete |
| US4 (P2) | US1 (session validation) | US1 complete |
| US5 (P2) | US1, US2 (auth flows) | US1, US2 complete |
| US6 (P3) | US3 (GSI) | US3 complete |

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Unit tests → Integration tests → Contract tests
3. Models/utilities before services
4. Backend before frontend
5. Core implementation before endpoint wiring

### Parallel Opportunities

**Phase 1 (all parallelizable)**:
- T002, T003, T004 can run simultaneously

**Phase 2 (partial parallel)**:
- T008, T009, T010 can run simultaneously after T005-T007

**User Stories (can be parallelized across team)**:
- US1, US2, US3 can all start after Phase 2
- US4 depends on US1
- US5 depends on US1, US2
- US6 depends on US3

**Within US1**:
- T012-T018 (tests) can all run in parallel
- T021, T022 (frontend) can run in parallel
- T019, T020 must be sequential (backend logic)

---

## Parallel Example: User Story 2

```bash
# Launch all tests for US2 together:
Task: "Unit test for atomic token verification in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py"
Task: "Unit test for token already used error in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py"
Task: "Unit test for token expired error in tests/unit/lambdas/shared/auth/test_atomic_token_verification.py"
Task: "Integration test for 10 concurrent verifications in tests/integration/test_session_race_conditions.py"
Task: "Contract test for POST /api/v2/auth/magic-link/verify in tests/contract/test_session_api_v2.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T011) - **CRITICAL**
3. Complete Phase 3: User Story 1 (T012-T025)
4. **STOP and VALIDATE**: Test anonymous session in browser
5. Deploy to preprod and verify "No sentiment data" bug is fixed

### Incremental Delivery

| Increment | Stories | Value Delivered |
|-----------|---------|-----------------|
| MVP | US1 | Dashboard works, sessions auto-created |
| Security | US1 + US2 + US3 | Race conditions fixed, no duplicates |
| Polish | + US4 | Sessions refresh, revocation works |
| Complete | + US5 + US6 | Merge works, performance optimized |

### Parallel Team Strategy

With 3 developers after Phase 2:
- **Dev A**: US1 (MVP) → US4 (depends on US1)
- **Dev B**: US2 → US5 (depends on US2)
- **Dev C**: US3 → US6 (depends on US3)

---

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 86 |
| **Setup Tasks** | 4 |
| **Foundational Tasks** | 7 |
| **US1 Tasks** | 14 (7 tests + 7 impl) |
| **US2 Tasks** | 9 (5 tests + 4 impl) |
| **US3 Tasks** | 10 (5 tests + 5 impl) |
| **US4 Tasks** | 15 (6 tests + 9 impl) |
| **US5 Tasks** | 11 (5 tests + 6 impl) |
| **US6 Tasks** | 6 (3 tests + 3 impl) |
| **Polish Tasks** | 10 |
| **Parallel Opportunities** | 52 tasks marked [P] |
| **MVP Scope** | US1 (14 tasks after foundational) |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- 80% coverage required before merge to main
