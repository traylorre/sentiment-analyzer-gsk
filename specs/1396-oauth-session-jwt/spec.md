# Feature 1396: Mint First-Party App JWT for OAuth Sessions

**Status:** Draft (spec suite)
**Owner-decided approach:** Option B — HS256 first-party app JWT, minted now.
**Depends on:** Feature 1395 (oauth-account-integrity) for deterministic `get_user_by_cognito_sub`.
**Serializes with:** Feature 1395 (both edit `src/lambdas/dashboard/auth.py`).

---

## Root Cause (verified against current code)

The OAuth login path returns the **raw Cognito access token** as the frontend bearer, but the
API middleware only validates a **first-party app JWT** that nothing in the repo mints. Every
OAuth-authenticated request therefore fails validation and 401s, which drops the user to guest and
triggers a refresh/anonymous mint storm. This is the M1 blocker.

Evidence (file:line):

- No app JWT is ever minted. `jwt.encode` appears nowhere in the codebase. `_generate_tokens`
  (`src/lambdas/dashboard/auth.py:1979`) is mock-only and hard-blocked in Lambda — it raises
  `RuntimeError` when `AWS_LAMBDA_FUNCTION_NAME` is set (`auth.py:1994-2002`).
- OAuth callback returns the Cognito access token as the bearer. `handle_oauth_callback` builds
  `OAuthCallbackResponse.tokens = {"id_token": tokens.id_token, "access_token": tokens.access_token, ...}`
  where `tokens` comes from `exchange_code_for_tokens` (Cognito) — `auth.py:2218-2223`, response at
  `auth.py:2434-2453`.
- Refresh returns Cognito tokens the same way. `refresh_access_tokens` returns
  `RefreshTokenResponse(id_token=tokens.id_token, access_token=tokens.access_token, ...)` from
  `cognito_refresh_tokens` — `auth.py:2984`, response at `auth.py:3006-3012`.
- Middleware validates ONLY an app JWT. `validate_jwt` (`src/lambdas/shared/middleware/auth_middleware.py:133`)
  uses HS256 + `JWT_SECRET`, pins the algorithm via `algorithms=[config.algorithm]` (`:160`), requires
  `sub/exp/iat/nbf` (`:165`), validates `aud=JWT_AUDIENCE` (`:162,201`) and `iss=JWT_ISSUER`
  (default `"sentiment-analyzer"`, `:161,198`), **rejects any token missing a `roles` claim**
  (Feature 1153, `:172-178`), and supports `jti`/`rev` revocation (Feature 1186, `:182-183`). It is
  invoked at `:314` and `:368`. There is **no** Cognito/JWKS validation branch anywhere.
- The frontend sends `tokens.access_token` as the bearer:
  `frontend/src/lib/api/auth.ts:135` maps `accessToken: response.tokens.access_token`;
  `frontend/src/lib/api/client.ts:138` sets `Authorization: Bearer ${accessToken}`.

**Consequence:** A Cognito access token fails signature, `aud`, `iss`, and the `roles`-required
check simultaneously → 401 on every authenticated call.

## Decision: Option B (owner-confirmed)

Mint a first-party HS256 app JWT at the OAuth callback **and** on refresh, and return **that** as the
frontend bearer in place of the Cognito access token. The middleware is **unchanged** — the minted
token simply passes `validate_jwt`. Option A (teach the middleware to validate Cognito/JWKS tokens)
was rejected after 3-agent adversarial research and is **not** re-litigated here.

---

## User Stories

### US1 — OAuth user stays logged in (P0)
As a user who signs in with Google/GitHub, I want my session to work on every API call so I am not
silently dropped to guest and forced to re-authenticate.

**Acceptance:** After OAuth callback, the frontend bearer passes `validate_jwt`; authenticated API
calls (configs, alerts, notifications) return 200; no drop-to-guest; no anonymous-mint storm.

### US2 — Session survives refresh (P0)
As a signed-in OAuth user, when my short-lived app JWT expires, the refresh flow re-mints a fresh app
JWT from the httpOnly Cognito refresh cookie without me noticing.

**Acceptance:** `/api/v2/auth/refresh` returns a newly minted app JWT (not a Cognito token) that
passes `validate_jwt`; the rotated Cognito refresh token stays in the httpOnly cookie.

### US3 — Roles and revocation are honored (P1)
As the platform, I want the minted token to carry the user's real roles and revocation counter so RBAC
works and a force-revoked session cannot be silently kept alive across refreshes.

**Acceptance:** `roles` claim reflects the user's **authoritative** role state (see FR-002/N4); `rev`
equals `user.revocation_id` at mint time. **Honest revocation posture (N1):** the request-path
middleware does **not** compare `rev` per-request (`check_revocation_id` is uncalled in `src/` — dead
code), so there is **no instant per-request per-session kill**. Instead, force-revocation takes effect
**within one access-token TTL (≤15 min)** via a **refresh-time `rev` check**: refresh refuses to re-mint
when the user's `revocation_id` has advanced past the incoming session's `rev`. The only instant,
system-wide kill is rotating `JWT_SECRET` (mass logout).

### US4 — No new attack surface (P1)
As a security owner, I want minting a session credential to not open forgery, replay, alg-confusion,
stale-role, or CSRF holes.

**Acceptance:** Threat model below is covered by FRs; adversarial reviews close at 0 CRITICAL / 0 HIGH.

---

## Functional Requirements

### Minting
- **FR-001** A new helper `mint_app_jwt(user, *, now=None) -> str` MUST produce an HS256 JWT signed
  with `JWT_SECRET`, using the **same** env-sourced config as `validate_jwt`
  (`_get_jwt_config()` semantics): algorithm from `JWT_ALGORITHM` (default `HS256`), issuer from
  `JWT_ISSUER` (default `"sentiment-analyzer"`), audience from `JWT_AUDIENCE`. It MUST NOT hardcode
  these values and MUST NOT introduce a header-driven `alg`.
- **FR-002** The minted token MUST contain claims: `sub` = internal `user.user_id`;
  `aud` = `JWT_AUDIENCE`; `iss` = `JWT_ISSUER`; `roles` = `get_roles_for_user(user)`
  (`src/lambdas/shared/auth/roles.py:24`, a `list[str]`); `iat`; `nbf` = `iat`; `exp` = `iat + TTL`;
  `jti` = a fresh `uuid4` per mint; `rev` = `user.revocation_id`
  (`src/lambdas/shared/models/user.py:70`).
- **FR-002a (N4 — authoritative roles).** `get_roles_for_user` gates on **`user.auth_type`**
  (`roles.py:52`), **not** `user.role`. On the existing-user OAuth path, `_advance_role`
  (`auth.py:2628-2700`) writes the `role` field to **DynamoDB** but does **not** mutate the in-hand
  in-memory `user`, and does **not** advance `auth_type`. Minting naively from the in-hand user could
  therefore emit `roles=["anonymous"]` for a just-upgraded user (under-grant). The mint MUST source roles
  from the **authoritative current role state**: before calling `get_roles_for_user`, the caller MUST
  ensure the in-hand `user` reflects the persisted advancement (mutate `user.auth_type`/`user.role`
  in-memory to match what `_advance_role` persisted, OR re-read the user), so the minted `roles` cannot
  under-grant an upgraded user. Newly-created OAuth users already get `auth_type=<provider>`
  (`_create_authenticated_user`, `auth.py:2393` → non-anonymous → `["free"]`); the gap is only the
  existing-user upgrade path.
- **FR-003** TTL MUST be **900 seconds (15 minutes)** — see Decision Notes for justification. The value
  MUST be defined as a single named constant, not a magic number.
- **FR-004** `handle_oauth_callback` MUST replace the value returned in `tokens["access_token"]` with
  the minted app JWT (the frontend already treats `access_token` as the bearer). `id_token` handling is
  unchanged; the Cognito refresh token continues to flow via `refresh_token_for_cookie`
  (`auth.py:2445`). Mint MUST use the in-hand `user` object (no extra lookup).
- **FR-005** `refresh_access_tokens` MUST replace the returned `access_token` with a freshly minted app
  JWT (re-mint on every refresh) for the Cognito-backed branch. The anonymous branch
  (`refresh_token.startswith("anon.")`, `auth.py:2978`) is **out of scope** and MUST be untouched.
- **FR-006** If minting cannot resolve required inputs (e.g. `JWT_SECRET` unset), the callback/refresh
  MUST fail closed with an explicit auth error — **no silent fallback** to returning a Cognito token as
  the bearer (that would reintroduce the 401 storm invisibly).
- **FR-006a (N3 — transient vs definitive).** The refresh identity-resolution block (`auth.py:2991-3005`)
  currently catches a **bare `Exception`** and degrades. "Fail closed" MUST distinguish failure classes,
  because collapsing every failure to 401 lets a **transient** fault (DynamoDB throttle/timeout, a
  `get_user_by_cognito_sub` GSI error) force re-login, and the 15-min refresh cadence amplifies that into
  broad logouts:
  - **Definitive unresolved identity** (Cognito refresh succeeded but `decode_id_token` yields no `sub`,
    or `get_user_by_cognito_sub` deterministically returns `None`) → **401** (`error="identity_unresolved"`);
    the session genuinely cannot be minted.
  - **Retryable/transient failure** (DynamoDB `ClientError`/throttle/timeout, or any infrastructure
    exception during lookup) → **503** (`error="identity_unavailable"`, retryable); the frontend retries
    and the session is **preserved**, NOT dropped to guest.
  The Cognito refresh itself already succeeded, so a transient DB fault is not evidence of a bad session.
  The revoked-token (`token_revoked`, `auth.py:2971`) and Cognito `TokenError` paths are unchanged.

### Middleware compatibility (no change)
- **FR-007** The minted token MUST pass the existing `validate_jwt` unchanged: satisfy the
  `require: [sub, exp, iat, nbf]` option, present a non-`None` `roles` claim (Feature 1153 gate,
  `auth_middleware.py:172-178`), and match `aud`/`iss`. `validate_jwt` MUST NOT be edited by this
  feature.
- **FR-008 (revised — N1: honest revocation posture).** The minted token MUST carry
  `rev = user.revocation_id` (well-formed, so a future per-request check or blocklist could use it). The
  spec MUST NOT claim instant per-request revocation, because `check_revocation_id`
  (`auth_middleware.py:223`) is **dead code** — it has **zero call sites in `src/`** (only in tests), and
  the request auth path (`extract_auth_context_typed` → `validate_jwt`, `auth_middleware.py:368`) extracts
  `JWTClaim.rev` but **never compares it** to the user's `revocation_id`. Wiring
  `check_revocation_id` into the middleware is **rejected** here: it would violate the middleware-unchanged
  guardrail (FR-007) and add a per-request DynamoDB read.
  Instead, revocation is enforced at **refresh time**: after resolving the user,
  `refresh_access_tokens` MUST compare the **incoming session's `rev`** against the freshly-read
  `user.revocation_id`, and **refuse to re-mint** (fail closed, `error="session_revoked"`, 401) if the
  user's `revocation_id` has advanced past the incoming `rev`.
  - **Source of the incoming `rev` (buildable):** the frontend's shared api client attaches
    `Authorization: Bearer <expiring app JWT>` to `POST /api/v2/auth/refresh` (`client.ts:138`;
    the same closure token used on every call). The refresh route (`router_v2.py:639`) currently reads
    only the refresh cookie, so this feature MUST plumb the `Authorization` bearer through to
    `refresh_access_tokens`. The helper decodes that app JWT **signature-verified with `verify_exp=False`**
    (it is expected to be expired — that's why we're refreshing) using the same `_get_jwt_config()`
    secret, and reads its `rev`. A bearer that fails signature verification is ignored (treated as absent).
  - **Backward-compat / bearer-absent (migration window ONLY — AR1-12):** if no valid app-JWT bearer
    accompanies the refresh, the `rev` check is **skipped** (mirrors `check_revocation_id`'s `None`
    handling). This skip is attacker-controllable (omit the header, bypass revocation forever), so it is
    a **temporary migration accommodation**, not a permanent posture: task **T033** makes a
    signature-valid bearer REQUIRED on the Cognito-backed refresh branch (401 `bearer_required`) once
    the deployed frontend is verified to always attach it. Recorded in AR#1 Addendum (AR1-12).
  This bounds a force-revoked session to at most **one access-token TTL (≤15 min)** with **no per-request
  cost** (refresh already does the user lookup). There is no instant per-session kill short of rotating
  `JWT_SECRET` (mass logout).
  **Owner-surface decision OQ-4** (see Deferred): confirm this refresh-time-check posture is acceptable
  vs. the stronger (rejected) option of wiring `check_revocation_id` into the middleware.

### Algorithm & secret hygiene
- **FR-009** Algorithm pinning: mint MUST use exactly the algorithm `validate_jwt` pins
  (`config.algorithm`, single-element `algorithms=[...]`). No `none`, no RS/HS confusion, no
  per-request algorithm selection.
- **FR-010** Trust-boundary assumption (verified): the SSE Lambda does **not** validate app JWTs
  (grep-confirmed), so a single symmetric secret shared within one trust boundary is acceptable for
  HS256. This assumption MUST be recorded. **REQUIREMENT:** if a second independent verifier of the app
  JWT is ever introduced, the mint MUST migrate to an asymmetric algorithm (RS256) so the verifier
  cannot also forge. That migration is a **carded follow-up, OUT of scope** here.
- **FR-011** Prod secret hygiene: the live preprod `JWT_SECRET` is the **shared E2E test secret**
  (`infrastructure/terraform/preprod.tfvars` — "must match `PREPROD_TEST_JWT_SECRET`", Feature 1054
  comment block). ~~acceptable for **preprod only**~~ **SUPERSEDED by FR-011a — no longer acceptable
  for preprod either.** Because the app JWT is now the real OAuth session credential, **PROD MUST use a
  strong, non-test `JWT_SECRET` sourced securely** (via `TF_VAR_jwt_secret`, never committed). This is an
  **owner action item** and MUST NOT be assumed done. A spec note flags it.
- **FR-011a (RIDER a — PREPROD-BLOCKING).** The app JWT signing secret in **preprod** MUST be a
  distinct, non-test secret: high-entropy, NOT the committed default
  (`test-jwt-secret-for-e2e-only-not-production`), and NOT any value recorded in the repo, docs, or
  public CI logs. Rationale: preprod is where **M1 verifiable-auth evidence is sealed**
  (`docs/cleanup-pristine/evidence/m1/`); with a known/test secret, anyone can forge the `roles` claim
  and the attestation is invalid. This is **PREPROD-BLOCKING**, not prod-only: the secret MUST be
  rotated and **verified before any M1 seal evidence is captured** for this feature. E2E signing
  parity, if still required, MUST come from the same CI secret store (`TF_VAR_jwt_secret` /
  `PREPROD_TEST_JWT_SECRET` both fed the new value), never a committed constant. Rotating the secret
  invalidates all outstanding app JWTs (mass logout) — acceptable in preprod; schedule accordingly.
  Task: T004 (deploy gate).

### CSRF (double-submit, Feature 1158)
- **FR-012** The OAuth callback's CSRF protection is the OAuth `state` nonce
  (`validate_oauth_state`, `auth.py:2188`) — the callback is deliberately double-submit-exempt
  (`csrf.py:47-49`). This existing protection MUST be preserved; the mint MUST NOT weaken it.
- **FR-013 (revised — N2: body-delivered CSRF token).** The refresh endpoint is currently
  double-submit-**exempt** (`csrf.py:38`) AND its refresh cookie is `SameSite=None` (Feature 1159,
  cross-origin Amplify→API). Because refresh now mints the **real session credential**, refresh MUST be
  CSRF-protected. **The naive "read `X-CSRF-Token` from the `csrf_token` cookie" approach is INFEASIBLE
  cross-origin:** the `csrf_token` cookie is set on the **API domain** with `SameSite=None`
  (`router_v2.py:166-174`); the frontend runs on **Amplify** (different registrable domain), so
  `document.cookie` on Amplify **cannot read** the API-domain cookie, and there is **zero** `X-CSRF-Token`
  handling in `frontend/src` today (all CSRF refs are OAuth `state`). Removing the exemption without a way
  to source the header would then **403 every refresh → mass logout**.
  **Mechanism (buildable), body-delivered token:**
  1. The callback and refresh JSON responses MUST **return the CSRF token value in the response body**
     (the same value written to the `csrf_token` Set-Cookie; today `_make_csrf_set_cookie` generates the
     value internally, so the handler MUST generate it once and put it in **both** the cookie and the
     body). The legitimate frontend, being same-origin with its own app, reads the body via CORS; a
     cross-site attacker's opaque `fetch` **cannot** read the body (CORS) nor the cookie (cross-domain).
  2. The frontend stores that token **in memory** and echoes it as `X-CSRF-Token` on the next
     `POST /api/v2/auth/refresh`.
  3. The backend validation is **unchanged**: `require_csrf_middleware` → `validate_csrf_token(cookie,
     header)` (`csrf.py:64`) compares the `X-CSRF-Token` header against the **auto-attached** `csrf_token`
     cookie (the browser sends the API-domain cookie server-side even though JS can't read it) via
     `hmac.compare_digest`. The only change is that the frontend can now supply a matching header value
     because it learned it from the body.
  Remove `"/api/v2/auth/refresh"` from `CSRF_EXEMPT_PATHS` **after** the frontend ships steps 1-2
  (deploy-order gate, OQ-2). Callback stays exempt — protected by the OAuth `state` nonce (FR-012). The
  CSRF cookie is already re-issued on both callback and refresh (`router_v2.py:626,701`).
- **FR-013a (RIDER b — ordered-deploy constraint, HARD GATE).** The frontend CSRF-echo change (read
  body `csrf_token`, send `X-CSRF-Token` on refresh — T041) MUST be **deployed and verified LIVE on
  Amplify** before the backend exemption removal (T042) deploys. "Merged before" is NOT sufficient —
  the gate is on **live traffic**: until every active client echoes the header, dropping the exemption
  403s every refresh and **logs out every existing user** on deploy. T042 carries an explicit
  pre-deploy checklist item: confirm the Amplify build containing T041 is serving, then deploy T042 in
  a separate, later deploy cycle (never the same cycle unless the owner explicitly accepts the risk
  window). Rollback path: re-adding the exempt path is a one-line revert.

### Frontend
- **FR-014** Confirmed: the frontend uses `tokens.access_token` as the bearer
  (`auth.ts:135` → `client.ts:138`). Because FR-004/FR-005 replace the **value** of that field, **no
  frontend change is required for the bearer itself.** The required frontend changes are FR-013's CSRF
  mechanism: (a) read the body-delivered CSRF token from the callback **and** refresh responses and hold
  it in memory; (b) echo it as `X-CSRF-Token` on the next `POST /api/v2/auth/refresh`. The frontend does
  **not** read the `csrf_token` cookie (it cannot, cross-domain — N2). These MUST be explicit coordinated
  tasks and MUST ship **before** the backend removes the refresh CSRF exemption (OQ-2).

### Dependency
- **FR-015** The refresh path resolves `user_id` via `get_user_by_cognito_sub`
  (`auth.py:2995`); the minted `sub` is only trustworthy if that lookup is deterministic. This feature
  **depends on Feature 1395** (dedup + footgun fix) for the refresh-mint's `sub`. The **callback path
  already holds the resolved `user` object** (`auth.py:2361-2417`), so callback-mint does **not** depend
  on the lookup and may ship independently of 1395 for that path. If refresh cannot deterministically
  resolve the user, it MUST fail closed (FR-006), not mint a token with an ambiguous `sub`.
- **FR-015a (serialization constraint — auth.py merge hotspot, verified this session).** 1395 is a WIP
  commit on the current branch (`71cb143 wip(1395): identity GSI pagination + canonical-user resolution
  — KNOWN DEFECTS, DO NOT MERGE`) and has **already shifted `auth.py` line numbers**: the callback
  response block this spec cites as `auth.py:2434-2453` (1396 T021's edit target) now sits at
  **~2568-2581**; the refresh identity block cited as `2991-3005` now sits at **~3118-3140**;
  `get_user_by_cognito_sub` is defined at `:3040` with the callback-side lookup at `:2373`. 1395's
  rewrite covered the `~2359-2402` (pre-shift) identity-resolution region — directly upstream of 1396's
  edit sites. **Constraint:** all 1396 `auth.py` line references MUST be re-anchored against the merged
  1395 tree before implementation; Phase 3 (refresh re-mint) serializes strictly AFTER 1395 merges;
  Phase 2 (callback mint) may proceed but must rebase onto 1395's branch state to avoid a semantic
  merge conflict in the callback region.

---

## Success Criteria

- **SC-001** A minted callback token, passed as `Authorization: Bearer`, is accepted by `validate_jwt`
  and yields `AuthType.AUTHENTICATED` with the user's roles.
- **SC-002** A raw Cognito access token, passed as bearer, is **rejected** by `validate_jwt` (regression
  lock — proves the fix and prevents reverting to the broken state).
- **SC-003** Refresh returns a token whose `iat` is newer than the prior mint and which also passes
  `validate_jwt` (re-mint proven).
- **SC-004 (revised — N1)** After incrementing `user.revocation_id`, a refresh carrying the previously
  minted app JWT (with the now-stale `rev`) is **refused** (`error="session_revoked"`, 401) — the session
  is not re-minted. The request-path middleware is unchanged and performs **no** per-request `rev` check
  (regression note: `check_revocation_id` remains uncalled in `src/`).
- **SC-007 (N3 — transient vs definitive)** A refresh where the user lookup raises a transient DynamoDB
  fault returns **503** (`identity_unavailable`, retryable) and does **not** drop the session; a refresh
  where identity is definitively unresolved (no `sub` / deterministic `None`) returns **401**
  (`identity_unresolved`).
- **SC-005** OAuth login end-to-end no longer drops to guest; no anonymous-mint storm in logs.
- **SC-006** `/api/v2/auth/refresh` rejects a request lacking valid CSRF material per the FR-013
  mechanism.

---

## Edge Cases

- `JWT_SECRET` unset in an environment → fail closed (FR-006), never emit an unsigned or Cognito bearer.
- `JWT_AUDIENCE` unset → `validate_jwt` treats audience as `None`; mint MUST match (omit `aud` only if
  audience is `None`, otherwise the token would fail its own validation). Keep mint and validate reading
  the identical env var.
- Clock skew: `validate_jwt` allows 60s leeway (`auth_middleware.py:103,163`). `nbf = iat` is safe within
  that leeway; do not set `nbf` in the future.
- User with no roles / anonymous upgrade in flight → `get_roles_for_user` returns at least `["free"]`
  for authenticated users; never emit an empty/`None` roles claim (would fail the 1153 gate). **N4:**
  because `get_roles_for_user` reads `auth_type` (not `role`) and `_advance_role` mutates neither the
  in-memory user's `auth_type`/`role`, the caller MUST refresh the in-hand user's state (or re-read)
  before minting so a just-upgraded existing user does not under-grant `["anonymous"]` (FR-002a).
- Refresh where `get_user_by_cognito_sub` returns `None` (pre-1395 ambiguity) → **definitive** → 401
  (`identity_unresolved`). A DynamoDB throttle/timeout during the same lookup → **transient** → 503
  (`identity_unavailable`, retryable, session preserved) — FR-006a / N3.
- Long-lived tab: app JWT expires every 15 min; refresh re-mints. Stale roles bounded by TTL. Revocation
  is **not** instant per-request (N1): a force-revoked session is refused at the next refresh, bounding it
  to ≤15 min; the request-path middleware performs no `rev` check.
- Refresh with no valid app-JWT bearer on the `Authorization` header → the refresh-time `rev` check is
  skipped (backward-compat), so that single refresh cannot detect revocation (FR-008 limitation).

---

## Threat Model

| # | Threat | Vector | Mitigation (FR) |
|---|--------|--------|-----------------|
| T1 | **Forged token if secret leaks** | Attacker with `JWT_SECRET` mints arbitrary `sub`/`roles` | HS256 shared-secret is the whole trust root → **prod must use a strong, non-test secret** (FR-011); trust-boundary recorded (FR-010); RS256 migration carded if a 2nd verifier appears |
| T2 | **Algorithm confusion** (`alg:none`, HS/RS swap) | Attacker rewrites header `alg` | `validate_jwt` pins `algorithms=[config.algorithm]`; mint uses the same pinned algorithm, no header-driven alg (FR-009) |
| T3 | **Replay** of a captured bearer | Steal token, reuse until exp | Short 15-min TTL (FR-003) bounds the window; `jti` present for future blocklisting; `rev` bump forces refusal at the next refresh (≤15 min), **not** instant per-request (N1, FR-008) |
| T4 | **Stale roles** baked into token | User downgraded but old token still grants access | TTL bounds staleness to ≤15 min (FR-003); a `rev` bump refuses re-mint at the next refresh (≤15 min, FR-008); no instant per-request revocation (N1) |
| T5 | **CSRF** on refresh re-mint | `SameSite=None` refresh cookie auto-attached cross-site triggers silent re-mint | Body-delivered CSRF token echoed as `X-CSRF-Token`, validated by unchanged double-submit (FR-013 / N2); attacker can read neither the body (CORS) nor the API-domain cookie (cross-domain); callback covered by OAuth `state` (FR-012) |
| T6 | **Token-in-URL** leakage | Bearer ends up in query string / referer / logs | Bearer travels only in the `Authorization` header and JSON body over TLS; refresh token stays httpOnly; no token logged (existing `refresh.success` logs only `auth_type`) |
| T7 | **XSS exfil of bearer** | Script reads the in-memory bearer | Out-of-scope structural mitigation, but short TTL (FR-003) + `rev` revocation (FR-008) bound damage; refresh token is httpOnly (unreachable by JS) |
| T8 | **Ambiguous `sub`** from non-deterministic lookup | Refresh mints a token for the wrong user | Depends on Feature 1395 (FR-015); fail closed if lookup is ambiguous (FR-006) |
| T9 | **GAP-1 SSE raw-identity acceptance** (deferred surface) | Deferred SSE config-stream path accepts ANY bearer string as `user_id` unvalidated | **No work scheduled here** — see the Risk Note below. Flagged so the eventual GAP-1 fix validates the app JWT; SSE path is deferred, never deleted (owner constraint) |

---

## Risk Note — GAP-1 SSE Interaction (RIDER c — recorded, NO work scheduled)

The deferred, unauthenticated SSE config-stream path treats the bearer as a **raw identity string**:
`src/lambdas/sse_streaming/handler.py:365-369` assigns `user_id = bearer_token` with **no validation**
(verified this session; `X-User-ID` header and `user_token` query param fall through the same way at
`:371-377`). This is the **GAP-1 IDOR**, carded CRITICAL-deferred.

**What 1396 changes about that surface:** nothing in code — FR-010's grep-verified assumption (SSE does
not validate app JWTs) still holds, and this feature touches no SSE file. But 1396 makes the surface
**concretely exploitable-by-format**: the minted app JWT is now the one bearer the frontend holds and
attaches everywhere, its payload is base64-decodable by anyone who sees it (JWT payloads are encoded,
not encrypted), and it advertises a real internal `user_id` in `sub`. Any leak of any app JWT hands an
attacker a valid victim `user_id` to present, raw, to the SSE path — which will accept it as identity.
The token designed to be safe-if-captured (15-min TTL, signature-gated) is fully impersonation-capable
against GAP-1 because GAP-1 never checks the signature.

**Constraints recorded for the eventual GAP-1 fix (owner: SSE is DEFERRED, NEVER DELETED):**
1. The fix MUST validate the app JWT on the SSE path (signature, `exp`, `aud`/`iss`, `sub`-derived
   identity) — not merely rename or hide the raw-identity parameters.
2. Validating there makes the SSE Lambda a **second independent verifier** of the app JWT, which trips
   FR-010's trigger: the mint MUST migrate to RS256 (or the SSE verifier must be prevented from holding
   forgery-capable key material). The GAP-1 fix and the RS256 migration card are therefore coupled.
3. Do NOT propose deleting or disabling the SSE path as the remediation.

---

## Adversarial Review #1

Attacked as: state-sponsored actor (has read access to a leaked CI env), a pentester with a valid
guest session, and a 3am on-call engineer staring at a 401 storm.

### Findings

| ID | Sev | Attack / Gap | Resolution |
|----|-----|--------------|------------|
| AR1-1 | CRITICAL | **Test secret in prod.** If prod ships with the shared E2E `JWT_SECRET`, anyone who has read the public-ish test secret can forge `sub`+`roles`+`operator` and own every account. HS256 makes the secret the entire trust root. | FR-011 makes a strong non-test prod secret a **hard requirement + owner action item**, explicitly not assumed done. Added SC/deploy-gate language: prod deploy MUST NOT reuse `PREPROD_TEST_JWT_SECRET`. Threat T1. |
| AR1-2 | HIGH | **Roles claim shape mismatch.** If mint sets `roles` to a string, a dict, or `[]`, `validate_jwt` behavior diverges: `[]` is falsy-but-not-`None` so it *passes* the 1153 gate yet grants nothing; a non-list breaks downstream RBAC. | FR-002 pins `roles = get_roles_for_user(user)` which is the canonical `list[str]` the middleware consumers already expect; edge case added forbidding empty/`None`. Tasks include an assertion that the minted `roles` deep-equals `get_roles_for_user(user)`. |
| AR1-3 | HIGH | **exp too long.** A 60-min TTL (Cognito's `expires_in`) would leave a downgraded/abused session valid for an hour. | FR-003 fixes TTL at 15 min and requires a named constant; T4/T3 reference it. ~~`rev` gives instant revocation regardless of TTL.~~ **Corrected by N1 (AR#4):** `rev` is not enforced per-request; revocation takes effect at the next refresh (≤15 min), so the 15-min TTL is what actually bounds a revoked session. |
| AR1-4 | HIGH | **Refresh-failure path leaks a Cognito bearer.** A naive "if mint fails, fall back to Cognito token" would silently reintroduce the 401 storm and, worse, hand out a token the middleware rejects — invisible breakage. | FR-006 mandates **fail closed**, no silent fallback. AR gate confirms no fallback branch is specified. |
| AR1-5 | HIGH | **CSRF gap on refresh.** Refresh cookie is `SameSite=None` (Feature 1159) and refresh is double-submit-exempt (`csrf.py:39`). Under Option B, a cross-site page can silently drive a re-mint. Cross-origin *read* of the new bearer is blocked by CORS, but login/silent-CSRF and cookie-rotation abuse remain. | FR-013 requires closing this + a task + explicit frontend coordination. **Mechanism refined by N2 (AR#4):** cookie-read double-submit is infeasible cross-origin, so FR-013 now uses a body-delivered token (same server-side double-submit comparison). Threat T5. |
| AR1-6 | MEDIUM | **Does replacing the bearer break an existing Cognito-token consumer?** If any server path expected the returned `access_token` to be a real Cognito token (e.g. calling a Cognito API with it), the swap breaks it. | Verified: the returned `access_token` is consumed **only** as the API bearer (`client.ts:138`); `sign_out` uses its own Cognito access token path, not the response field. Recorded as a plan finding; a task greps for any other consumer before merge. |
| AR1-7 | MEDIUM | **Clock skew / nbf.** If mint sets `nbf` slightly in the future (e.g. rounding up), tokens 401 immediately for clients whose clock lags. | Edge case + FR-002 set `nbf = iat`; `validate_jwt` already tolerates 60s leeway. No future-dated `nbf`. |
| AR1-8 | MEDIUM | **iss mismatch.** `JWT_ISSUER` is **not set** in the Lambda env (verified — `main.tf` sets only `JWT_SECRET`/`JWT_AUDIENCE`), so `validate_jwt` uses the default `"sentiment-analyzer"`. A mint that hardcodes a different issuer, or reads a differently-defaulted env, self-rejects. | FR-001 requires mint to reuse the identical `_get_jwt_config()` env+defaults (issuer default `"sentiment-analyzer"`). Task asserts round-trip iss match. |
| AR1-9 | LOW | **aud omission divergence.** If `JWT_AUDIENCE` is unset in some env, mint must not emit an `aud` the validator won't check (or vice-versa). | Edge case: mint and validate read the same env var; `aud` included iff audience is non-`None`. Preprod/prod both set `jwt_audience`, so this is a defensive-only case. |
| AR1-10 | LOW | **jti collision / reuse.** Reusing a `jti` across mints would undermine future blocklisting. | FR-002 requires a fresh `uuid4` per mint. |

### Gate

All CRITICAL and HIGH findings resolved into FR-002/003/006/009/011/013 and recorded edge cases.
**0 CRITICAL, 0 HIGH remaining.** Proceed to plan.md.

## Clarifications

Self-answered from the codebase where determinable; genuinely open items deferred to owner.

**Q1 — What exact shape does `validate_jwt` require for `roles`, and does `get_roles_for_user` match?**
Answered. `validate_jwt` only rejects when `roles is None` (`auth_middleware.py:172-178`); any
non-`None` value passes the gate and is surfaced as `AuthContext.roles`. `get_roles_for_user`
(`roles.py:24`) returns a `list[str]` (e.g. `["free"]`, `["free","paid"]`). Using it satisfies the gate
and gives downstream RBAC the expected list. Empty list would pass the gate but grant nothing — forbidden
by the edge cases.

**Q2 — Is `JWT_ISSUER` set in the Lambda environment?**
Answered: **No.** `main.tf:489-491` sets only `JWT_SECRET` and `JWT_AUDIENCE` on the dashboard Lambda.
Both mint and validate therefore fall back to the default issuer `"sentiment-analyzer"`
(`auth_middleware.py:127`). Mint must reuse the same default (FR-001) or tokens self-reject (AR1-8).

**Q3 — Where does `rev` come from and how is it revoked?**
Answered. `rev` = `user.revocation_id` (`user.py:70`), incremented on password change / force
revocation. **⚠ SUPERSEDED BY N1 (AR#4):** the original answer assumed `check_revocation_id`
(`auth_middleware.py:223`) enforces this per-request — it does **not** (dead code, uncalled in `src/`).
Revocation is instead enforced at **refresh time** (revised FR-008). Mint still always sets `rev` so the
refresh-time check (and any future blocklist) has a well-formed value.

**Q4 — Which token field does the frontend actually send as the bearer?**
Answered: `access_token`. `auth.ts:135` → `accessToken`; `client.ts:138` → `Authorization: Bearer`.
`id_token` is stored but not sent as the bearer. So the mint replaces `access_token` (FR-004/FR-014).

**Q5 — Is the refresh endpoint currently CSRF-protected?**
Answered: **No.** `/api/v2/auth/refresh` is in `CSRF_EXEMPT_PATHS` (`csrf.py:38`) and its cookie is
`SameSite=None` (Feature 1159). This is the gap FR-013 closes — via a **body-delivered** token (N2), not
a cookie-read token, because the `csrf_token` cookie sits on a different registrable domain than the
Amplify frontend and is unreadable by its JS.

**Q6 — Is `rev`-based revocation actually enforced anywhere today? (N1)**
Answered: **No — it is dead code.** `check_revocation_id` (`auth_middleware.py:223`) has **zero call
sites in `src/`** (tests only); the request auth path (`extract_auth_context_typed` → `validate_jwt`,
`:368`) never compares `rev`. So the running system has no per-request revocation. FR-008 is revised to
an honest refresh-time check (≤15-min bound) rather than claiming instant revocation.

### Deferred to owner
- **OQ-1 (FR-011, ESCALATED by FR-011a):** Confirm prod `JWT_SECRET` is a strong, non-test value
  distinct from `PREPROD_TEST_JWT_SECRET`, and how/when it is rotated. **Rider (a) escalation: the
  PREPROD secret is now also in scope and PREPROD-BLOCKING** — rotate before any M1 seal evidence is
  captured (FR-011a, T004). Remaining owner input: rotation timing (mass-logout window) and whether E2E
  keeps signing parity via the CI secret store or moves to a login-flow token source.
- **OQ-2 (FR-013 deploy order):** Confirm the frontend `X-CSRF-Token`-on-refresh change can ship in
  lockstep with the exemption removal, or whether the backend change must be gated behind the frontend
  deploy to avoid a lockout window.
- **OQ-3:** Should `jti` be persisted for active blocklisting now, or is TTL+`rev` sufficient for this
  feature (blocklisting carded separately)? Recommended: defer; TTL+`rev` is adequate here.
- **OQ-4 (FR-008 — revocation posture, N1):** Confirm the **refresh-time `rev` check** posture is
  acceptable — force-revocation takes effect within one access-token TTL (≤15 min), with no instant
  per-request per-session kill short of rotating `JWT_SECRET` (mass logout). The stronger alternative —
  wiring the currently-dead `check_revocation_id` into the request middleware — is **rejected** here
  because it violates the middleware-unchanged guardrail (FR-007) and adds a per-request DynamoDB read.
  Owner decision required before the refresh phase lands.

---

## Adversarial Review #4 (Independent Refuter Resolution)

An independent security refuter attacked the AR#1-#3 spec suite and CONFIRMED five findings. Each was
re-verified against the running code this session (file:line cited) and resolved below. The owner-decided
Option B approach (mint a first-party HS256 app JWT at callback + refresh) is **unchanged**; the
middleware-unchanged guardrail (FR-007) is **intact**.

| # | Sev | Finding (verified) | Resolution | FR / task changed |
|---|-----|--------------------|------------|-------------------|
| N1 | HIGH | **`rev` revocation is dead code.** `check_revocation_id` (`auth_middleware.py:223`) has **zero call sites in `src/`** (tests only); the request path (`extract_auth_context_typed` → `validate_jwt`, `:368`) extracts `JWTClaim.rev` but never compares it. "Instant revocation via `rev`" does not exist in the running system. | Keep the token carrying `rev = user.revocation_id` (well-formed). Do **not** claim instant revocation. Add a **refresh-time `rev` check**: `refresh_access_tokens` decodes the expiring app JWT from the `Authorization` bearer (`verify_exp=False`), compares its `rev` to the freshly-read `user.revocation_id`, and refuses to re-mint (`session_revoked`) if advanced → bounds a force-revoked session to ≤15 min with no per-request cost and no middleware edit. Wiring `check_revocation_id` into the middleware is rejected (violates FR-007 + adds per-request DB read). Surfaced as **OQ-4**. | US3, FR-008 (rewritten), SC-004 (rewritten), edge cases, T3/T4; new **OQ-4**; tasks T010/T031/T032 |
| N2 | HIGH | **CSRF double-submit is infeasible cross-origin.** The `csrf_token` cookie is on the API domain, `SameSite=None` (`router_v2.py:166-174`); the Amplify frontend (different registrable domain) cannot `document.cookie`-read it, and there is **zero** `X-CSRF-Token` handling in `frontend/src`. Removing the exemption as-specified would 403 every refresh → mass logout. | Re-scope FR-013 to a **body-delivered CSRF token**: callback/refresh responses return the same token value that is set in the `csrf_token` cookie; the frontend holds it in memory and echoes it as `X-CSRF-Token`. Backend validation is **unchanged** — `validate_csrf_token(cookie, header)` (`csrf.py:64`) still compares the header against the browser-auto-attached cookie via `hmac.compare_digest`. Attacker reads neither body (CORS) nor cookie (cross-domain). Deploy-order (frontend first) preserved. | FR-013 (rewritten), FR-014 (updated), SC-006, T5, Q5; plan §4; tasks T040/T041/T042 |
| N3 | MED | **Fail-closed inversion conflates transient vs definitive.** The refresh identity block catches a **bare `Exception`** and degrades (`auth.py:2991-3005`); turning all of that into 401 lets a DynamoDB throttle or swallowed `decode_id_token` error force re-login, amplified by the 15-min cadence. | Split: **definitive** unresolved identity (no `sub` / deterministic `None`) → **401** (`identity_unresolved`); **transient** fault (DynamoDB `ClientError`/throttle/timeout) → **503** (`identity_unavailable`, retryable, session preserved). Cognito refresh already succeeded, so a transient DB fault is not a bad session. | new **FR-006a**, SC-007, edge cases; plan §3; tasks T030/T031 |
| N4 | LOW-MED | **Roles from wrong field + circular test.** `get_roles_for_user` gates on `user.auth_type` (`roles.py:52`), not `user.role`; `_advance_role` (`auth.py:2628-2700`) writes DDB `role` but mutates neither the in-memory `user.auth_type`/`role` → an existing anonymous-upgrade user could mint `roles=["anonymous"]` (under-grant). Test T010 asserted `== get_roles_for_user(user)` (tautology). | new **FR-002a**: mint sources roles from the **authoritative** current state — ensure the in-hand user reflects the persisted advancement (mutate in-memory or re-read) before `get_roles_for_user`. De-tautologize **T010**: assert **literal** expected role lists per user state (`["anonymous"]` pre-upgrade, `["free"]` post-upgrade / new OAuth user, `["free","paid"]`, `["free","paid","operator"]`), not `== get_roles_for_user(user)`. | new **FR-002a**, edge cases; tasks T010 (rewritten) |
| N5 | LOW | **`auth.py` must `import jwt`** — PyJWT is imported only in `auth_middleware.py:19`; `auth.py` imports `map_stripe_plan_to_role` but not `jwt` nor `get_roles_for_user`. | Note added: `mint_app_jwt` requires `import jwt` (PyJWT) and `from src.lambdas.shared.auth.roles import get_roles_for_user` in `auth.py`. Covered by T011. | plan §1; tasks T011 |

**Gate:** N1-N5 resolved into US3 / FR-002a / FR-006a / FR-008 (rewritten) / FR-013 (rewritten) / FR-014,
SC-004/006/007, edge cases, threat model, and new OQ-4. Middleware-unchanged guardrail (FR-007) intact —
the revocation and CSRF fixes live entirely in the callback/refresh handlers and the frontend.
**0 CRITICAL, 0 HIGH remaining.** Ready for implementation pending owner decisions **OQ-1** (prod
secret), **OQ-2** (CSRF deploy lockstep), **OQ-4** (refresh-time revocation posture).

---

## Adversarial Review #1 — Addendum (rider reconciliation pass)

Re-attacked the JWT design after folding in riders (a)-(c): algorithm confusion, TTL-vs-revocation
lag, clock skew, secret rotation, replay. Prior AR findings re-checked against the current tree
(1395 WIP `71cb143` present on branch).

| ID | Sev | Attack / Gap | Resolution |
|----|-----|--------------|------------|
| AR1-11 | CRITICAL | **Preprod attestation forgery.** AR1-1 gated the test-secret risk as prod-only, but M1 verifiable-auth evidence is sealed FROM PREPROD (`docs/cleanup-pristine/evidence/m1/` — wi1/wi3/wi5/wi6 already present). With `JWT_SECRET` = the committed E2E default, anyone can mint an arbitrary `roles`/`sub` token in preprod, so any sealed evidence claiming "roles are cryptographically bound" is false at capture time. | **Self-resolved: FR-011a (PREPROD-BLOCKING)** — distinct high-entropy secret in preprod, rotated and verified BEFORE any M1 seal evidence is captured; E2E parity only via the CI secret store. Deploy gate T004. Supersedes AR1-1's preprod-only carve-out. |
| AR1-12 | HIGH | **Revocation bypass by bearer omission.** FR-008's backward-compat skip ("no valid app-JWT bearer → `rev` check skipped") is attacker-controllable: an attacker holding the victim's refresh cookie (stolen device, cookie-jar malware) simply calls `/refresh` WITHOUT the `Authorization` header and re-mints forever — the ≤15-min revocation bound never engages. CSRF enforcement (FR-013) does not help this attacker: they hold the cookie, they are not cross-site. | **Self-resolved:** the skip is downgraded from a permanent accommodation to a **migration window only**. New task **T033**: once the deployed frontend is verified to always attach the bearer on `/refresh` (it already does via `client.ts:138`; verify the cold-reload path reads the persisted token before first refresh), the Cognito-backed refresh branch MUST require a signature-valid bearer (401 `bearer_required` when absent). Ordered like T042: enforcement deploys only after frontend behavior is confirmed live. FR-008 limitation text now points at T033. Residual (accepted, recorded): during the migration window the bypass exists — same exposure as today's status quo, so no regression. |
| AR1-13 | MEDIUM | **Secret rotation has no dual-key story.** Rotating `JWT_SECRET` (the only instant kill switch, and now required by FR-011a in preprod) invalidates every outstanding token at once — mass logout — and any misordered rotation (Lambda picks up the new secret while old tokens circulate) is indistinguishable from an outage. There is no `kid` header or dual-secret validate window. | Accepted for this feature: mass logout on rotation is the documented posture (FR-008/T1) and preprod rotation (T004) is scheduled deliberately. A `kid` + dual-secret validation window is **carded as a follow-up, out of scope** (same card family as the RS256 migration, FR-010). Mint SHOULD NOT add a `kid` header now — the validator ignores it and it invites header-trust bugs. |
| AR1-14 | LOW | **Clock skew re-check.** `nbf = iat` with the validator's 60s leeway (`auth_middleware.py:103,163`) is safe; a mint host whose clock runs ≥60s fast could still emit tokens rejected by a correct validator. | Lambda hosts are NTP-disciplined; leeway already covers realistic skew. T010 keeps the `nbf == iat` assertion. No change. |
| AR1-15 | LOW | **Replay window re-check under rider (b).** The CSRF deploy-order gate (FR-013a) means refresh stays CSRF-exempt until T042 deploys; during that window a captured 15-min bearer plus a cross-site page could drive a silent re-mint chain. | Window exists today pre-1396 too (refresh is currently exempt AND returns usable Cognito tokens); 1396 does not widen it, and T042 closes it. Ordering risk is the lesser risk vs. mass logout from premature enforcement. Recorded; no change. |

**Gate:** AR1-11 resolved into FR-011a/T004; AR1-12 resolved into T033 + FR-008 limitation rewrite.
**0 CRITICAL, 0 HIGH remaining.** Algorithm confusion re-verified closed (validator pins
`algorithms=[config.algorithm]`, mint uses the same single pinned alg, no header-driven trust —
FR-009/T2); TTL-vs-revocation lag is honestly bounded at ≤15 min post-T033 (N1); replay bounded by TTL
+ `jti` groundwork (OQ-3).
