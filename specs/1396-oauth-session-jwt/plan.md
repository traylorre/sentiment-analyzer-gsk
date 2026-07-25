# Feature 1396 — Implementation Plan

**Feature:** Mint first-party app JWT for OAuth sessions (Option B, HS256-now).
**Spec:** `specs/1396-oauth-session-jwt/spec.md`

---

## Technical Approach

### 1. New helper: `mint_app_jwt`

Location: `src/lambdas/dashboard/auth.py` (co-located with `handle_oauth_callback` /
`refresh_access_tokens`, which both consume it). Signature:

```python
APP_JWT_TTL_SECONDS = 900  # FR-003: 15-min session bearer; re-minted on refresh

def mint_app_jwt(user: User, *, now: datetime | None = None) -> str:
    """Mint a first-party HS256 app JWT that passes validate_jwt (Feature 1396)."""
```

Config sourcing (FR-001) — reuse the exact env + defaults `validate_jwt` uses via
`_get_jwt_config()` in `auth_middleware.py:107`. The plan is to **import and call
`_get_jwt_config()`** (promote it to a non-underscore accessor if a public name is preferred) so mint
and validate cannot drift. From it: `secret`, `algorithm` (default `HS256`), `issuer`
(default `"sentiment-analyzer"`), `audience` (`JWT_AUDIENCE`, may be `None`).

- If `config is None` (`JWT_SECRET` unset) → raise an explicit error → callers fail closed (FR-006).

Claims (FR-002):

```python
iat = int((now or datetime.now(UTC)).timestamp())
payload = {
    "sub": user.user_id,
    "iss": config.issuer,
    "iat": iat,
    "nbf": iat,                         # FR-002 / AR1-7: never future-dated
    "exp": iat + APP_JWT_TTL_SECONDS,
    "roles": get_roles_for_user(user),  # canonical list[str], FR-002 / AR1-2
    "jti": str(uuid4()),                # fresh per mint, FR-002 / AR1-10
    "rev": user.revocation_id,          # FR-008
}
if config.audience is not None:         # AR1-9: match validator's aud handling
    payload["aud"] = config.audience
return jwt.encode(payload, config.secret, algorithm=config.algorithm)  # FR-009: pinned alg
```

`jwt` is PyJWT, already a dependency, but **currently imported only in `auth_middleware.py:19`** — 
**N5:** `auth.py` MUST add `import jwt` (it presently imports `map_stripe_plan_to_role` from roles but
neither `jwt` nor `get_roles_for_user`). `jwt.encode` takes a single `algorithm=` string (no
header-driven alg — FR-009). Also add `from src.lambdas.shared.auth.roles import get_roles_for_user`.

**N4 — authoritative roles (FR-002a).** `get_roles_for_user` (`roles.py:24`) branches on
`user.auth_type == "anonymous"` (`:52`), **not** `user.role`. `_advance_role` (`auth.py:2628-2700`)
persists `role="free"` to DynamoDB but does **not** mutate the in-memory `user` nor advance `auth_type`.
So `mint_app_jwt(user)` must be handed a `user` whose in-memory state is authoritative. The callback
already computes `final_role = "free" if user.role == "anonymous" else user.role` (`auth.py:2432`) but
never writes it back to `user`. The mint caller MUST reconcile the in-hand user before minting — set
`user.auth_type`/`user.role` to the persisted post-advancement values (or re-read the user) — so an
existing anonymous-upgrade user does not under-grant `["anonymous"]`. New OAuth users get
`auth_type=<provider>` at creation (`auth.py:2393`), so they already resolve to `["free"]`.

### 2. Call site — callback (FR-004)

In `handle_oauth_callback`, the `user` object is resolved and its DynamoDB record mutated by
`_advance_role`/`_link_provider`/`_mark_email_verified` (`auth.py:2361-2417`) before the response is
built at `auth.py:2434-2453`. **N4/FR-002a:** those helpers do **not** update the in-memory `user`, so
reconcile it before minting (mirror the `final_role` computation the code already does at `:2432`):

```python
# N4/FR-002a: make the in-hand user authoritative BEFORE roles are read.
# get_roles_for_user gates on user.auth_type (roles.py:52), NOT user.role.
# In the callback the user has just authenticated via OAuth, so auth_type must
# not still read "anonymous" or get_roles_for_user under-grants ["anonymous"].
if user.auth_type == "anonymous":
    user.auth_type = provider   # authenticated via OAuth; matches new-user creation
if user.role == "anonymous":
    user.role = "free"          # keep role consistent with _advance_role's persisted value
app_jwt = mint_app_jwt(user)  # in-hand user, no extra lookup (FR-004, T8-safe)
...
tokens={
    "id_token": tokens.id_token,       # unchanged
    "access_token": app_jwt,           # was tokens.access_token (Cognito) — now app JWT
    "expires_in": APP_JWT_TTL_SECONDS,  # reflect the app JWT's real lifetime
},
refresh_token_for_cookie=tokens.refresh_token,  # unchanged: Cognito refresh stays httpOnly
```

`expires_in` is updated to the app JWT TTL so the frontend schedules refresh correctly (it previously
echoed Cognito's `expires_in`).

### 3. Call site — refresh (FR-005, FR-006a, FR-008, FR-015)

In `refresh_access_tokens`, the Cognito-backed branch already resolves `user` via
`get_user_by_cognito_sub` (`auth.py:2995`). Re-mint there. **Two refuter fixes land here:** the
transient-vs-definitive split (N3/FR-006a) and the refresh-time `rev` check (N1/FR-008).

`refresh_access_tokens` gains an optional `incoming_bearer: str | None = None` parameter so the router
can pass the expiring app JWT from the `Authorization` header (N1 — see §5). The current bare
`except Exception` at `auth.py:2999-3005` is split by failure class:

```python
from botocore.exceptions import ClientError  # already imported in auth.py

try:
    cognito_sub = decode_id_token(tokens.id_token).get("sub")
except Exception as e:                       # decode failure = definitive
    logger.warning("OAuth refresh id_token decode failed", extra=get_safe_error_info(e))
    return RefreshTokenResponse(error="identity_unresolved",
                                message="Could not resolve session identity")   # 401
if not cognito_sub:
    return RefreshTokenResponse(error="identity_unresolved", ...)               # 401 (definitive)
try:
    user = get_user_by_cognito_sub(table, cognito_sub)
except ClientError as e:                     # N3/FR-006a: transient infra fault
    logger.warning("OAuth refresh user lookup unavailable", extra=get_safe_error_info(e))
    return RefreshTokenResponse(error="identity_unavailable",
                                message="Session temporarily unavailable")       # 503, retryable
if not user:                                 # deterministic None (post-1395) = definitive
    return RefreshTokenResponse(error="identity_unresolved", ...)               # 401

# N1/FR-008: refresh-time revocation check. Decode the expiring app JWT (verify_exp=False)
# to read its rev; refuse to re-mint if the user's revocation_id has advanced.
incoming_rev = _read_rev_from_expiring_bearer(incoming_bearer)   # None if absent/invalid sig
if incoming_rev is not None and incoming_rev != user.revocation_id:
    logger.warning("Refresh refused: session revoked (rev advanced)")
    return RefreshTokenResponse(error="session_revoked",
                                message="Session has been revoked")             # 401

access_token_out = mint_app_jwt(user)        # FR-005 re-mint (authoritative user)
return RefreshTokenResponse(
    id_token=tokens.id_token,
    access_token=access_token_out,           # app JWT, not tokens.access_token
    expires_in=APP_JWT_TTL_SECONDS,
    user_id=user.user_id, auth_type=user.auth_type,
)
```

`_read_rev_from_expiring_bearer` decodes with the same `_get_jwt_config()` secret and
`options={"verify_exp": False}` (the app JWT is expected to be expired). A bearer that fails signature
verification or is absent → returns `None` → the `rev` check is skipped (backward-compat, mirrors
`check_revocation_id`'s `None` handling; the ≤15-min bound holds on the next bearer-carrying refresh).

The anonymous branch (`refresh_token.startswith("anon.")`, `auth.py:2978`) is untouched (FR-005). The
`token_revoked` blocklist check (`auth.py:2964-2974`) and Cognito `TokenError` path are unchanged.

> **Design note (fail-closed, but classed — N3):** today the refresh path *degrades* to returning
> Cognito tokens without identity (`auth.py:2999-3005`), swallowing **every** exception. Under Option B
> that degrade path yields a bearer the middleware rejects, so it must fail closed (FR-006) — but
> **collapsing transient DB faults to 401 would cause 15-min-cadence mass logouts**. So the split above
> returns **503 (retryable, session preserved)** on transient infra faults and **401** only on definitive
> unresolved identity. Deliberate behavior change from Feature 1381's degrade-to-guest; called out for
> the reviewer.

### 3b. Router plumbing for the refresh-time rev check (N1)

The refresh route (`router_v2.py:639-657`) extracts only the refresh cookie today. Add extraction of the
`Authorization: Bearer <expiring app JWT>` header and pass it as `incoming_bearer` into
`auth_service.refresh_access_tokens(...)`. The frontend's shared api client already attaches this bearer
to the `/refresh` POST (`client.ts:138`), so no new frontend work is needed for N1. The 503 result maps
to an HTTP 503 (retryable) rather than the existing blanket 401 in the route's `result.error` handling.

### 4. CSRF on refresh (FR-013 — body-delivered token, N2)

**Why the obvious approach is unbuildable (N2):** the `csrf_token` cookie is set on the **API domain**
with `SameSite=None` (`_make_csrf_set_cookie`, `router_v2.py:166-174`); the frontend runs on **Amplify**
(different registrable domain), so `document.cookie` there **cannot read** it, and `frontend/src` has
**zero** `X-CSRF-Token` handling today (all CSRF refs are OAuth `state`). "Read the token from the cookie
and echo it" is impossible cross-origin; removing the exemption without another header source would 403
every refresh → mass logout.

**Backend validation stays exactly as-is.** `require_csrf_middleware` → `validate_csrf_token(cookie,
header)` (`csrf.py:64`) already compares the `X-CSRF-Token` header against the browser-**auto-attached**
`csrf_token` cookie via `hmac.compare_digest`. The browser sends that API-domain cookie server-side even
though Amplify JS can't read it. So double-submit already works *server-side*; the only missing piece is
giving the legitimate frontend the token value for the header.

**Fix — deliver the token in the response body:**

1. In `router_v2.py`, generate the CSRF token **once** and use it for both the Set-Cookie and the body.
   Today `_make_csrf_set_cookie` calls `generate_csrf_token()` internally, hiding the value; refactor so
   the handler (callback at `:626`, refresh at `:701`) creates `csrf = generate_csrf_token()`, builds the
   cookie from `csrf`, and adds `csrf_token: csrf` to the JSON response body.
2. The frontend reads `csrf_token` from the callback **and** refresh response bodies, holds it **in
   memory** (not a cookie — it can't read the cookie anyway), and echoes it as the `X-CSRF-Token` header
   on the next `POST /api/v2/auth/refresh`.
3. Only **after** the frontend ships (1-2), remove `"/api/v2/auth/refresh"` from `CSRF_EXEMPT_PATHS`
   (`csrf.py:38`). Enforcement then activates against the auto-attached cookie + the now-present header.

A cross-site attacker's opaque `fetch` cannot read the body (CORS) nor the cookie (cross-domain), so it
cannot produce a matching `X-CSRF-Token`. Callback stays exempt — protected by the OAuth `state` nonce
(FR-012). `validate_csrf_token` / `csrf.py`'s comparison logic is **unchanged** (only the exempt-path set
and the token-plumbing change).

> Deploy-order gate (OQ-2): the frontend body-read + header-echo MUST ship before the exemption removal,
> else refresh 403s. If they can't land in the same cycle, gate the exemption removal behind the frontend
> deploy. Encoded in tasks.md (T040/T041 before T042... see tasks).

---

## Data Model

No schema change. Inputs read from the existing `User` record:

- `user.user_id` → `sub`
- `user.revocation_id` (`user.py:70`, int, default 0) → `rev`
- **authoritative** `user` state (`auth_type`/`role` reconciled — N4/FR-002a) → `get_roles_for_user(user)`
  → `roles`

No DynamoDB writes added by minting. (`_advance_role` already persists `role`; the N4 reconciliation only
updates the **in-memory** user so the minted roles match the persisted state.)

---

## Contracts

### `OAuthCallbackResponse` (changed semantics + new `csrf_token` body field)
`tokens.access_token` now carries a first-party app JWT instead of a Cognito access token;
`tokens.expires_in` now reflects the 900s app-JWT TTL. `id_token` and `refresh_token_for_cookie`
unchanged. **N2:** the response body now also surfaces `csrf_token` (same value as the `csrf_token`
Set-Cookie) so the cross-origin frontend can echo it as `X-CSRF-Token`.

### `RefreshTokenResponse` (changed semantics + new `csrf_token` body field)
`access_token` now carries a freshly minted app JWT; `expires_in` = 900. **N2:** body also surfaces
`csrf_token`. Failure modes: `error="identity_unresolved"` (**401**, definitive — FR-006/FR-015);
**new** `error="identity_unavailable"` (**503**, transient/retryable — N3/FR-006a); **new**
`error="session_revoked"` (**401**, revocation_id advanced — N1/FR-008).

### Frontend bearer (no change required — FR-014)
`auth.ts:135` reads `response.tokens.access_token` into `accessToken`; `client.ts:138` sends it as
`Authorization: Bearer`. Replacing the field's value is transparent to the bearer plumbing.

---

## Frontend Impact

1. **Bearer:** none (FR-014).
2. **CSRF on refresh (FR-013 / N2):** the frontend must (a) read the `csrf_token` value from the
   callback **and** refresh JSON response bodies and hold it in memory, and (b) attach it as the
   `X-CSRF-Token` header on `POST /api/v2/auth/refresh`. It must **not** try to read the `csrf_token`
   cookie — that cookie is on the API domain and is unreadable cross-origin (N2). Coordinated task in
   tasks.md; deploy-order constraint (frontend before exemption removal) noted above.
3. **Refresh-time rev check (N1):** no new frontend work — the api client already sends the expiring app
   JWT as `Authorization: Bearer` on `/refresh` (`client.ts:138`), which the backend now reads for the
   `rev` comparison.

---

## AR1-6 finding — no other Cognito-token consumer

Verified the returned `access_token` is consumed only as the API bearer (`client.ts:138`).
`sign_out` (`auth.py:3021`) takes its own `access_token` argument for the Cognito global-signout path
and does not depend on the response field's being a Cognito token. A pre-merge grep task confirms no
server path re-presents the response `access_token` to Cognito.

---

## Constitution Check

- **No new AWS resources.** Mint is pure compute; reads existing `User`; no new tables/secrets/infra.
  (Prod `JWT_SECRET` provisioning is an owner action against the *existing* `TF_VAR_jwt_secret`, not a
  new resource — FR-011.)
- **No unjustified fallbacks / no silent failures.** FR-006 mandates fail-closed; the current
  degrade-to-Cognito path is explicitly replaced, not silently kept.
- **Python 3.13; PyJWT already present; moto for tests.** No new dependency.
- **Match auth.py patterns.** Helper co-located, uses existing `get_safe_error_info` logging idiom,
  no token material logged.
- **Serialize with Feature 1395.** Both touch `auth.py`; land 1395's deterministic lookup first or
  coordinate the refresh-branch edit to avoid conflict. Callback-mint is independent of 1395 (FR-015).
- **Middleware untouched (FR-007).** `validate_jwt` / `check_revocation_id` are not edited. The N1
  revocation fix lives entirely in `refresh_access_tokens` + the refresh route, and the N2 CSRF fix lives
  in `router_v2.py` + the frontend — `auth_middleware.py` and `csrf.py`'s comparison logic are untouched
  (only `CSRF_EXEMPT_PATHS` loses one entry).

---

## Decision Notes

**TTL = 900s (15 min).** Matches `JWTConfig.access_token_lifetime_seconds = 900`
(`auth_middleware.py:104`) — the lifetime the validator already documents as expected — and sits at the
top of the owner's 5-15 min band, trading a slightly larger replay window for fewer refresh round-trips
on the cross-origin Amplify→API path. Stale-role exposure is bounded to ≤15 min by TTL and to *zero*
on demand by bumping `revocation_id` (T4/T3, FR-008). Re-minted on every refresh (FR-005).

---

## Adversarial Review #2 — drift & cross-artifact consistency

Checked plan.md against spec.md FRs and against the actual code read this session.

| ID | Sev | Issue | Resolution |
|----|-----|-------|------------|
| AR2-1 | HIGH | **Config-drift risk.** Plan proposes importing the private `_get_jwt_config()` from `auth_middleware`. If a future edit changes one copy of the env defaults, mint/validate could diverge and self-reject. | Plan mandates a **single** config source (call `_get_jwt_config()`, optionally promote to public) precisely to prevent drift. Consistent with FR-001. A task asserts round-trip mint→validate so any drift fails CI. |
| AR2-2 | HIGH | **Fail-closed contradicts Feature 1381's degrade-to-guest.** Plan changes the refresh path from "return Cognito tokens without identity" to a 401. Must be intentional and consistent with FR-006. | Called out explicitly in the plan Design Note and in FR-006/FR-015. Consistent: under Option B the degrade path yields a middleware-rejected bearer, so degrade == silent breakage. Fail-closed is correct. No drift. |
| AR2-3 | MEDIUM | **`expires_in` semantics change.** Plan sets `expires_in=900` (app-JWT TTL) vs the old Cognito `expires_in`. If the frontend used the old value to schedule refresh, timing shifts. | Intentional and correct — the returned bearer now lives 900s, so `expires_in` must reflect that or the frontend refreshes too late and 401s. Spec SC-003/FR-003 consistent. Noted for frontend awareness (no code change; frontend reads `expires_in` generically). |
| AR2-4 | MEDIUM | **CSRF deploy-order lockout.** Removing the refresh exemption before the frontend sends `X-CSRF-Token` would 403 every refresh → mass logout. | Plan encodes a deploy-order constraint (gate exemption removal behind frontend deploy) and OQ-2 defers final ordering to owner. tasks.md sequences the frontend task before the exemption-removal task. Consistent with FR-013. |
| AR2-5 | LOW | **`aud` conditional.** Plan omits `aud` when audience is `None`; spec edge case says the same. Preprod/prod both set `jwt_audience`, so the conditional is defensive-only. | Consistent; no action. |
| AR2-6 | LOW | **Serialization with 1395.** Plan and spec both flag the shared `auth.py` edit and that callback-mint is 1395-independent while refresh-mint depends on 1395's deterministic lookup. | Consistent (FR-015). Task ordering reflects it. |

**Gate:** plan.md is consistent with spec.md; no unresolved HIGH drift. **0 CRITICAL, 0 HIGH
remaining.** Proceed to tasks.md.

---

## Adversarial Review #4 alignment (independent refuter — N1-N5)

Plan sections updated to match the revised spec FRs (full narrative in spec.md → *Adversarial Review #4*):

| # | Plan change |
|---|-------------|
| N1 | §3 refresh-time `rev` check (decode expiring bearer, `verify_exp=False`; `session_revoked` if `revocation_id` advanced); §3b router plumbs the `Authorization` bearer into `refresh_access_tokens(incoming_bearer=...)`. No middleware edit — `check_revocation_id` stays unused. Contract adds `session_revoked` (401). |
| N2 | §4 rewritten to **body-delivered CSRF token** (return `csrf_token` in callback/refresh body; frontend holds in memory + echoes `X-CSRF-Token`; backend `validate_csrf_token(cookie, header)` unchanged against the auto-attached cookie). Contracts add `csrf_token` body field. Cookie-read approach documented as infeasible cross-origin. |
| N3 | §3 splits the bare `except Exception` into **definitive → 401 (`identity_unresolved`)** vs **transient DynamoDB fault → 503 (`identity_unavailable`, retryable, session preserved)**. Router maps 503 distinctly from the blanket 401. |
| N4 | §1/§2 reconcile the in-hand `user` (`auth_type`/`role`) before `get_roles_for_user`, since it gates on `auth_type` and `_advance_role` mutates neither in-memory field. |
| N5 | §1 requires `auth.py` to add `import jwt` and `from ...auth.roles import get_roles_for_user`. |

**Gate:** plan aligns with the AR#4-revised spec; middleware-unchanged guardrail intact. **0 CRITICAL,
0 HIGH remaining.** Owner decisions OQ-1/OQ-2/OQ-4 remain before implementation.
