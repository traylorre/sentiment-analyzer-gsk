# Feature 1396 — Tasks

Dependency-ordered. `[P]` = parallelizable with siblings. Each task maps to FRs.
Serialize `auth.py` edits with Feature 1395.

---

## Phase 0 — Pre-flight

- **T001** Confirm Feature 1395's deterministic `get_user_by_cognito_sub` (dedup + footgun fix) is
  merged, OR scope this PR to callback-mint only and gate refresh-mint behind 1395. (FR-015)
- **T002** [P] Grep-verify no server path re-presents the response `access_token` to Cognito
  (`sign_out` uses its own arg). Lock the AR1-6 finding. (AR1-6)
- **T003** [P] Confirm with owner: prod `JWT_SECRET` is strong and distinct from
  `PREPROD_TEST_JWT_SECRET`. Record as deploy gate; do not assume done. (FR-011, OQ-1)

## Phase 1 — Mint helper (TDD)

- **T010** Write unit tests for `mint_app_jwt` **first**:
  - minted token round-trips through `validate_jwt` and returns a `JWTClaim` (aud/iss/roles/sub). (FR-007, SC-001)
  - **(N4 — de-tautologized)** `roles` equals the **literal** expected list per user state, NOT
    `== get_roles_for_user(user)`: assert `["anonymous"]` for an un-reconciled anonymous user;
    `["free"]` for a new OAuth user (`auth_type=<provider>`) **and** for an existing anonymous user
    **after** the FR-002a reconciliation; `["free","paid"]` for a subscription-active user;
    `["free","paid","operator"]` for an operator. Add a **regression test** proving that minting from an
    un-reconciled just-upgraded existing user would under-grant `["anonymous"]` (locks the N4 fix).
    Never empty/`None`. (FR-002, FR-002a, AR1-2)
  - `rev` equals `user.revocation_id`. **(N1)** Revocation is tested at the refresh layer (T032), NOT via
    `check_revocation_id` in the request path (which is dead code). (FR-008)
  - `exp - iat == 900`; `nbf == iat`; `jti` is a fresh UUID and differs across two mints. (FR-002, FR-003, AR1-10)
  - `iss` matches `validate_jwt`'s default (`"sentiment-analyzer"`) with `JWT_ISSUER` unset. (AR1-8)
  - `alg` in the JWT header is exactly `HS256`; a token re-signed with `alg:none` or a wrong key is
    rejected by `validate_jwt`. (FR-009, T2)
  - `JWT_SECRET` unset → `mint_app_jwt` raises (fail closed). (FR-006)
  Use moto/env fixtures; no real AWS.
- **T011** Implement `mint_app_jwt` + `APP_JWT_TTL_SECONDS` in `auth.py`, sourcing config from the
  single shared `_get_jwt_config()` accessor. **(N5)** Add `import jwt` (PyJWT) and
  `from src.lambdas.shared.auth.roles import get_roles_for_user` to `auth.py` — neither is imported there
  today. (FR-001, FR-002, FR-003, FR-009, N5) — depends on T010.
- **T012** Add the **regression-lock** test: a raw Cognito-style access token (or any non-app-JWT
  string) passed to `validate_jwt` returns `None` / is rejected. (SC-002)

## Phase 2 — Callback mint

- **T020** Test: `handle_oauth_callback` returns `tokens["access_token"]` that passes `validate_jwt`
  with the user's roles and `sub == user.user_id`; `expires_in == 900`; `refresh_token_for_cookie` is
  still the Cognito refresh token. (FR-004, SC-001) — depends on T011.
- **T021** Implement: replace `access_token` with `mint_app_jwt(user)` and set `expires_in` at the
  callback response (`auth.py:2434-2453`), using the in-hand `user`. **(N4/FR-002a)** Reconcile the
  in-memory user first — set `user.auth_type` off `"anonymous"` (→ provider) and `user.role` off
  `"anonymous"` (→ `"free"`) to match what `_advance_role` persisted — so `get_roles_for_user` (which
  gates on `auth_type`) does not under-grant. (FR-004, FR-002a) — depends on T011.

## Phase 3 — Refresh re-mint (depends on 1395 / T001)

- **T030** Test: Cognito-backed `refresh_access_tokens` returns a freshly minted app JWT (newer `iat`)
  that passes `validate_jwt`; anonymous (`anon.`) branch unchanged. **(N3 — transient vs definitive)**
  definitive unresolved identity (no `sub` / deterministic `None`) → `error="identity_unresolved"` (401,
  no Cognito bearer); a **DynamoDB `ClientError`/throttle** during `get_user_by_cognito_sub` →
  `error="identity_unavailable"` (503, retryable) and the session is NOT dropped. Assert the route maps
  503 distinctly from 401. (FR-005, FR-006, FR-006a, FR-015, SC-003, SC-007)
- **T031** Implement: re-mint in the Cognito branch of `refresh_access_tokens`; **(N3)** split the current
  bare `except Exception` (`auth.py:2999-3005`) into definitive → 401 vs transient (`ClientError`) → 503;
  add the router 503 mapping (`router_v2.py:674-678`). (FR-005, FR-006, FR-006a) — depends on T011, T001.
- **T032** **(N1 — refresh-time revocation)** Test + implement the refresh-time `rev` check: add
  `incoming_bearer` param to `refresh_access_tokens`; plumb the `Authorization` bearer from the refresh
  route (`router_v2.py:639-657`); decode it `verify_exp=False` with `_get_jwt_config()`'s secret to read
  `rev`; refuse to re-mint (`error="session_revoked"`, 401) when `rev != user.revocation_id`. Tests:
  (a) matching `rev` → re-mint succeeds; (b) after `user.revocation_id` bump, the same expiring bearer →
  `session_revoked`; (c) absent/invalid-signature bearer → check skipped (backward-compat), still re-mints.
  **Do NOT touch the middleware** — `check_revocation_id` stays uncalled (FR-007). (FR-008, SC-004, OQ-4)
  — depends on T011, T031.

## Phase 4 — CSRF on refresh (body-delivered token, N2; ordering-sensitive)

- **T040** **Backend** [body-delivery]: in `router_v2.py`, generate the CSRF token **once** per
  callback (`:626`) and refresh (`:701`) handler, use it for both the `csrf_token` Set-Cookie and a new
  `csrf_token` field in the JSON response body. Refactor `_make_csrf_set_cookie` so the caller owns the
  value. Tests assert body `csrf_token` == the Set-Cookie value. `validate_csrf_token`/`csrf.py` compare
  logic unchanged. (FR-013, N2)
- **T041** **Frontend** [coordinated]: read `csrf_token` from the callback **and** refresh response
  bodies, hold it in memory (NOT from the cookie — unreadable cross-origin), and attach it as
  `X-CSRF-Token` on `POST /api/v2/auth/refresh` in the Next.js api client. (FR-013, FR-014, N2) — must
  land **before** T042.
- **T042** Remove `"/api/v2/auth/refresh"` from `CSRF_EXEMPT_PATHS` (`csrf.py:38`); add/adjust tests so
  refresh without a matching `X-CSRF-Token` returns 403 and with it succeeds (double-submit against the
  auto-attached API-domain cookie). (FR-013, SC-006) — depends on T040 **and** T041 (deploy-order gate,
  OQ-2). Callback stays exempt (OAuth `state`, FR-012).

## Phase 5 — Validation & docs

- **T050** [P] Run `pytest tests/unit/` for auth + middleware; `ruff format`/`ruff check`; `make sast`.
- **T051** [P] Update the OAuth/auth doc note: `access_token` in callback/refresh responses is now a
  first-party app JWT (900s TTL), refresh requires CSRF, RS256 migration is carded if a 2nd verifier
  appears (FR-010).
- **T052** [P] Record OQ-1/OQ-2/OQ-3 resolutions or carry them as owner follow-ups.

---

## FR → Task coverage

| FR | Tasks |
|----|-------|
| FR-001 | T011 |
| FR-002 | T010, T011 |
| FR-002a (N4) | T010, T021 |
| FR-003 | T010, T011 |
| FR-004 | T020, T021 |
| FR-005 | T030, T031 |
| FR-006 | T010, T030, T031 |
| FR-006a (N3) | T030, T031 |
| FR-007 | T010, T020, T032 (middleware untouched) |
| FR-008 (N1, refresh-time) | T032 |
| FR-009 | T010, T011 |
| FR-010 | T051 |
| FR-011 | T003 |
| FR-012 | T042 |
| FR-013 (N2, body-delivered) | T040, T041, T042 |
| FR-014 | T041 (bearer: no change) |
| FR-015 | T001, T030, T031 |
| N5 (import jwt) | T011 |

---

## Adversarial Review #3 — task risk & readiness

**Highest-risk task: T042 (remove refresh CSRF exemption).** Getting the deploy order wrong 403s every
refresh → mass logout of the exact users this feature is meant to keep logged in. Mitigation is baked
into ordering: T040 (backend delivers `csrf_token` in the body) and T041 (frontend echoes it as
`X-CSRF-Token`) MUST ship before T042, and OQ-2 forces the owner to confirm the lockstep vs gated-deploy
decision. If uncertain, T042 ships behind the frontend deploy.

**Second-highest: T031 (refresh fail-closed, classed).** This inverts Feature 1381's degrade-to-guest
behavior. The N3 split avoids the amplification trap: transient DynamoDB faults return **503 (retryable,
session preserved)**, only definitive unresolved identity returns **401**. Risk of rework if a downstream
consumer relied on refresh returning *something* on unresolved identity; T002/T030 bound this.

**Third: T032 (refresh-time rev check, N1).** Depends on the router passing the expiring bearer through;
the frontend already sends it (`client.ts:138`). Backward-compat skip on absent/invalid bearer avoids a
lockout regression. Middleware is NOT touched — `check_revocation_id` stays dead code by design (OQ-4).

**Most-likely rework: T011 config sourcing.** If `_get_jwt_config()` is copied rather than shared,
silent mint/validate drift appears only at runtime. T010's round-trip assertion turns that into a CI
failure, so rework is caught pre-merge rather than in prod.

**Dependency correctness:** callback-mint (T020/T021) is independent of Feature 1395 and can ship
first; refresh-mint (T030/T031/T032) is gated on 1395 via T001. `auth.py` edits serialized with 1395.

**Test sufficiency:** SC-001 (mint passes), SC-002 (Cognito token fails — regression lock), SC-003
(re-mint), SC-004 (refresh-time rev revocation — T032), SC-006 (CSRF — T042), SC-007 (transient vs
definitive — T030) all have dedicated tasks. N4 has a literal-value + under-grant regression test (T010).
Threats T1-T8 map to FRs with test coverage except T7 (XSS, structurally out of scope, bounded by
TTL + refresh-time rev).

**Gate:** dependency order is coherent, the highest-risk task has an explicit ordering safeguard, and
tests cover every success criterion including the regression lock and the AR#4 (N1-N5) fixes.
**READY FOR IMPLEMENTATION pending owner decisions OQ-1 (prod secret), OQ-2 (CSRF deploy lockstep), OQ-4
(refresh-time revocation posture).** T001 (Feature 1395 status) still gates the refresh phase.
