---
description: "Task list for OAuth Session Persistence (1381)"
---

# Tasks: OAuth Session Persistence

**Input**: Design documents from `specs/1381-oauth-session-persistence/`
**Prerequisites**: plan.md, spec.md (US1–US3, FR-001..FR-011, SR-001..SR-006), research.md (R1–R7), contracts/auth-refresh.md

**Tests**: Unit tests are included for the backend response contract (repo convention: no mocks for E2E; real verification is owner-driven and manual). Preprod verification tasks are explicit and gated on an owner-performed interactive Google login.

**Two-dashboard guard**: All work targets the **Customer Dashboard** (`frontend/` + `src/lambdas/dashboard/`). Do NOT touch `src/dashboard/` (HTMX admin).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (or SETUP/FOUND/POLISH)

---

## Phase 1: Setup

- [ ] T001 [SETUP] Confirm worktree is on the customer-dashboard code paths; open `src/lambdas/dashboard/auth.py`, `src/lambdas/dashboard/router_v2.py`, `frontend/src/stores/auth-store.ts` and re-read the cited line ranges (spec Root-Cause). Activate the Python 3.13 venv (`source .venv/bin/activate`).
- [ ] T002 [SETUP] Capture a baseline: record current `POST /api/v2/auth/refresh` behavior for an OAuth session on preprod (401) and the response body, so the fix is provably a change. (Owner may need to supply a live session for the capture.)

---

## Phase 2: Foundational (Blocking) — Diagnose the live 401 (Defect A discriminator)

**⚠️ CRITICAL**: Phase 0 of the plan. This decides whether Defect A remediation is a Cognito-config action or a cookie-Path correction. Blocks the Phase 2-remediation tasks (T012/T013) but NOT the Defect B fix (US1 core).

- [ ] T003 [FOUND] (FR-007, SR-006) In `src/lambdas/dashboard/router_v2.py` `refresh_tokens()`, add non-secret diagnostic logging that emits exactly one of `refresh.cookie_absent` / `refresh.cognito_rejected` / `refresh.success`, using hash-prefix/masking (`sanitize_for_log`). Distinguish `_extract_refresh_token_from_event` returning `None` (absent) from `result.error` (Cognito reject). No raw tokens (CWE-312).
- [ ] T004 [FOUND] (FR-007) In `src/lambdas/dashboard/auth.py` Cognito branch of `refresh_access_tokens`, surface the mapped Cognito error code (from `TokenError`) into the log context (not the body) so `invalid_grant` vs `invalid_client` vs `network_error` is visible.
- [ ] T005 [FOUND] Unit test in `tests/unit/dashboard/` asserting the three diagnostic branches fire on: (a) event with no cookie, (b) Cognito 4xx (mock httpx via `responses`), (c) success. Assert no token material is logged.
- [ ] T006 [FOUND] Deploy diagnostics to preprod via the normal pipeline; owner performs an interactive Google login + reload; collect CloudWatch logs to classify the live 401 as cookie-absent (→ FR-008 path) or Cognito-reject (→ FR-009 path). **Record the verdict in the PR/spec before remediation.**

**Checkpoint**: The live 401 sub-cause is known and recorded.

---

## Phase 3: User Story 1 — OAuth session survives reload (P1) 🎯 MVP

**Goal**: `/refresh` returns 200 with `user_id` for an OAuth session, and `restoreSession` rebuilds the Google identity instead of dropping to guest.

**Independent Test**: Owner interactive Google login on Amplify → reload → 200 refresh carrying `user_id` → stays signed in as Google user.

### Tests for User Story 1

- [ ] T007 [P] [US1] Unit test in `tests/unit/dashboard/test_auth_refresh.py`: Cognito-branch `refresh_access_tokens` returns a `RefreshTokenResponse` with non-null `user_id` and `auth_type` for a valid OAuth refresh (mock `cognito_refresh_tokens` to return a fresh id-token; mock the user lookup). Covers FR-002/FR-003.
- [ ] T008 [P] [US1] Contract test asserting the `/refresh` 200 body matches `contracts/auth-refresh.md` (has `access_token`, `id_token`, `expires_in`, `user_id`, `auth_type`; does NOT contain `refresh_token`). Covers SR-001.

### Implementation for User Story 1 (Defect B — backend)

- [ ] T009 [US1] (FR-002, FR-003, SR-005) In `src/lambdas/dashboard/auth.py` Cognito branch (`~2934-2939`): after a successful `cognito_refresh_tokens`, `decode_id_token(tokens.id_token)` to get `sub` (+ provider from identity claim), resolve internal `user_id` via `get_user_by_provider_sub(table, provider, sub)` (`auth.py:527`) — reuse it; add a `by_cognito_sub` GSI query helper ONLY if provider is not recoverable. Populate `RefreshTokenResponse(user_id=..., auth_type=...)`. `user_id` MUST come from validated claims/DB, never request input.
- [ ] T010 [US1] (AR#2 #2) Guard the lookup: if `table is None` or the user is not found, do NOT 500 — return the tokens without `user_id` (existing behavior) and log a `refresh.identity_unresolved` diagnostic, so the endpoint degrades to today's behavior rather than regressing.
- [ ] T011 [US1] Run `pytest tests/unit/dashboard/ -v` and `ruff format`/`ruff check`; ensure no SAST (bandit/semgrep) findings on the new logging/lookup.

**Checkpoint**: `/refresh` returns `user_id` for OAuth on a 200 — `restoreSession` can complete without frontend changes.

---

## Phase 4: User Story 1 (cont.) — Remediate Defect A (gated by T006)

**Only one of T012 / T013 applies, per the T006 verdict.**

- [ ] T012 [US1] (FR-009) IF Cognito-reject: correct `COGNITO_CLIENT_ID`/`COGNITO_CLIENT_SECRET` (or app-client) on the dashboard Lambda **via the CI "Step 2.5" env-sync in `.github/workflows/deploy.yml`** (Terraform cannot — Feature 1290 freeze). Verify with `aws lambda get-function-configuration` that the live env matches the Hosted-UI app client that issues OAuth tokens. Do NOT commit secrets; reference the secret store.
- [ ] T013 [US1] (FR-008) IF cookie-absent: correct the deployed refresh-cookie `Path`/scope so it is sent on the real `/refresh` request path (reconcile `_cookie_path_prefix` `router_v2.py:150-163` against the actual browser path — custom domain / base-path mapping vs stage). Add a unit test pinning the computed Path for the deployed topology.

**Checkpoint**: `/refresh` returns 200 for a live OAuth session on preprod.

---

## Phase 5: User Story 2 — Navigation persistence + responsive left-nav (P1)

**Goal**: Restored OAuth identity is consistent across UserMenu/Settings/left-nav; nav stays responsive.

**Independent Test**: With a restored OAuth session, navigate into/out of Settings via the left-nav; identity consistent, no lockup.

- [ ] T014 [US2] (FR-005, FR-006) Verify on the real Amplify frontend (owner session): after reload-restore, navigate `/` ↔ `/settings` via left-nav ≥3 cycles; confirm UserMenu + Settings show the same Google user and every left-nav link stays clickable. Capture screenshots/network trace.
- [ ] T015 [US2] (FR-010) Verify graceful fallback: with a deliberately expired/absent refresh cookie, reload → guest fallback occurs with no unresponsive nav and no console unhandled rejection. If a residual UI-only lockup persists AFTER restore succeeds, file a scoped follow-up (per Clarification Q5) — do not expand this feature.
- [ ] T016 [P] [US2] (Regression) Run the customer Playwright suite (`cd frontend && npx playwright test`) against the Amplify URL for the auth/session specs to confirm no guest-flow regression. (Google consent step remains owner-manual.)

**Checkpoint**: All three reported symptoms clear on the real frontend.

---

## Phase 6: User Story 3 — Security posture preserved (P2)

**Goal**: No regression to CSRF, blocklist, cookie-scope, or token-body hygiene.

- [ ] T017 [P] [US3] (SR-002) Test/verify `require_csrf_middleware` still returns 403 for a non-exempt state-changing route called cross-site without a matching CSRF header/cookie; `/refresh` stays CSRF-exempt and rotates the CSRF cookie on success (`router_v2.py:684`).
- [ ] T018 [P] [US3] (SR-004) Test that a blocklisted refresh token yields 401 `token_revoked` BEFORE any token issuance (`auth.py:2913-2924`) — reload cannot resurrect an evicted session.
- [ ] T019 [P] [US3] (SR-001, SR-003) Assert the refresh token never appears in any `/refresh` body and `SameSite=None` scope is unchanged (no broadening); the added `user_id` is the minimal identity only.
- [ ] T020 [US3] (SR-006) Re-run `make sast` (semgrep) + bandit on `auth.py`/`router_v2.py`; confirm the new logging has no CWE-117/CWE-312 findings.

**Checkpoint**: Security gates green.

---

## Phase 7: Polish & Verification Seal

- [ ] T021 (SC-001..SC-006) Produce a verification record: preprod `/refresh` 200 (was 401), 3× reload persistence, UserMenu/Settings identity match, responsive left-nav, security checks — attach network traces / log excerpts. Real frontend, no mocks.
- [ ] T022 [P] Update `specs/1381-oauth-session-persistence/` with the T006 verdict and the final applied remediation (T012 or T013) for traceability.
- [ ] T023 Run `make validate` + full `pytest tests/unit/ -m "not preprod"`; GPG-sign commits (`git commit -S`). Do NOT push/open PR (pipeline stops at planning; implementation/commit is a separate gated step).

---

## Dependencies & Execution Order

- **Setup (T001–T002)**: first.
- **Foundational / Diagnose (T003–T006)**: blocks Defect A remediation (T012/T013) and the final verification seal. Does NOT block the Defect B code fix (T007–T011), which can proceed in parallel since it's required regardless.
- **US1 (T007–T013)**: T009 is the core; T012/T013 are mutually exclusive and gated on T006.
- **US2 (T014–T016)**: requires US1 fix deployed to preprod.
- **US3 (T017–T020)**: can run in parallel with US2 verification (different concern), but before the seal.
- **Polish (T021–T023)**: last.

### Parallel Opportunities

- T007, T008 (different test files) in parallel.
- T017, T018, T019 (independent security checks) in parallel.
- T016 (Playwright regression) parallel with T014/T015 manual verification.

---

## Requirement → Task Coverage (traceability)

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (200 for OAuth) | T009, T012/T013, T006, T021 |
| FR-002 (user_id in response) | T007, T008, T009 |
| FR-003 (server-derived user_id) | T009 |
| FR-004 (restoreSession takes Cognito branch, no guest fallback) | T009, T014 |
| FR-005 (consistent identity) | T014 |
| FR-006 (responsive left-nav) | T014 |
| FR-007 (diagnostics) | T003, T004, T005 |
| FR-008 (cookie sent cross-site) | T006, T013 |
| FR-009 (env-freeze delivery) | T012 |
| FR-010 (graceful guest fallback) | T015 |
| FR-011 (no new AWS resources) | T012, T013 (reuse existing), plan Constitution Check |
| SR-001 (refresh token never in body) | T008, T019 |
| SR-002 (CSRF intact) | T017 |
| SR-003 (SameSite=None not broadened) | T019 |
| SR-004 (blocklist before issuance) | T018 |
| SR-005 (server-side identity, no spoof) | T009 |
| SR-006 (no secret logging) | T003, T005, T020 |
| SC-001..SC-006 | T021 |

Every FR/SR maps to ≥1 task. Every task traces to a requirement or an explicit setup/verification purpose.

---

## Adversarial Review #3

Final readiness review across spec.md, plan.md, tasks.md, research.md, contracts/.

### Highest-risk task
**T012 — correcting Cognito client/secret on the frozen Lambda env (Feature 1290).** Risk: an implementer applies the change via Terraform (the obvious place), it silently no-ops on the live env, preprod stays 401, and the team concludes "the fix didn't work" and rips out the correct Defect B fix. Mitigation baked in: T012 mandates the CI Step 2.5 path + a `get-function-configuration` verification; FR-009, research R4, and Clarification Q4 all reinforce it. Second-order risk: leaking a secret into git during the correction — T012 forbids committing secrets.

### Most-likely rework
**T009's user_id resolution** — provider may not be directly present on a bare Cognito refresh id-token, so `get_user_by_provider_sub` could miss and the code falls to T010's degrade path, leaving OAuth still un-restored despite a 200. If T006 shows the 401 is purely Cognito-reject, the team could ship T012 alone, verify a 200, and MISS that Defect B still blocks restore. Mitigation: T007/T008 unit-gate `user_id` presence, and the traceability table forces FR-002 (T009) to ship even when FR-001 (T012) is the visible win. AR#2 #3 pre-specified the provider-claim / `by_cognito_sub` GSI fallback so this is a known decision, not a surprise.

### Readiness checks
- Root cause verified against source with file:line (not re-derived from the task's hypothesis; the cookie hypothesis was disproven and the real two-defect chain proven). ✅
- Both defects have tasks; fixing only the visible 401 is explicitly guarded against. ✅
- Security requirements each have a task; no CSRF/blocklist/cookie-scope regression path is unowned. ✅
- Env-freeze operational trap is called out in spec, plan, research, clarifications, and the highest-risk task. ✅
- Verification is real-frontend / owner-interactive, no mocks, per constraints. ✅
- Two deferred owner items (D1 live Cognito config, D2 deployment topology) are runtime-only and are exactly what T006 resolves. ✅

### Gate

**READY FOR IMPLEMENTATION.**

Rationale: the plan is executable by a fresh agent, every requirement is task-covered and traceable, the two most dangerous failure modes (env-freeze no-op, single-defect tunnel vision) are explicitly mitigated, and the only remaining unknowns are runtime facts that the first foundational task (T006) is designed to resolve on preprod. No open CRITICAL/HIGH. Pipeline stops here (no `/speckit.implement`, no push).
