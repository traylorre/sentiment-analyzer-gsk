# Tasks: Auth Security Hardening (1222)

**Input**: Design documents from `/specs/1222-auth-security-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included — this is a security hardening feature where test coverage is essential (SC-007).

**Organization**: Tasks grouped by vulnerability class (mapped to user stories US1-US4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1=Provider Uniqueness, US2=Merge Auth, US3=Verification State, US4=PKCE

---

## Phase 1: Setup

**Purpose**: Audit existing data and prepare test infrastructure

- [x] T001 Run `scripts/audit_duplicate_provider_subs.py` to scan existing users table for duplicate `provider_sub` entries (FR-012)
- [x] T002 [P] Create test file `tests/unit/auth/test_provider_uniqueness.py` with test class skeleton
- [x] T003 [P] Create test file `tests/unit/auth/test_account_link_auth.py` with test class skeleton
- [x] T004 [P] Create test file `tests/unit/auth/test_verification_state.py` with test class skeleton
- [x] T005 [P] Create test file `tests/unit/auth/test_pkce.py` with test class skeleton

---

## Phase 2: Foundational

**Purpose**: Create the audit script that serves all user stories

- [x] T006 Create `scripts/audit_duplicate_provider_subs.py` — scan `by_provider_sub` GSI for duplicate composite keys, output report of affected user IDs (FR-012)

**Checkpoint**: Audit script ready. Existing data risk assessed before code changes begin.

---

## Phase 3: User Story 1 — Prevent Provider Identity Theft (Priority: P1) 🎯 MVP

**Goal**: No two user accounts can share the same `provider_sub` value. Reject duplicate linking attempts.

**Independent Test**: Create User B linked to `google:12345`, then attempt linking User A to same sub — must be rejected.

### Tests for User Story 1

- [x] T007 [P] [US1] Write test: successful provider linking for unlinked sub in `tests/unit/auth/test_provider_uniqueness.py`
- [x] T008 [P] [US1] Write test: reject linking when provider_sub already owned by different user in `tests/unit/auth/test_provider_uniqueness.py`
- [x] T009 [P] [US1] Write test: allow idempotent re-link by same user in `tests/unit/auth/test_provider_uniqueness.py`
- [x] T010 [P] [US1] Write test: race condition — concurrent link attempts for same sub (simulate via mocked GSI responses) in `tests/unit/auth/test_provider_uniqueness.py`
- [x] T011 [P] [US1] Write test: generic error message returned (no leakage of which user owns the sub) in `tests/unit/auth/test_provider_uniqueness.py`

### Implementation for User Story 1

- [x] T012 [US1] Add `get_user_by_provider_sub()` pre-check call before update in `_link_provider()` at `src/lambdas/dashboard/auth.py:2362`
- [x] T013 [US1] Return error if pre-check finds a different user owning the provider_sub in `src/lambdas/dashboard/auth.py`
- [x] T014 [US1] Allow idempotent re-link if pre-check finds same user in `src/lambdas/dashboard/auth.py`
- [x] T015 [US1] Add structured audit log for linking success and rejection with correlation ID in `src/lambdas/dashboard/auth.py` (FR-011)
- [x] T016 [US1] Verify all 5 tests pass (T007-T011)

**Checkpoint**: Provider identity theft blocked. Run `pytest tests/unit/auth/test_provider_uniqueness.py` — all pass.

---

## Phase 4: User Story 2 — Prevent Unauthorized Account Merging (Priority: P1)

**Goal**: Account merge endpoint verifies the authenticated caller owns the source account.

**Independent Test**: Authenticate as User A, call `link_accounts` targeting User B's account — must return 403.

### Tests for User Story 2

- [x] T017 [P] [US2] Write test: valid merge (authenticated user owns source account) in `tests/unit/auth/test_account_link_auth.py`
- [x] T018 [P] [US2] Write test: 403 when authenticated user doesn't own source account in `tests/unit/auth/test_account_link_auth.py`
- [x] T019 [P] [US2] Write test: 401 when unauthenticated in `tests/unit/auth/test_account_link_auth.py`
- [x] T020 [P] [US2] Write test: valid anonymous-to-authenticated merge (user owns both) in `tests/unit/auth/test_account_link_auth.py`

### Implementation for User Story 2

- [x] T021 [US2] Add JWT `sub` comparison check at entry of `link_accounts()` in `src/lambdas/dashboard/auth.py:2828`
- [x] T022 [US2] Return 403 Forbidden with generic error on mismatch in `src/lambdas/dashboard/auth.py`
- [x] T023 [US2] Add structured audit log for merge attempt (success/rejection) in `src/lambdas/dashboard/auth.py` (FR-011)
- [x] T024 [US2] Verify all 4 tests pass (T017-T020)

**Checkpoint**: Unauthorized account merging blocked. Run `pytest tests/unit/auth/test_account_link_auth.py` — all pass.

---

## Phase 5: User Story 3 — Enforce Email Verification State Machine (Priority: P2)

**Goal**: The `verification` field can only transition through valid states at the data layer, not just the application model layer.

**Independent Test**: Attempt a direct DynamoDB update setting `verification=verified` on an anonymous user without valid token — conditional write must fail.

### Tests for User Story 3

- [x] T025 [P] [US3] Write test: valid magic link verification sets `verified` via conditional write in `tests/unit/auth/test_verification_state.py`
- [x] T026 [P] [US3] Write test: conditional write rejects direct `verified` without token flow in `tests/unit/auth/test_verification_state.py`
- [x] T027 [P] [US3] Write test: conditional write prevents downgrade from `verified` to `none` in `tests/unit/auth/test_verification_state.py`
- [x] T028 [P] [US3] Write test: idempotent re-verification of already-verified user succeeds in `tests/unit/auth/test_verification_state.py`

### Implementation for User Story 3

- [x] T029 [US3] Add ConditionExpression to `_mark_email_verified()` in `src/lambdas/dashboard/auth.py:2618` — guard `verification` field transitions
- [x] T030 [US3] Add ConditionExpression to `complete_email_link()` in `src/lambdas/dashboard/auth.py:3120` — guard `verification` field + validate `pending_email`
- [x] T031 [US3] Handle `ConditionalCheckFailedException` gracefully (log + return appropriate error) in `src/lambdas/dashboard/auth.py`
- [x] T032 [US3] Verify all 4 tests pass (T025-T028)

**Checkpoint**: Verification state machine enforced at data layer. Run `pytest tests/unit/auth/test_verification_state.py` — all pass.

---

## Phase 6: User Story 4 — Add PKCE to OAuth Flow (Priority: P2)

**Goal**: All OAuth authorization URLs include PKCE `code_challenge` and all token exchanges include `code_verifier`.

**Independent Test**: Initiate OAuth flow, verify URL contains `code_challenge` and `code_challenge_method=S256`, verify token exchange includes `code_verifier`.

### Tests for User Story 4

- [x] T033 [P] [US4] Write test: `get_authorize_url()` includes `code_challenge` and `code_challenge_method=S256` in `tests/unit/auth/test_pkce.py`
- [x] T034 [P] [US4] Write test: `store_oauth_state()` stores `code_verifier` field in `tests/unit/auth/test_pkce.py`
- [x] T035 [P] [US4] Write test: `validate_oauth_state()` returns `code_verifier` in validated state in `tests/unit/auth/test_pkce.py`
- [x] T036 [P] [US4] Write test: `exchange_code_for_tokens()` includes `code_verifier` in POST body in `tests/unit/auth/test_pkce.py`
- [x] T037 [P] [US4] Write test: backward compat — OAuth state without `code_verifier` (transition period) still works in `tests/unit/auth/test_pkce.py`

### Implementation for User Story 4

- [x] T038 [US4] Add `code_verifier` field to `OAuthState` dataclass in `src/lambdas/shared/auth/oauth_state.py:27`
- [x] T039 [US4] Generate `code_verifier` (43-128 chars, URL-safe base64) in `store_oauth_state()` in `src/lambdas/shared/auth/oauth_state.py:57`
- [x] T040 [US4] Store `code_verifier` in DynamoDB alongside existing state fields in `src/lambdas/shared/auth/oauth_state.py`
- [x] T041 [US4] Return `code_verifier` from `validate_oauth_state()` in `src/lambdas/shared/auth/oauth_state.py:146`
- [x] T042 [US4] Add `code_challenge` parameter to `get_authorize_url()` in `src/lambdas/shared/auth/cognito.py:82`
- [x] T043 [US4] Derive `code_challenge` from `code_verifier` using SHA-256 + base64url in `src/lambdas/shared/auth/cognito.py`
- [x] T044 [US4] Add `code_verifier` parameter to `exchange_code_for_tokens()` in `src/lambdas/shared/auth/cognito.py:115`
- [x] T045 [US4] Pass `code_verifier` through `handle_oauth_callback()` → `exchange_code_for_tokens()` in `src/lambdas/dashboard/auth.py`
- [x] T046 [US4] Pass `code_challenge` through `get_oauth_urls()` → `get_authorize_url()` in `src/lambdas/dashboard/auth.py:1985`
- [x] T047 [US4] Verify all 5 tests pass (T033-T037)

**Checkpoint**: PKCE fully integrated. Run `pytest tests/unit/auth/test_pkce.py` — all pass.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify full suite, audit logging, and documentation

- [x] T048 Run full unit test suite (`pytest tests/unit/`) — verify zero regressions (SC-006)
- [x] T049 [P] Verify audit logs emit for all 4 vulnerability classes with correlation IDs (FR-011, SC-005)
- [x] T050 [P] Verify error messages are generic and consistent across all rejection paths (FR-010)
- [x] T051 Run `scripts/audit_duplicate_provider_subs.py` against preprod to document existing state
- [x] T052 Update CLAUDE.md Active Technologies section with 1222 entry

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — creates audit script
- **User Stories (Phases 3-6)**: All depend on Foundational completion
  - US1 and US2 are P1 and can proceed in parallel
  - US3 and US4 are P2 and can proceed in parallel after P1
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (Provider Uniqueness)**: Independent — modifies `_link_provider()` only
- **US2 (Merge Auth)**: Independent — modifies `link_accounts()` only
- **US3 (Verification State)**: Independent — modifies `_mark_email_verified()` and `complete_email_link()` only
- **US4 (PKCE)**: Independent — modifies `cognito.py`, `oauth_state.py`, and `handle_oauth_callback()`

No cross-story dependencies. All 4 stories touch different functions in `auth.py`.

### Parallel Opportunities

Within each story, all test tasks (marked [P]) can run in parallel since they write to the same test file but define independent test methods.

Across stories:
- US1 + US2 can execute in parallel (different functions in auth.py)
- US3 + US4 can execute in parallel (different files)
- With 2 workers: {US1, US2} then {US3, US4}

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006)
3. Complete Phase 3: US1 Provider Uniqueness (T007-T016)
4. **STOP and VALIDATE**: `pytest tests/unit/auth/test_provider_uniqueness.py` — all pass
5. This alone closes the most critical vulnerability (account takeover)

### Incremental Delivery

1. Setup + Foundational → Audit complete
2. US1 (Provider Uniqueness) → Test → Most critical vulnerability closed
3. US2 (Merge Auth) → Test → Second critical vulnerability closed
4. US3 (Verification State) → Test → Privilege escalation blocked
5. US4 (PKCE) → Test → Code interception blocked
6. Polish → Full regression + audit

---

## Notes

- All test tasks create moto-mocked DynamoDB tables (per constitution: unit tests mock all AWS)
- `auth.py` is a large file (~3000 lines) — changes target specific functions by line number
- PKCE code_verifier generation uses `secrets.token_urlsafe(32)` (43 chars, RFC 7636 compliant)
- Backward compatibility: existing OAuth states without `code_verifier` are handled gracefully (T037)
