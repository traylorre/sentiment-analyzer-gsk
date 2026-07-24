# Feature Specification: OAuth Session Persistence

**Feature Branch**: `1381-oauth-session-persistence`
**Created**: 2026-07-23
**Status**: Draft (planning only — no implementation in this pipeline)
**Input**: Real Google OAuth login succeeds on the customer frontend (Next.js on AWS Amplify, `https://main.d29tlmksqcx494.amplifyapp.com`), but the OAuth session does not persist. `POST /api/v2/auth/refresh` returns 401 for an authenticated OAuth session on page load; session-init falls back to `signInAnonymous()`; Settings shows "Anonymous/Guest (limited features)" while the top-nav UserMenu still shows the Google user, and the left-nav becomes unresponsive after entering Settings.

---

## Root-Cause Investigation (verified against current code)

The task-provided prime suspect ("the OAuth-callback refresh cookie has wrong SameSite/Path/Domain attributes so the browser won't send it cross-site") was **investigated and found to already be resolved in current code**. It is NOT the live root cause. Evidence:

- The OAuth callback path (`src/lambdas/dashboard/router_v2.py:587-628`), the magic-link path (`router_v2.py:507-561`), and the guest path (`router_v2.py:405-416`) all build the refresh cookie through the **same** unified helper `_make_refresh_token_cookie` (`router_v2.py:179-194`) and the CSRF cookie through `_make_csrf_set_cookie` (`router_v2.py:166-176`). Both emit `SameSite=None; Secure; HttpOnly` (refresh) with a **stage-aware Path** `{/stage}/api/v2/auth` via `_cookie_path_prefix` (`router_v2.py:150-163`), `Max-Age=30 days`.
- This unification was the fix delivered by commit `0849559` (M1 WI-3, PR #928): *"stage-prefix cookie Path + stale SameSite broke deployed session restore"*. The helper's own docstring records that the inline OAuth/magic-link blocks were already updated to `SameSite=None` and the stale `Strict` was removed (`router_v2.py:182-184`).
- Because the guest path uses the **identical** cookie helper and guest restore works, cookie attributes cannot be the OAuth-specific differentiator.

The **actual** OAuth-specific breakage is in the token-refresh code path, which differs by session type. There are **two backend defects in one persistence chain**:

### Defect A — Cognito refresh round-trip returns 401 (the observed console error)

- `/api/v2/auth/refresh` is CSRF-exempt (`src/lambdas/shared/auth/csrf.py:38`), so CSRF (403) is not the cause. The 401 is emitted by `refresh_tokens()` at `router_v2.py:663-664` (no refresh token found) or `router_v2.py:670-671` (`result.error` set).
- Guest sessions carry an **opaque, self-contained** refresh token (`anon.{user_id}.{secret}`) refreshed **locally** with no external call — `refresh_access_tokens` branches to `_refresh_anonymous_session` (`auth.py:2928-2929`). This never fails on identity round-trips, which is why guest restore is reliable.
- OAuth sessions carry a **real Cognito refresh token** (`auth.py:2437`, `refresh_token_for_cookie=tokens.refresh_token`). On refresh they take the Cognito branch (`auth.py:2931-2944`) → `cognito_refresh_tokens` (`src/lambdas/shared/auth/cognito.py:213-284`), which POSTs `grant_type=refresh_token` to the Cognito token endpoint with Basic auth built from `config.client_id` / `config.client_secret` (`cognito.py:236-247`). A non-200 raises `TokenError` (`cognito.py:257-265`), surfaced as a 401 at `router_v2.py:671`.
- Prime configuration suspect: a **Cognito app-client / client-secret mismatch** between the Hosted-UI app client that ISSUED the OAuth refresh token and the `COGNITO_CLIENT_ID`/`COGNITO_CLIENT_SECRET` the dashboard Lambda uses at refresh time (`CognitoConfig.from_env`, `cognito.py:51-56`). Cognito returns `invalid_grant`/`invalid_client`, producing the 401. **This is not confirmable from source alone** — the dashboard Lambda's live env is FROZEN (Feature 1290: `modules/lambda` `lifecycle { ignore_changes = [environment] }`), so the running values can drift from Terraform. It must be discriminated at runtime (see US1 / instrumentation task).
- Alternate (less likely) sub-cause still in scope: the refresh cookie is genuinely not sent because the DEPLOYED browser-visible API path prefix differs from what `_cookie_path_prefix` computes (custom domain / base-path mapping vs raw stage). This produces the 401 at `router_v2.py:664` and is distinguishable from the Cognito-reject case by whether `_extract_refresh_token_from_event` returned a token.

### Defect B — Cognito refresh response omits `user_id` (latent; blocks persistence even after A is fixed)

- The Cognito branch of `refresh_access_tokens` returns `RefreshTokenResponse(id_token, access_token, expires_in)` only (`auth.py:2934-2939`); `user_id` and `auth_type` default to `None` (`RefreshTokenResponse`, `auth.py:1507-1517` — the model comments confirm these are "None for Cognito-backed refreshes").
- The frontend `restoreSession` (`frontend/src/stores/auth-store.ts:102-198`) requires `data.userId` for the non-anonymous branch: when `!data.userId` it returns `false` (`auth-store.ts:157-161`), and `use-session-init.ts` then calls `signInAnonymous()`.
- **Consequence**: even if Defect A is fixed and `/refresh` returns 200, an OAuth session still cannot rebuild its user object and still falls back to guest. Fixing A without B leaves every reported symptom intact.

### Why three symptoms, one chain

`restoreSession` fails → `signInAnonymous()` runs → Zustand user is overwritten with a guest identity that Settings reads ("Guest, limited features"), while the top-nav UserMenu is showing a stale pre-fallback render of the Google user, and the guest identity mismatch/aborted async work leaves the left-nav in an inconsistent, unresponsive state. One failed restore, three visible faults.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OAuth session survives a full-page reload (Priority: P1) 🎯 MVP

A user signs in with Google on the Amplify frontend, then reloads the page (F5). The app restores the same Google-authenticated session instead of dropping to guest.

**Why this priority**: This is the headline defect and the MVP. Without reload persistence, OAuth login is effectively single-use per tab and the product looks broken immediately after the marquee "Sign in with Google" flow.

**Independent Test**: On the real Amplify frontend, sign in with Google (owner-performed interactive login), reload, and confirm `POST /api/v2/auth/refresh` returns 200 with a body carrying the OAuth `user_id`, and that the app remains signed in as the Google user. No mocks.

**Acceptance Scenarios**:

1. **Given** a live Google OAuth session (valid refresh cookie present), **When** the page reloads and `SessionProvider` runs `restoreSession()`, **Then** `POST /api/v2/auth/refresh` returns 200 with `access_token`, `id_token`, and a non-null `user_id` for the OAuth user.
2. **Given** the 200 refresh response, **When** `restoreSession()` processes it, **Then** it takes the Cognito-restore branch, rebuilds the user with the OAuth identity, returns `true`, and `signInAnonymous()` is NOT called.
3. **Given** the restored session, **When** the Settings page renders, **Then** it shows the signed-in Google user (email/role `free` or higher), NOT "Anonymous/Guest".
4. **Given** an expired or revoked OAuth refresh token, **When** `/refresh` is called, **Then** the backend returns 401 with a clear reason and the frontend falls back to guest *gracefully* (no unresponsive UI).

---

### User Story 2 - OAuth session survives client-side navigation and the left-nav stays responsive (Priority: P1)

After signing in with Google, the user navigates to Settings and around the app via the left-nav. The nav stays responsive and every view reflects the Google user, not guest.

**Why this priority**: The left-nav lockup and the Settings/UserMenu identity mismatch are the other two reported symptoms of the same failed restore. Ties with US1 as P1 because they share the root cause and must both be verified to call the bug fixed.

**Independent Test**: With a restored OAuth session, click into Settings and back out through the left-nav; confirm no lockup and consistent Google identity across UserMenu, Settings, and the left-nav.

**Acceptance Scenarios**:

1. **Given** a restored OAuth session, **When** the user navigates to `/settings` and back via the left-nav, **Then** the left-nav remains interactive (no dead clicks) and no unhandled rejection/timeout fires.
2. **Given** a restored OAuth session, **When** any authenticated view renders, **Then** the identity shown by the top-nav UserMenu and by Settings is the same Google user (no guest/Google split-brain).
3. **Given** a transient `/refresh` failure during navigation, **When** the store degrades, **Then** the UI surfaces a recoverable state rather than a hung nav.

---

### User Story 3 - Security posture is preserved under cross-site cookies (Priority: P2)

The persistence fix keeps the existing auth/session/cookie security guarantees intact: httpOnly refresh cookie, CSRF double-submit protection, single-use guest tokens, and no widening of exploitable surface from `SameSite=None`.

**Why this priority**: This is auth/session/cookie work on a cross-origin (Amplify → API Gateway) deployment. `SameSite=None` is already in place and required, but any change to the refresh path must not regress CSRF, session fixation, or cookie-scope protections. P2 because it gates merge, not the demo.

**Independent Test**: Re-run the CSRF and refresh-path security checks; confirm `/refresh` still rejects forged/absent cookies, CSRF middleware still guards non-exempt state-changing routes, and no refresh token or user_id leaks into a response body beyond what the frontend requires.

**Acceptance Scenarios**:

1. **Given** the fix, **When** `/refresh` receives no valid refresh cookie, **Then** it returns 401 and issues no tokens.
2. **Given** the fix, **When** a request presents a blocklisted (evicted) refresh token, **Then** `/refresh` returns 401 `token_revoked` (`auth.py:2913-2924`) — blocklist check still runs before issuance.
3. **Given** the fix, **When** the refresh response is serialized, **Then** the rotated refresh token is never in the body (`exclude={"refresh_token_for_cookie"}`, `router_v2.py:674`) and only the minimal `user_id` needed for restore is present.
4. **Given** the fix, **When** a state-changing non-exempt route is called cross-site without a matching CSRF header/cookie, **Then** `require_csrf_middleware` still returns 403 (`csrf_middleware.py:66-73`).

---

### Edge Cases

- **Cookie sent but Cognito rejects** (Defect A, Cognito sub-case): `/refresh` returns 401 with a Cognito error; frontend must fall back to guest without UI lockup, and the backend must log enough to distinguish this from "cookie not sent."
- **Cookie NOT sent** (Defect A, path/scope sub-case): `_extract_refresh_token_from_event` returns `None`; `/refresh` returns 401 "not found." Instrumentation must make this case unambiguous.
- **Refresh succeeds but `/auth/me` fails**: `restoreSession` already best-effort registers the identity with conservative role (`auth-store.ts:177-192`); confirm this path still yields a usable OAuth session once `user_id` is present.
- **Cognito does not rotate the refresh token**: `cognito_refresh_tokens` returns `refresh_token=None` (`cognito.py:273`); the router correctly leaves the existing cookie in place (`router_v2.py:678`). Ensure this does not accidentally clear the cookie.
- **Guest → OAuth upgrade in the same tab**: after upgrade, the refresh cookie now holds a Cognito token; the next reload must restore OAuth, not the pre-upgrade guest.
- **Stage vs custom-domain path**: if a custom domain / base-path mapping is in front of API Gateway, the cookie `Path` computed from `requestContext.stage` may not match the browser path. Must be verified on the real deployment.
- **Env drift under Feature 1290 freeze**: any Cognito client/secret correction lands via the CI "Step 2.5" env sync or a manual `update-function-configuration`, NOT Terraform. A "fixed" Terraform value that never reaches the live Lambda is a trap.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `POST /api/v2/auth/refresh` MUST return HTTP 200 for a live, valid Google OAuth session on the real Amplify → API Gateway deployment.
- **FR-002**: The 200 refresh response for a Cognito-backed (OAuth) session MUST include the session's `user_id` (and `auth_type`) so the frontend can rebuild the user object. (Fixes Defect B: `auth.py:2934-2939` must populate `user_id`.)
- **FR-003**: The system MUST resolve `user_id` for a Cognito refresh from a trustworthy source — the validated token claims (`cognito_sub` → user lookup) or an existing session/user record — NOT from client-supplied data.
- **FR-004**: `restoreSession()` MUST take the Cognito-restore branch for OAuth sessions and MUST NOT fall back to `signInAnonymous()` when a valid OAuth session is restorable.
- **FR-005**: After restore, the OAuth identity MUST be consistent across the top-nav UserMenu, the Settings page, and the left-nav (no guest/OAuth split-brain).
- **FR-006**: The left-nav MUST remain responsive after navigating into and out of Settings with a restored OAuth session.
- **FR-007**: The backend refresh path MUST emit diagnostic logging that unambiguously distinguishes (a) refresh cookie absent, (b) refresh cookie present but Cognito rejected, (c) success — without logging secret token values (use existing `sanitize_for_log` / hash-prefix conventions).
- **FR-008**: The refresh cookie for OAuth sessions MUST continue to be sent by the browser on cross-site `/refresh` calls from the Amplify origin (verify the deployed cookie `Path`/`Domain`/`SameSite=None`/`Secure` against the real request path; correct only if a real mismatch is observed).
- **FR-009**: Any Cognito client/secret configuration correction MUST be delivered through the CI env-sync ("Step 2.5") or a manual live `update-function-configuration`, since Terraform cannot mutate the frozen dashboard Lambda env (Feature 1290). The change MUST be documented and verified against the live function config.
- **FR-010**: On an unrecoverable refresh (expired/revoked/invalid), the frontend MUST fall back to guest gracefully with no unresponsive UI and no console-visible unhandled rejection.
- **FR-011**: No new AWS resources may be introduced; the fix reuses the existing Cognito user pool, app client(s), dashboard Lambda, and DynamoDB tables.

### Security Requirements

- **SR-001**: The refresh token MUST remain httpOnly and MUST NEVER appear in a response body (preserve `exclude={"refresh_token_for_cookie"}`).
- **SR-002**: CSRF protection MUST remain intact: `require_csrf_middleware` still guards non-exempt state-changing routes; `/refresh` stays cookie-only and CSRF-exempt by design (`csrf.py:38`), and the CSRF cookie continues to rotate on refresh (`router_v2.py:684`).
- **SR-003**: `SameSite=None` MUST NOT be broadened beyond what cross-origin requires; the CSRF double-submit token remains the CSRF control that compensates for `SameSite=None`.
- **SR-004**: The refresh-token blocklist / eviction check MUST run BEFORE issuing new tokens (preserve `auth.py:2913-2924`), so revoked sessions cannot be resurrected via reload.
- **SR-005**: The `user_id` added to the refresh response (FR-002) MUST be the minimum identity needed for restore and MUST be derived server-side from validated tokens/session, never echoed from request input (guards against session fixation / identity spoofing).
- **SR-006**: Diagnostic logging (FR-007) MUST NOT log raw refresh tokens, id/access tokens, or full user identifiers; use hash prefixes and masking consistent with repo SAST rules (CWE-117/CWE-312).

### Key Entities

- **Refresh token (OAuth)**: real Cognito refresh token; lives only in the httpOnly `refresh_token` cookie; scoped to `{/stage}/api/v2/auth`.
- **RefreshTokenResponse**: backend response model (`auth.py:1504-1520`); must carry `user_id`/`auth_type` for the Cognito branch after this feature.
- **CognitoConfig**: `client_id`/`client_secret`/URLs from env (`cognito.py:44-56`); the suspected misconfiguration surface for Defect A.
- **Auth store (frontend)**: Zustand store; `restoreSession` (`auth-store.ts:102-198`) is the consumer that gates on `user_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the real Amplify frontend, after an owner-performed interactive Google login, `POST /api/v2/auth/refresh` returns **200** on page reload (was 401) — verified in the browser network panel / preprod, no mocks.
- **SC-002**: The reload keeps the session signed in as the Google user in **100%** of trials across at least 3 consecutive reloads.
- **SC-003**: Settings and the top-nav UserMenu show the **same** Google identity (0 guest/OAuth mismatches) after reload and after Settings navigation.
- **SC-004**: The left-nav remains responsive (all links clickable) after entering and leaving Settings, across at least 3 navigation cycles.
- **SC-005**: OAuth session persists across client-side navigation with no re-drop to guest for the token's validity window (≥ the Cognito access-token lifetime, e.g. 1 hour, on a single refresh cycle).
- **SC-006**: No security regression: existing CSRF, blocklist, and cookie-scope checks still pass; `/refresh` still 401s on absent/forged cookies and on blocklisted tokens.

## Assumptions

- The Google OAuth *login* itself works (task-confirmed): code exchange, user provisioning, and cookie SET on callback all succeed. Only *persistence via refresh* is broken.
- The refresh cookie is being SET correctly on the OAuth callback (unified helper), matching the working guest path. Whether it is being SENT on `/refresh` in the deployed topology is the one cookie-side item still to confirm at runtime (FR-008).
- The dashboard Lambda live env is authoritative and may differ from Terraform due to the Feature 1290 freeze.
- Owner performs the interactive Google login for verification; automated E2E cannot complete Google's consent screen.

## Out of Scope

- The HTMX admin dashboard (`src/dashboard/`) — this is the customer dashboard only.
- OAuth *login* flow changes (provider config, redirect URI, code exchange) beyond what refresh persistence needs.
- GitHub OAuth provider behavior (only incidentally covered; primary target is Google).
- Prod rollout (tracked separately, e.g. 1372); this feature targets fix + preprod verification.

---

## Adversarial Review #1

Attacked the spec as a pentester, a skeptical staff engineer, and a 3am on-call. Findings and resolutions below; all CRITICAL/HIGH self-resolved by editing the spec above.

| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| 1 | CRITICAL | Original prime suspect (cookie attributes) would have sent the whole feature down a dead end — cookies are already unified/fixed (WI-3 #928). Building the spec around a non-bug wastes the fix. | Rewrote the root-cause section to prove the cookie hypothesis is already resolved (cited `router_v2.py:179-194`, commit `0849559`) and re-anchored on the real chain (Defects A + B). |
| 2 | CRITICAL | Even a "fix the 401" spec would leave the bug live: the Cognito refresh response omits `user_id`, so `restoreSession` bails to guest on a 200. Single-defect framing fails the success criteria. | Added **Defect B** and **FR-002/FR-003**; made SC-002/SC-003 depend on both defects being fixed. |
| 3 | HIGH | "The cookie is not sent" vs "Cognito rejects the token" are different fixes with the same 401. Without disambiguation, implementers guess and thrash at 3am. | Added FR-007 (diagnostic logging that separates absent-cookie / Cognito-reject / success) and made it the first implementation task (see plan/tasks). |
| 4 | HIGH | `SameSite=None` widens CSRF surface; a naive fix could relax CSRF on `/refresh` "to make it work." | Added SR-002/SR-003: `/refresh` stays CSRF-exempt by design (cookie-only), CSRF double-submit remains the compensating control; forbid relaxing it. |
| 5 | HIGH | Session fixation / identity spoof: if `user_id` in the refresh response were sourced from client input, an attacker could pin another identity. | FR-003 + SR-005: `user_id` MUST be derived server-side from validated token claims / session, never from request input. |
| 6 | HIGH | Feature 1290 env freeze trap: a Cognito client/secret "fix" applied via Terraform silently never reaches the live Lambda; verification passes locally, prod stays broken. | FR-009 + Edge Case + Assumption: config corrections go via CI Step 2.5 / manual `update-function-configuration`, verified against live config. |
| 7 | MED | Revoked-session resurrection: reload could revive an evicted session if blocklist check is bypassed. | SR-004: preserve pre-issuance blocklist check (`auth.py:2913-2924`); added AC US3-2. |
| 8 | MED | Logging a refresh token while adding diagnostics (FR-007) would create a CWE-312 leak. | SR-006: hash-prefix/masking only, per repo SAST rules. |
| 9 | MED | Left-nav "unresponsive" is asserted but not mechanistically tied to the root cause — risk of treating it as a separate UI bug and mis-scoping. | Explained the one-chain mechanism ("Why three symptoms, one chain") and kept US2 acceptance focused on the shared restore failure, with a fallback-graceful requirement (FR-010). |
| 10 | LOW | Cognito not rotating the refresh token could be misread as "cookie lost," causing a spurious cookie-clear. | Edge case added; noted router already handles `refresh_token=None` (`router_v2.py:678`). |

**Post-resolution gate: 0 CRITICAL, 0 HIGH remaining.** Residual MED/LOW items are captured as requirements/edge cases and carried into the plan and tasks. The one genuinely runtime-only unknown (is the 401 cookie-absent or Cognito-reject?) is converted into a required first diagnostic step rather than left as an open question.

---

## Clarifications

Self-answered from the codebase/context (no human asked, per pipeline rules). Each records the question, the chosen answer, and the evidence source. Genuinely-unanswerable items are deferred to the final report.

### Session 2026-07-23

- **Q1: Should the core fix live in the backend (return `user_id`) or the frontend (`restoreSession` accept a `user_id`-less OAuth restore)?**
  **A: Backend.** `restoreSession` already implements the correct, secure contract — it needs a server-authoritative `user_id` and refuses to invent one (`frontend/src/stores/auth-store.ts:157-161`). The backend Cognito branch is the side that violates the contract by returning `None` (`src/lambdas/dashboard/auth.py:2934-2939`, model `auth.py:1515`). Fixing the backend keeps identity server-derived (SR-005) and requires no frontend change. Evidence: auth-store.ts:141-193; auth.py:1504-1520, 2934-2939.

- **Q2: Where does the OAuth `user_id` come from server-side so it is never client-supplied?**
  **A: From the refreshed id-token claims → internal user lookup.** `cognito_refresh_tokens` returns a fresh `id_token` (`cognito.py:270-274`); `decode_id_token` extracts `sub` (used at `auth.py:2228-2230` for the callback). Map `sub` → internal `user_id` via the existing `get_user_by_provider_sub(table, provider, sub)` helper (`auth.py:527`), using the provider from the id-token identity claim, and/or the `by_cognito_sub` GSI introduced by Feature 1222. NOTE (accuracy correction from AR#2): there is **no** `get_user_by_cognito_sub` function in `auth.py` today — the only sub-based lookup helper is `get_user_by_provider_sub` (`auth.py:527`); implementation must reuse it (adding a thin `by_cognito_sub` GSI query helper only if the provider is not recoverable at refresh time). This keeps identity server-authoritative (SR-005). Evidence: auth.py:527, 2228-2245; cognito.py:270-274. `refresh_access_tokens` already receives `table` on the live path (`router_v2.py:667-668`), so the lookup is available.

- **Q3: Is the 401 a CSRF rejection (403) misreported, or a genuine 401?**
  **A: Genuine 401 from the refresh handler.** `/api/v2/auth/refresh` is in `CSRF_EXEMPT_PATHS` (`src/lambdas/shared/auth/csrf.py:38`), and `require_csrf_middleware` returns 403 (not 401) on failure (`csrf_middleware.py:66-73`). So the observed 401 must come from `refresh_tokens()` at `router_v2.py:664` (cookie absent) or `:671` (Cognito error). Evidence: csrf.py:38; csrf_middleware.py:66-73; router_v2.py:663-671.

- **Q4: Does the fix require any Terraform/infra change, and how is a Cognito config correction delivered given the env freeze?**
  **A: No Terraform env change is possible; corrections go through the CI "Step 2.5" env-sync or a manual `update-function-configuration`.** The dashboard Lambda module carries `lifecycle { ignore_changes = [image_uri, environment] }` (Feature 1290), so Terraform cannot mutate `COGNITO_CLIENT_ID`/`COGNITO_CLIENT_SECRET`. Any correction must be applied via the deploy workflow env-sync and verified against `aws lambda get-function-configuration`. Evidence: research.md R4; task-provided ground truth (Feature 1290); FR-009.

- **Q5: Is a frontend change in scope for the MVP (US1/US2), or backend-only?**
  **A: Backend-only for the core fix; frontend is verification-only.** Once the backend returns `user_id`+`auth_type` for the Cognito branch, the existing `restoreSession` Cognito branch (`auth-store.ts:141-193`) completes without modification, and the guest-fallback that produced all three symptoms stops firing. The left-nav/UserMenu/Settings symptoms are downstream of the restore result, so they clear when restore succeeds. If preprod verification reveals a residual UI-only lockup after restore succeeds, that becomes a follow-up (deferred), not part of this MVP. Evidence: auth-store.ts:141-198; use-session-init.ts restore-first flow; spec "Why three symptoms, one chain".

**Deferred to owner (not codebase-answerable):**
- **D1**: The live value of `COGNITO_CLIENT_SECRET`/`COGNITO_CLIENT_ID` on the deployed dashboard Lambda and the app-client that Cognito Hosted UI used to issue the OAuth refresh token — required to confirm the Cognito-reject sub-cause of Defect A. Runtime-only.
- **D2**: Whether a custom domain / base-path mapping fronts the API Gateway on preprod (affects whether the stage-derived cookie `Path` matches the browser path, FR-008). Deployment-topology fact, runtime-only.
