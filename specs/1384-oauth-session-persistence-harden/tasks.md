---
description: "Task list for OAuth Session Persistence — Harden (1384)"
---

# Tasks: OAuth Session Persistence — Harden (Anti-Clobber)

**Input**: Design documents from `specs/1384-oauth-session-persistence-harden/`
**Prerequisites**: plan.md, spec.md (US1–US3, FR-001..FR-010, SR-001..SR-006), contracts/anonymous-no-clobber.md
**Follow-on to**: Feature 1381 / PR #942 (merged + deployed to preprod)

**Tests**: Frontend Vitest unit tests simulate interleaved init orderings and single-flight; backend pytest covers the no-clobber guard. E2E is owner-driven against the Amplify URL (Google consent cannot be automated).

**Two-dashboard guard**: All work targets the **Customer Dashboard** (`frontend/` + `src/lambdas/dashboard/`). Do NOT touch `src/dashboard/` (HTMX admin).

**Hotspot warning**: `src/lambdas/dashboard/auth.py` / `router_v2.py` are shared with in-flight auth features (1381/1383/1382). Keep the backend diff confined to the `/anonymous` handler + a small cookie-inspection helper; rebase before committing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3 (or SETUP/FOUND/DIAG/POLISH)

---

## Phase 1: Setup

- [ ] T001 [SETUP] Confirm the worktree serves the customer-dashboard paths; re-read the cited ranges: `frontend/src/hooks/use-auth.ts:52-129`, `use-session-init.ts:46-103`, `stores/auth-store.ts:102-239`, `src/lambdas/dashboard/router_v2.py:382` + `:197`. Activate venv (`source .venv/bin/activate`); `cd frontend && npm ci` for the frontend toolchain.
- [ ] T002 [SETUP] Capture a baseline waterfall: with an owner OAuth session, reload and record the current `/refresh` call count and identities per load (expect the 3-call, two-identity clobber). Store as the before-state so the fix is provably a change.

---

## Phase 2: Foundational — Verify-Fail gate (blocks conclusions, not the frontend fix)

**⚠️ Runs only IF the owner's post-#942 interactive login STILL guests on reload (D1).** Rules out deploy/data causes before attributing to the frontend race. Does NOT block T005–T013 (the frontend fix is correct regardless).

- [ ] T003 [DIAG] (plan §Verify-Fail i) Confirm the live dashboard-Lambda alias serves #942 code, NOT a frozen env-snapshot (v105/v108/v110). Check `aws lambda get-alias`/`get-function-configuration` for the live `FunctionVersion` + image digest; verify the served code contains `get_user_by_cognito_sub` (`auth.py:2906`) and the Cognito-branch identity resolution (`auth.py:2989-3012`). If it points at a pre-#942 snapshot → the fix is a deploy/alias-repoint (hand off), not this feature.
- [ ] T004 [DIAG] (plan §Verify-Fail ii) Confirm the owner's user record has `cognito_sub` in the `by_cognito_sub` GSI: decode a fresh owner id_token for `sub`, query the GSI, assert one item exists and `_update_cognito_sub` (`auth.py:2456`) ran on last login. If missing → `/refresh` returns guest even with #942 code; backfill via re-login/one-off write (no new resource). **Record both verdicts in the PR/spec before proceeding to attribute to the race.**

**Checkpoint**: Either the residual is confirmed to be the frontend race (proceed), or it is a deploy/data cause (hand off, stop).

---

## Phase 3: User Story 1 + 3 — Single-flight, owned bootstrap, anti-clobber (P1/P2) 🎯 MVP

**Goal**: Identity bootstrap runs once per load under any ordering; no anon-mint while an OAuth session is present/restorable.

**Independent Test**: Instrumented concurrent-mount test → `createAnonymousSession` ≤1 call, concurrent `/refresh` share one promise; owner reload → 0 `/anonymous`, all `/refresh` OAuth.

### Tests for User Story 1/3 (write first)

- [ ] T005 [P] [US1] Vitest in `frontend/src/stores/__tests__/`: simulate the race — mock `authApi.refreshToken()` to resolve slowly with an OAuth `user_id` while a second caller invokes `signInAnonymous()`; assert the OAuth user wins and `createAnonymousSession` is NOT called (FR-001/FR-003).
- [ ] T006 [P] [US3] Vitest: fire `restoreSession()` twice and `refreshSession()` concurrently in one tick; assert `authApi.refreshToken()` is invoked once (single-flight, FR-004) and the shared promise resolves all callers (SC-005).
- [ ] T007 [P] [US2] Vitest: with NO cookie (mock `/refresh` → 401) assert exactly one `createAnonymousSession()` still fires — guard does not starve real guests (FR-006/SR-003).

### Implementation for User Story 1/3 (frontend — the race source)

- [ ] T008 [US3] (FR-004) In `frontend/src/stores/auth-store.ts`, add a shared in-flight promise for the `/refresh` callers (`restoreSession` `:102`, `refreshSession` `:343`): concurrent calls await one request/one cookie write; clear on settle. Do NOT cache results across settles (preserve per-request blocklist, SR-005).
- [ ] T009 [US1] (FR-003) In `auth-store.ts` `signInAnonymous` (`:200`): before minting, no-op (return existing session) if a restore is in flight OR the store holds a non-anonymous user. Guards the common single-tab clobber.
- [ ] T010 [US1] (FR-002) In `frontend/src/hooks/use-auth.ts`, REMOVE the independent `signInAnonymous().catch(...)` from the init effect (`:52-69`, specifically `:59-64`); `useAuth` consumes resolved auth state and keeps only the timer/redirect duties. Bootstrap becomes solely `useSessionInit`'s job.
- [ ] T011 [US3] (FR-004) Ensure `useSessionInit` (`use-session-init.ts:46-103`) remains the sole restore-or-mint owner; verify `initAttempted` + `isInitialized` still dedupe now that `useAuth` no longer writes the bootstrap path. Confirm `requireAuth` protected routes render `isInitializing` (`:110`) until bootstrap resolves (no stranded route — AR#2 #2).
- [ ] T012 [US1] Run `cd frontend && npm test` (Vitest) + `npm run typecheck`; confirm T005–T007 pass and no regressions in existing auth/session specs.

**Checkpoint**: Under any client init ordering, no anon-mint occurs over an OAuth session; concurrent refreshes collapse to one.

---

## Phase 4: User Story 1 — Backend no-clobber backstop (P1)

**Goal**: `/api/v2/auth/anonymous` refuses to overwrite a valid Cognito `refresh_token` cookie — survives multi-tab and any future client path.

- [ ] T013 [P] [US1] Backend unit test in `tests/unit/dashboard/`: `POST /api/v2/auth/anonymous` with (a) incoming `refresh_token` = valid Cognito token → guard refuses to set an `anon.*` cookie and logs `anonymous.clobber_blocked`; (b) incoming cookie `anon.*` → mints normally; (c) no cookie → mints normally (FR-005/FR-006/SR-003). Assert no token material in logs (SR-006).
- [ ] T014 [US1] (FR-005, SR-002) In `src/lambdas/dashboard/router_v2.py` `create_anonymous_session()` (`:382`): read the incoming cookie via `_extract_refresh_token_from_event` (`:197`); if it is a valid non-`anon.*` (Cognito) token — validated server-side using the same local discrimination as the refresh path (`auth.py:2978`), NO Cognito round-trip on the guest path — do NOT emit the `anon.*` `Set-Cookie`; return without clobbering. Keep `require_csrf_middleware` (SR-004). Confine the diff to this handler + a small cookie-inspection helper (hotspot).
- [ ] T015 [US1] (FR-009, SR-006) Add the `anonymous.clobber_blocked` diagnostic with hash-prefix/masking (no raw token, CWE-117/312). Run `pytest tests/unit/dashboard/ -v`, `ruff`, and `make sast`/bandit on the changed file.

**Checkpoint**: A stray or multi-tab client mint cannot overwrite a live OAuth session.

---

## Phase 5: User Story 2 + Verification Seal (P1/P2)

- [ ] T016 [US1] (SC-001, SC-002, FR-007) Owner interactive Google login on Amplify → reload **≥5×**; in DevTools confirm `POST /api/v2/auth/anonymous` = **0 calls** and **every** `/refresh` carries the OAuth token → 200 with OAuth `user_id`; **0** `anon.*`. Attach the network trace (contrast with T002 baseline).
- [ ] T017 [US1] (SC-003, FR-008) With the restored session, navigate `/` ↔ `/settings` via left-nav ≥3 cycles; confirm UserMenu + Settings show the same Google account (0 guest/OAuth mismatches) and the nav stays responsive.
- [ ] T018 [P] [US2] (SC-004) Fresh browser profile (no cookies) → load Amplify → confirm exactly one `/anonymous`, working guest dashboard; reload → guest restored via `anon.*` cookie, not re-minted (FR-006).
- [ ] T019 [P] [US3] (SC-006, SR-005) Verify the `/refresh` blocklist check (`auth.py:2963-2974`) still runs per request under single-flight (a blocklisted token still 401s `token_revoked`); confirm no token material moved to JS storage (SR-001) — grep the frontend diff for `localStorage`/`sessionStorage` token writes.
- [ ] T020 [POLISH] (SC-001..SC-006) Produce a verification record: 0 `/anonymous` over 5 reloads, all-OAuth `/refresh`, Settings identity match, responsive nav, fresh-profile guest works, security checks green — attach traces/log excerpts. Run `make validate` + `pytest tests/unit/ -m "not preprod"` + frontend Vitest; GPG-sign commits (venv active). Do NOT push/open PR (pipeline stops at planning). **Finalization is gated on the D1 owner live-verify outcome.**

---

## Dependencies & Execution Order

- **Setup (T001–T002)**: first.
- **Verify-Fail (T003–T004)**: runs only if D1 shows persisting guest; gates *attribution*, not the frontend fix. If it finds a deploy/data cause, STOP and hand off.
- **US1/US3 frontend (T005–T012)**: core; tests (T005–T007) before implementation (T008–T011). Correct regardless of Verify-Fail.
- **Backend backstop (T013–T015)**: independent of the frontend; can run in parallel with Phase 3 (different files/language).
- **Verification (T016–T020)**: requires the frontend fix + backend guard deployed to preprod; owner-manual Google login.

### Parallel Opportunities

- T005, T006, T007 (independent Vitest specs) in parallel.
- Backend backstop (T013–T015) parallel with frontend Phase 3 (different files, no shared code).
- T018, T019 (guest-flow + security checks) parallel during verification.

---

## Requirement → Task Coverage (traceability)

| Requirement | Task(s) |
|-------------|---------|
| FR-001 (no anon-mint under any ordering) | T005, T008, T009, T010, T016 |
| FR-002 (single owned bootstrap; remove useAuth mint) | T010, T011 |
| FR-003 (signInAnonymous guard) | T005, T009 |
| FR-004 (single-flight, idempotent bootstrap) | T006, T008, T011 |
| FR-005 (backend no-clobber on /anonymous) | T013, T014 |
| FR-006 (real guests still get a session) | T007, T013, T018 |
| FR-007 (all /refresh OAuth, no /anonymous) | T016 |
| FR-008 (Settings shows Google, no split-brain) | T017 |
| FR-009 (clobber diagnostics, no secrets) | T015 |
| FR-010 (no new AWS resources) | T014 (reuse), plan Constitution Check |
| SR-001 (tokens httpOnly, no JS storage) | T019 |
| SR-002 (server-side Cognito-token validation) | T014 |
| SR-003 (guard never starves guests) | T007, T013, T018 |
| SR-004 (CSRF on /anonymous unchanged) | T014 |
| SR-005 (blocklist survives single-flight) | T008, T019 |
| SR-006 (no secret logging) | T013, T015 |
| SC-001..SC-006 | T016–T020 |
| Verify-Fail (D1/D2 causes) | T003, T004 |

Every FR/SR maps to ≥1 task. Every task traces to a requirement or an explicit setup/diagnostic/verification purpose.

---

## Adversarial Review #3

Final readiness review across spec.md, plan.md, tasks.md, contracts/.

### Highest-risk task
**T010 — removing `useAuth`'s independent `signInAnonymous()` (`use-auth.ts:59-64`).** Risk: this was the safety net for `requireAuth` routes when bootstrap is slow; naively removing it could leave a protected route with no session and no loading state → blank/looping page for real users, a worse regression than the clobber. Mitigation baked in: T011 verifies `useSessionInit` remains the sole bootstrap owner AND that protected routes render `isInitializing` (`use-session-init.ts:110`) until it resolves; AR#2 #2 pre-cleared the stranded-route concern; T012 runs the existing auth/session Vitest specs to catch a regression before preprod.

### Most-likely rework
**T014 — the backend "is this a valid Cognito token" discrimination.** If the guard is too strict (full Cognito verify) it adds latency/failure to the guest path; too loose (bare "not `anon.*`") and a malformed cookie could suppress a legitimate guest mint. Rework risk: tuning the local validation until it both (a) reliably recognizes a real Cognito JWE and (b) never blocks an absent/`anon.*`/garbage cookie from minting. Mitigation: T013 pins all three cases (valid-Cognito → block, `anon.*` → mint, absent → mint) as unit tests first; plan AR#2 #4 fixes the decision to local shape-discrimination with NO Cognito round-trip on the guest path. If the owner's live login shows the frontend fix alone (Phase 3) already yields SC-001/SC-002, the backend guard is pure defense-in-depth and its tuning is non-urgent.

### Readiness checks
- Race-survives-#942 verified against source with file:line (`use-auth.ts:52-69` second mint trigger; shared-`isInitialized` TOCTOU; per-mount timers), not re-derived from the prior spec. ✅
- Primary (frontend race source) and backstop (backend no-clobber) both have tasks; a client-only fix's multi-tab hole is owned by T013/T014. ✅
- The anonymous-first product is protected: FR-006/SR-003 have dedicated tests (T007/T018) so the guard cannot starve real guests. ✅
- Verify-Fail causes (live alias snapshot, missing GSI record) are explicit tasks (T003/T004) gating attribution before blaming the race. ✅
- Security preserved: httpOnly-only (T019), CSRF unchanged (T014), blocklist under single-flight (T008/T019), no secret logs (T015). ✅
- Shared backend hotspot (auth.py/router_v2.py w/ 1381/1383) called out; backend diff confined to `/anonymous` + a helper. ✅

### Gate

**READY FOR IMPLEMENTATION — with one deferred dependency.**

Rationale: a fresh agent can execute this; every requirement is task-covered and traceable; the two most dangerous failure modes (stranded `requireAuth` routes from removing the `useAuth` mint, and a guard that starves real guests) are explicitly mitigated with tests-first tasks. The frontend fix is correct independent of runtime facts. The one open dependency is **D1 — the owner's pending post-#942 live-verify**: if it shows the reload STILL guests, T003/T004 must first rule out the live-alias-snapshot and missing-GSI-record causes before the race attribution stands, and T020 finalization is gated on that outcome. No open CRITICAL/HIGH. Pipeline stops here (no `/speckit.implement`, no push).
