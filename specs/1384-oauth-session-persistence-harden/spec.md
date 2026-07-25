# Feature Specification: OAuth Session Persistence — Harden (Anti-Clobber)

**Feature Branch**: `1384-oauth-session-persistence-harden`
**Created**: 2026-07-24
**Status**: Draft (planning only — no implementation in this pipeline)
**Input**: Follow-on to Feature 1381 (PR #942, merged + deployed to preprod). After Google OAuth login on the customer frontend (Next.js on AWS Amplify, `https://main.d29tlmksqcx494.amplifyapp.com`), a full-page reload (F5) can still flip the app to Guest; Settings then shows "Anonymous/Guest" while the dashboard had shown the signed-in Google user. PR #942 fixed the primary defect (the Cognito refresh branch now resolves `user_id` so `restoreSession()` succeeds), but the owner's canonical DevTools waterfall shows **three** `POST /api/v2/auth/refresh` calls in one page load carrying **two different identities under the same `refresh_token` cookie** — a guest `anon.<uuid>` token and an OAuth Cognito JWE (`eyJ…`). That is a residual **cookie-clobber race** that #942 does not fully close.

---

## Root-Cause Investigation (verified against current code)

Feature 1381's diagnosis is accepted and NOT re-derived. This feature verifies #942 landed and attacks what remains.

### What #942 fixed (confirmed in source)

- `refresh_access_tokens()` Cognito branch now decodes the freshly-issued `id_token` sub and resolves the internal `user_id` via the `by_cognito_sub` GSI (`src/lambdas/dashboard/auth.py:2989-3012`, helper `get_user_by_cognito_sub` at `auth.py:2906-2945`). `cognito_sub` is written on OAuth login (`_update_cognito_sub`, `auth.py:2456`).
- Because `/refresh` now returns a non-null `user_id`, `restoreSession()` takes the Cognito-restore branch and returns `true` (`frontend/src/stores/auth-store.ts:141-197`) instead of hitting `if (!data.userId) return false` (`auth-store.ts:157-161`). So `useSessionInit`'s own fallback to `signInAnonymous()` (`frontend/src/hooks/use-session-init.ts:73-76`) no longer fires on the happy path.

### The residual defect — cookie clobber survives #942 (confirmed)

The fundamental fragility is unchanged by #942: **guest and OAuth sessions share ONE cookie** — name `refresh_token`, path `{/stage}/api/v2/auth`, `SameSite=None; Secure; HttpOnly` (`src/lambdas/dashboard/router_v2.py:179-194`). ANY anonymous-session mint overwrites the OAuth cookie. #942 closed only ONE of the paths that mint an anon session on load. Two others remain:

- **Second anon-mint trigger — `useAuth`'s init effect (independent of `useSessionInit`).** `useAuth` calls `signInAnonymous()` whenever `!isInitialized && !hasValidSession && requireAuth` (`frontend/src/hooks/use-auth.ts:52-69`, specifically the `signInAnonymous().catch(...)` at `:59-64`). This path was **not touched by #942** (which only changed the backend refresh identity and `restoreSession`'s guard). `useAuth` is mounted at **9 sites** (`components/auth/protected-route.tsx`, `settings/page.tsx`, `user-menu.tsx`, `oauth-buttons.tsx`, `magic-link-form.tsx`, `sign-out-dialog.tsx`, `app/auth/callback/page.tsx`, `app/auth/verify/page.tsx`, plus `use-auth.ts` itself). `signInAnonymous()` → `authApi.createAnonymousSession()` → `POST /api/v2/auth/anonymous` (`router_v2.py:382`), which mints `anon.{user_id}.{secret}` (`auth.py:177`) and **sets the shared `refresh_token` cookie**, clobbering the OAuth `eyJ…` value.

- **Shared `isInitialized` is a check-then-act (TOCTOU) race.** Both `useSessionInit` (`use-session-init.ts:48`) and every `useAuth` instance (`use-auth.ts:53`) read `!isInitialized` and later write `setInitialized(true)`. On a cold reload, `restoreSession()` is `await`-ed (network round-trip to `/refresh`) while `useAuth`'s synchronous init effect can read `isInitialized === false`, see no valid session yet, and fire `signInAnonymous()` **before** the OAuth restore resolves. The mint and the restore interleave on the one cookie.

- **Multiple pre-expiry refresh timers = the 3-refresh waterfall.** Each `useAuth` mount schedules its own pre-expiry refresh (`use-auth.ts:96-98`, `refreshSession()`) and its own 60s validity check (`use-auth.ts:104-111`). With several `useAuth` instances live at once, one page load issues several `/refresh` calls, not one — matching the owner's three-call waterfall. If one of those calls lands **after** a stray anon-mint clobbered the cookie, it sends `anon.*` and the response comes back guest, permanently flipping the tab.

### Why the symptom persists post-#942

`restoreSession()` succeeds and sets the OAuth user (dashboard shows signed-in), but a concurrent `useAuth` anon-mint (or a pre-expiry refresh firing on the clobbered cookie) overwrites `refresh_token` with `anon.*`; the next `/refresh` (there are 2-3 in the load) returns guest, `setUser` rewrites the store to anonymous, and Settings — read a beat later — shows "Anonymous/Guest". One shared cookie, two writers, non-deterministic winner.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OAuth session survives reload under ANY init ordering (Priority: P1) 🎯 MVP

A signed-in Google user reloads (F5). Regardless of the order in which `useSessionInit` restore, `useAuth` init, and any pre-expiry refresh timer fire, the app stays signed in as the Google user. No anonymous session is ever minted while an OAuth session is present or restorable.

**Why this priority**: This is the residual bug. #942 made the happy path work, but the race means "works most of the time," which for auth is "broken." The MVP is making persistence deterministic under all init orderings.

**Independent Test**: On the real Amplify frontend, owner interactive Google login → reload ≥5 times. In DevTools, confirm every `POST /api/v2/auth/refresh` in each load carries the OAuth token (never `anon.*`) and returns 200 with the OAuth `user_id`; `POST /api/v2/auth/anonymous` is NOT called; UI and Settings stay the Google user. No mocks.

**Acceptance Scenarios**:

1. **Given** a valid OAuth refresh cookie, **When** the page reloads and `useSessionInit` + all `useAuth` instances mount concurrently, **Then** exactly one identity-bootstrap runs, `restoreSession()` restores the OAuth user, and `signInAnonymous()` is never called.
2. **Given** the reload, **When** `useAuth`'s init effect evaluates `!isInitialized`, **Then** it does NOT independently mint an anonymous session while a restore is in flight or an OAuth cookie is present.
3. **Given** several `useAuth` mounts each scheduling a pre-expiry refresh, **When** the timers/checks fire during/after restore, **Then** all `/refresh` calls carry the OAuth cookie (never a clobbered `anon.*`) and the store stays authenticated.
4. **Given** the backend `/api/v2/auth/anonymous` endpoint receives a request whose incoming `refresh_token` cookie is a valid non-anon (Cognito) token, **When** it processes the mint, **Then** it refuses to overwrite the OAuth cookie (no-clobber guard) and the OAuth session survives even if a stray client mint slips through.

---

### User Story 2 - Real anonymous users still get a guest session (Priority: P1)

A brand-new visitor with no cookie (never signed in) lands on the app. They still get an anonymous session so the dashboard works, exactly as today. The anti-clobber guards must not starve legitimate guest creation.

**Why this priority**: The obvious fix ("stop minting anon") could break the entire anonymous-first product. This story pins the guard's blast radius: block anon-mint ONLY when an OAuth session is present/restorable, never for a genuine first-time visitor.

**Independent Test**: Fresh browser profile (no cookies) → load Amplify → confirm exactly one `POST /api/v2/auth/anonymous`, a guest session is created, and the dashboard renders. Reload → guest session restored via the `anon.*` cookie, not re-minted.

**Acceptance Scenarios**:

1. **Given** no `refresh_token` cookie at all, **When** the app loads, **Then** a single anonymous session is created and the dashboard works.
2. **Given** an existing `anon.*` refresh cookie, **When** the app reloads, **Then** `restoreSession()` restores the guest (the anon branch, `auth-store.ts:116-138`) and no new mint occurs.
3. **Given** the server-side no-clobber guard, **When** the incoming cookie is `anon.*` or absent, **Then** `POST /api/v2/auth/anonymous` still mints normally (guard keys on "valid Cognito cookie present," not "any cookie present").

---

### User Story 3 - Init is single-flight and idempotent (Priority: P2)

The session-init logic runs identity bootstrap exactly once per page load even when many components mount `useAuth` simultaneously, and concurrent `restoreSession()`/`refreshSession()` collapse to one in-flight request.

**Why this priority**: Deduplicating the bootstrap and single-flighting the refresh is the durable structural fix that removes the race source rather than patching symptoms. P2 because US1's guard already blocks the harm; this removes the cause.

**Independent Test**: Instrument the store; on reload with all 9 `useAuth` mounts, assert `createAnonymousSession` is called ≤1 time and concurrent `refreshToken()` calls share a single promise.

**Acceptance Scenarios**:

1. **Given** N concurrent `useAuth` mounts, **When** the page loads, **Then** identity bootstrap (restore-or-mint) executes once, not N times.
2. **Given** two callers invoke `restoreSession()`/`refreshSession()` within the same tick, **When** both run, **Then** they await a single shared in-flight `/refresh` promise (single-flight), not two racing cookie writes.
3. **Given** `useSessionInit` owns bootstrap, **When** `useAuth`'s init effect runs, **Then** `useAuth` no longer performs an independent anon-mint or competes to write `isInitialized`.

---

### Edge Cases

- **Multi-tab**: Tab A is OAuth, Tab B does a fresh load. Tab B must not mint an anon session that clobbers the shared-cookie OAuth identity for Tab A. (Cookie is per-origin, shared across tabs.) The server-side no-clobber guard is the backstop here since client single-flight is per-tab.
- **Pre-expiry timer fires during restore**: `refreshSession()` (`use-auth.ts:97`) fires while `restoreSession()` is mid-flight → both write the cookie. Single-flight must collapse them; if not collapsed, both must be OAuth-token writes (never an anon-mint).
- **Slow network**: `restoreSession()`'s `/refresh` is slow (or hits `SESSION_INIT_TIMEOUT_MS`, `use-session-init.ts:78-80`); a `useAuth` init effect must not treat "restore not done yet" as "no session → mint anon."
- **Expired/revoked OAuth refresh**: `/refresh` legitimately 401s; the app SHOULD then fall back to guest — but only after restore is conclusively unrestorable, and the fallback mint must be the single owned path, not a racing `useAuth` mint.
- **Genuine first visit under the guard**: no cookie → guard must allow the mint (US2). The guard keys on a *valid Cognito* cookie, not on cookie presence.
- **`useAuth` with `requireAuth: true`**: `protected-route.tsx` wraps authenticated views; its `useAuth({requireAuth})` init effect (`use-auth.ts:57-65`) is the most likely stray-mint trigger during an OAuth restore.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: On page reload with a valid or restorable OAuth session, the frontend MUST NOT mint an anonymous session under ANY interleaving of `useSessionInit` restore, `useAuth` init, and pre-expiry refresh timers. (Closes the clobber race that survives #942.)
- **FR-002**: `useAuth`'s init effect MUST NOT independently call `signInAnonymous()`; identity bootstrap (restore-or-mint) MUST be owned by a single code path (`useSessionInit`). (`use-auth.ts:52-69` is the second trigger to remove.)
- **FR-003**: `signInAnonymous()` MUST be guarded so it does not mint an anonymous session while an OAuth restore is in flight or an OAuth session is already present in the store.
- **FR-004**: Session-init MUST be single-flight and idempotent: concurrent `restoreSession()`/`refreshSession()` calls MUST collapse to one in-flight `/refresh` request (one cookie write), and identity bootstrap MUST run at most once per page load regardless of how many `useAuth` instances mount.
- **FR-005**: The backend `POST /api/v2/auth/anonymous` endpoint MUST refuse to overwrite an existing valid non-anon (Cognito) `refresh_token` cookie — a defense-in-depth no-clobber guard that survives a stray client-side mint. When the incoming cookie is a valid Cognito token, the endpoint MUST NOT set an `anon.*` cookie.
- **FR-006**: A genuine first-time visitor (no `refresh_token` cookie) MUST still receive exactly one anonymous session; the guards MUST NOT block legitimate guest creation (guard keys on "valid Cognito cookie present," not "any cookie present").
- **FR-007**: After login + reload, every `POST /api/v2/auth/refresh` in the page load MUST carry the OAuth token and return 200 with the OAuth `user_id`; `POST /api/v2/auth/anonymous` MUST NOT be called while the OAuth session is present. (Directly measurable in DevTools.)
- **FR-008**: Settings MUST show the signed-in Google account after reload and after navigation (no "Anonymous/Guest" split-brain with the dashboard/UserMenu).
- **FR-009**: Diagnostic logging MUST make an attempted clobber observable server-side (e.g. `anonymous.clobber_blocked` when the guard refuses a mint over a valid Cognito cookie) without logging token material (hash-prefix/masking, CWE-117/CWE-312).
- **FR-010**: No new AWS resources; reuse the existing dashboard Lambda, Cognito pool, `by_cognito_sub` GSI, and DynamoDB tables. Backend change is confined to the `/anonymous` handler + shared cookie/token helpers.

### Security Requirements

- **SR-001**: Refresh/anon tokens MUST remain in httpOnly cookies; NO token material may move to JS-readable storage (no `localStorage`/`sessionStorage` token persistence). The backend Bearer + `require_role` remains the security boundary.
- **SR-002**: The no-clobber guard (FR-005) MUST validate "is this a real Cognito token" server-side (token shape/verification consistent with the existing refresh path), NOT trust a client claim, so an attacker cannot forge a cookie to suppress guest creation for others.
- **SR-003**: The guard MUST NOT create a denial path for legitimate anonymous users: an absent or `anon.*` cookie MUST always be allowed to mint (FR-006). The guard is "don't overwrite a valid OAuth session," never "require a cookie to mint."
- **SR-004**: CSRF posture is unchanged: `/api/v2/auth/anonymous` keeps its existing `require_csrf_middleware` (`router_v2.py:382`); the guard adds no CSRF-exempt surface.
- **SR-005**: The blocklist/eviction check on `/refresh` (`auth.py:2963-2974`) MUST remain intact; single-flighting refresh MUST NOT bypass it.
- **SR-006**: No secret/token values in the new diagnostics (SR consistent with repo SAST rules).

### Key Entities

- **`refresh_token` cookie**: single shared cookie for BOTH guest (`anon.*`) and OAuth (Cognito `eyJ…`) sessions; name/path `{/stage}/api/v2/auth` (`router_v2.py:179-194`). The shared-writer fragility is the root of the clobber.
- **`useSessionInit`**: the intended single owner of identity bootstrap (`use-session-init.ts:30-115`).
- **`useAuth` init effect**: the competing anon-mint trigger to remove (`use-auth.ts:52-69`); also owns the pre-expiry refresh timers (`use-auth.ts:72-129`).
- **`/api/v2/auth/anonymous` handler**: the server-side guard site (`router_v2.py:382`).
- **auth store `signInAnonymous` / `restoreSession` / `refreshSession`**: the client single-flight sites (`auth-store.ts:102-198`, `:200-239`, `:343+`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After owner interactive Google login, across **≥5 consecutive reloads**, `POST /api/v2/auth/anonymous` is called **0 times** while the OAuth session is present (DevTools network, no mocks).
- **SC-002**: Across those reloads, **100%** of `POST /api/v2/auth/refresh` calls carry the OAuth token and return 200 with a non-null OAuth `user_id`; **0** carry `anon.*`.
- **SC-003**: Settings and the top-nav UserMenu show the **same** Google identity after reload and after `/` ↔ `/settings` navigation — **0** guest/OAuth mismatches across ≥3 cycles.
- **SC-004**: A fresh browser profile (no cookie) yields **exactly one** `POST /api/v2/auth/anonymous` and a working guest dashboard — the guard does not starve real anonymous users.
- **SC-005**: Under an instrumented concurrent-mount test, identity bootstrap runs **≤1** time and concurrent `/refresh` calls share **one** in-flight promise (single-flight proven).
- **SC-006**: No security regression: CSRF on `/anonymous`, the `/refresh` blocklist check, and httpOnly cookie scope all still pass; no token material in logs or JS storage.

## Assumptions

- PR #942 is deployed to the code the live alias serves. (This is a VERIFY-FAIL risk — see the diagnostic in plan/tasks — because the dashboard Lambda has manual env-snapshot versions v105/v108/v110 under a `lifecycle { ignore_changes }` freeze, so the live alias could point at a snapshot lacking #942.)
- The owner's user record has `cognito_sub` populated in the `by_cognito_sub` GSI (written by `_update_cognito_sub`, `auth.py:2456`). If missing, #942's `get_user_by_cognito_sub` returns `None` and `/refresh` still returns guest — a second VERIFY-FAIL suspect.
- Cookies flow cross-site in regular windows (owner evidence: `Sec-Fetch-Storage-Access: active`); 3rd-party cookie blocking is NOT the live cause.
- Owner performs the interactive Google login for verification (Google consent cannot be automated).

## Out of Scope

- The HTMX admin dashboard (`src/dashboard/`). Customer dashboard only.
- OAuth *login* flow changes (code exchange, provider config) beyond persistence.
- Moving tokens out of httpOnly cookies (explicitly forbidden, SR-001).
- Prod rollout (tracked separately); this feature targets fix + preprod verification.
- Re-deriving 1381's diagnosis or re-fixing the Cognito refresh identity (that is #942).

---

## Adversarial Review #1

Attacked as a pentester, a skeptical staff engineer, and a 3am on-call. All CRITICAL/HIGH self-resolved by editing the spec above.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | CRITICAL | **"Stop minting anonymous" could kill the anonymous-first product.** A blunt guard that blocks `signInAnonymous()` whenever any cookie exists would deny guest creation to real first-time visitors and break the dashboard for everyone not signed in. | Added **US2** + **FR-006/SR-003**: the guard keys strictly on "a **valid Cognito** cookie is present," never on cookie presence. Absent/`anon.*` cookie always mints. SC-004 measures it. |
| 2 | CRITICAL | **Race survives #942 but a client-only fix is per-tab.** Multi-tab / a stray mint from any of 9 `useAuth` sites can still clobber the shared cookie; a purely frontend guard leaves a backend hole. | Added **FR-005** server-side no-clobber guard on `/api/v2/auth/anonymous` (defense-in-depth) as the backstop that survives any client path, present or future. Multi-tab edge case documents it. |
| 3 | HIGH | **Session fixation via the guard.** If the guard trusted a client-asserted "I have an OAuth session" to suppress guest creation, an attacker could forge a cookie to deny others a session (or pin identity). | **SR-002**: the guard verifies the cookie is a real Cognito token server-side (same validation as the refresh path), never a client claim. |
| 4 | HIGH | **Removing `useAuth`'s mint could strand `requireAuth` routes** with no session at all (blank/looping protected route) if `useSessionInit` hasn't finished. | **FR-002/FR-004**: bootstrap becomes single-flight and owned by `useSessionInit`; `useAuth` awaits the shared init rather than minting. Protected routes render the init/loading state until bootstrap resolves (existing `isInitializing`, `use-session-init.ts:110`). |
| 5 | HIGH | **VERIFY-FAIL blind spot.** If the owner's live login STILL guests post-#942, the team could thrash on the frontend race when the real cause is (a) the live alias serving a pre-#942 env snapshot, or (b) a missing `cognito_sub` GSI record. | Added both as **Assumptions** + a dedicated diagnostic (plan §Verify-Fail, tasks T-diag) that checks the live alias code/version AND the owner's `by_cognito_sub` record before blaming the race. |
| 6 | MED | **3am reload storm / timer pile-up.** Multiple `useAuth` mounts each schedule a `refreshSession()` + 60s check interval; a burst of reloads multiplies `/refresh` load and cookie writes. | **FR-004** single-flight collapses concurrent refreshes to one request; US3 pins bootstrap to ≤1 run. SC-005 proves it. |
| 7 | MED | **Single-flight could bypass the blocklist** if it caches a stale successful refresh across an eviction. | **SR-005**: single-flight caches only the in-flight promise for one tick, not results across evictions; the `/refresh` blocklist check (`auth.py:2963-2974`) still runs per request. |
| 8 | MED | **Adding clobber diagnostics risks logging the Cognito token** while inspecting the cookie. | **FR-009/SR-006**: hash-prefix/masking only; log the decision (`clobber_blocked`), never the token. |
| 9 | LOW | **Guard could mask a legitimate guest→OAuth downgrade** (user signs out, expects guest). | Sign-out clears the cookie via the existing signout path before any mint; the guard only triggers on a *valid* Cognito cookie, so a signed-out (cleared) cookie mints normally. Noted in US2 AC-3. |

**Post-resolution gate: 0 CRITICAL, 0 HIGH remaining.** Residual MED/LOW items are captured as requirements/edge cases and carried into plan and tasks.

---

## Clarifications

Self-answered from the codebase/context (no human asked, per pipeline rules). Each records the question, the answer, and evidence.

### Session 2026-07-24

- **Q1: Does the clobber race actually survive #942, or did #942 close it?**
  **A: It survives.** #942 only removed `useSessionInit`'s *own* fallback trigger (by making `restoreSession` succeed). It did not touch `useAuth`'s independent `signInAnonymous()` at `use-auth.ts:59-64`, nor the shared-`isInitialized` TOCTOU (`use-auth.ts:53` vs `use-session-init.ts:48`), nor the per-mount pre-expiry timers (`use-auth.ts:96-98`) that produce the 3-refresh waterfall. Any of these can still write `anon.*` over the OAuth cookie. Evidence: use-auth.ts:52-69, 72-129; use-session-init.ts:46-103; auth-store.ts:200-239.

- **Q2: Frontend guard, backend guard, or both?**
  **A: Both, primary frontend.** Primary fix is client-side single-flight + owned bootstrap + a `signInAnonymous` guard (removes the race at the source, FR-002/FR-003/FR-004). Backend no-clobber on `/anonymous` (FR-005) is defense-in-depth for multi-tab and any future client path, since the server already receives the incoming cookie on that same path (`_extract_refresh_token_from_event`, `router_v2.py:197`) and can refuse to overwrite a valid Cognito token. Evidence: router_v2.py:197, 382; auth.py:177.

- **Q3: How does the backend tell "this cookie is a real OAuth session" without a client claim?**
  **A: Token shape + existing Cognito validation.** Guest tokens are self-describing `anon.{user_id}.{secret}` (`auth.py:177`, branch check `auth.py:2978`). Anything not `anon.*` is a candidate Cognito token; the guard verifies it via the same path the refresh handler already trusts (decode/verify), server-side (SR-002). No client assertion is trusted. Evidence: auth.py:2976-2979, 2981-3012.

- **Q4: Does removing `useAuth`'s anon-mint break `requireAuth` protected routes?**
  **A: No.** Bootstrap moves to the single owned path (`useSessionInit`); protected routes render the existing initializing/loading state until it resolves (`use-session-init.ts:110`, `isInitializing`). `useAuth` consumes the resolved state instead of racing to create it. Evidence: use-auth.ts:131-136; use-session-init.ts:105-114.

- **Q5: Can the anti-clobber guard itself be abused to deny guest sessions (DoS/fixation)?**
  **A: No, by construction.** The guard blocks a mint ONLY when the incoming cookie is a *valid* Cognito token (SR-002/SR-003). An attacker cannot forge a valid Cognito JWE, and an absent/`anon.*` cookie always mints (FR-006). So real anonymous users are never starved. Evidence: FR-006, SR-003; auth.py:2978.

**Deferred to owner (not codebase-answerable):**
- **D1 (pending live-verify)**: The owner's post-#942 interactive Google-login result on Amplify — does reload STILL guest? This gates whether the residual is the frontend race (this feature's primary fix) or a VERIFY-FAIL cause (live alias snapshot / missing GSI record). Runtime-only; the plan's Verify-Fail diagnostic resolves it. Finalizing tasks depend on this outcome.
- **D2**: Whether the live dashboard-Lambda alias points at manual env-snapshot v105/v108/v110 (frozen env) rather than the #942 image — checkable only against the deployed function.
