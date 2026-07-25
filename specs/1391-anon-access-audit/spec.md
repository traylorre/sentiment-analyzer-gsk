# Feature 1391 — anon-access-audit (RE-SCOPED)

**Status:** Draft (planning-only; no implementation)
**Branch:** `1381-session-persistence` (worktree; no new branch per instruction)
**Type:** Security hardening — Backend (Dashboard Lambda REST only)
**Target:** CUSTOMER API surface (Amplify → API Gateway → Dashboard Lambda). NOT the SSE streaming
Lambda (deferred — see §0), NOT the HTMX admin dashboard (`src/dashboard/`).
**Tracks:** GitHub Issue #501 — "Audit all endpoints for anonymous access appropriateness".
**Created:** 2026-07-24 · **Re-scoped:** 2026-07-24

---

## 0. Scope Change Notice (READ FIRST)

This feature was **re-scoped by the owner**. The original 101-route anonymous-access audit found
six gaps. The active scope is now **exactly two** non-SSE, Dashboard-Lambda access-control fixes:

| Gap | Was | Now |
|---|---|---|
| **GAP-2** — unauthenticated `POST /configurations/<id>/refresh` (mutating IDOR) | in scope | **ACTIVE** |
| **GAP-3** — `/chaos/*` controls gated on "any authenticated user" not `operator` | in scope | **ACTIVE** |
| **GAP-1** — SSE config-stream spoofable identity (CRITICAL / A01) | in scope | **OUT OF SCOPE — DEFERRED** |
| GAP-4 (timeseries anon doc), GAP-5 (check-email enum), GAP-6 (alert read asymmetry) | in scope | **DROPPED from active reqs** (confirmed-correct/LOW; recorded in Appendix A) |

**GAP-1 is NOT dropped or ignored.** The SSE streaming Lambda IDOR is being carded separately as a
**CRITICAL-deferred** item — SSE needs its own architectural visit (the streaming Lambda carries an
inline auth stack, selective-COPY Dockerfile constraints, and RESPONSE_STREAM plumbing that warrant
a dedicated feature). It is moved out of THIS feature's active scope and referenced here so it is
not lost. See Appendix A row 101 and §6.

The full 101-route inventory and the "confirmed-correct" dispositions are retained as supporting
evidence in **Appendix A** (the #501 audit deliverable). The **active** requirements and tasks below
cover ONLY GAP-2 and GAP-3.

---

## 1. Problem Statement

Two Dashboard-Lambda routes enforce the wrong access-control posture, both verified against current
code:

1. **`POST /api/v2/configurations/<config_id>/refresh`** (`router_v2.py:1320-1324`) has **no
   identity check and no ownership check** — it calls `market_service.trigger_refresh(config_id)`
   directly and returns 202. Its sibling one function above, `GET .../refresh/status`
   (`router_v2.py:1301-1317`), was hardened by Feature 1249 with `_require_user_id` + ownership.
   The mutating sibling was left open. Anonymous callers can trigger a refresh on **any** config_id
   they can enumerate (resource abuse, cost, cache-stampede, mutating IDOR).

2. **`/chaos/*` operational controls** (`handler.py:1238-1665`) gate on
   `_get_chaos_user_id_from_event` (`handler.py:248-259`), which accepts **any non-anonymous
   authenticated user** (Feature 1250 rejects anonymous, but not free users). They do **not**
   require the `operator` role. So a free signed-in user can pull the andon-cord (emergency
   kill-switch) or flip the chaos gate. Broken function-level access control (OWASP A01:2021).

The tier model is three application roles plus one operator role
(`src/lambdas/shared/auth/enums.py`): `anonymous`, `free`, `paid`, `operator`. The correct boundary
for operational controls is `operator`, enforced by `require_role_middleware("operator")` (Feature
1130), exactly as the already-correct `POST /api/v2/admin/sessions/revoke` and
`GET /api/v2/users/lookup` routes do (`router_v2.py:775`, `:946`).

### Verified current state (file:line, not assumed)

- **GAP-2:** `router_v2.py:1321-1324` — `trigger_refresh(config_id)` body is two lines: call service,
  return 202. No `_require_user_id`, no `_get_config_with_tickers`. Sibling `get_refresh_status`
  (`:1302-1317`) does both. Confirmed.
- **GAP-3:** all `/chaos/*` handlers call `_get_chaos_user_id_from_event(event)` → 401 only when
  `None` (no user / anonymous). None attach `require_role_middleware`. Confirmed at
  `handler.py:1242, 1352, 1417, 1547, 1579, 1627, 1660` (reports/gate/andon/metrics/health) and
  `:960, 1023, 1085, 1134` (experiments, additionally `_is_dev_environment()`-gated).
- **Environment nuance (GAP-3):** the chaos service layer (`dashboard/chaos.py:922-932`,
  `check_environment_allowed()`) restricts gate/andon/health/metrics to
  `ALLOWED_ENVIRONMENTS = ["preprod","dev","test","local"]` and raises `EnvironmentNotAllowedError`
  → 403 in **prod**. So the live abuse window is **preprod** (a real deployed environment) and the
  lower envs — a free user there gets operator-grade control. The original spec's "flip the chaos
  gate in prod" was imprecise; the fix (operator role) is still required to close the preprod
  exposure and to make the boundary correct rather than relying on the env allowlist alone.

---

## 2. User Stories

- **US-1 (Authenticated owner).** As a signed-in (or anonymous-session) config owner, I can trigger
  a manual refresh on **my own** config — the frontend "refresh" button and pull-to-refresh keep
  working (`frontend/src/lib/api/sentiment.ts:30-31` → `POST .../refresh`).
- **US-2 (Attacker, denied).** As a caller who has not proven ownership of a config, my
  `POST .../refresh` is rejected — I cannot mutate/refresh another user's config by guessing its id.
- **US-3 (Operator).** As an operator, I can use the `/chaos/*` operational controls (gate,
  andon-cord, reports, metrics, health) via the operator-gated admin dashboard.
- **US-4 (Free user, denied).** As a free signed-in user, I cannot pull the andon-cord or flip the
  chaos gate — those require the `operator` role, not merely a valid session.

---

## 3. Functional Requirements (ACTIVE — two gaps only)

- **FR-001 (GAP-2 — authentication + ownership on refresh).**
  `POST /api/v2/configurations/<config_id>/refresh` (`router_v2.py:1320`) MUST mirror the Feature
  1249 sibling `get_refresh_status`: resolve the event, call `_require_user_id(event, table=table)`,
  then `_get_config_with_tickers(table, user_id, config_id)` for the ownership check, **before**
  `market_service.trigger_refresh(config_id)`. Missing credential → **401**; valid session but
  non-owner (config not found for this user) → **404** (no existence oracle); owner → **202**
  (unchanged success). Anonymous **session** owners are allowed (`_require_user_id` is anon-ok,
  matching the sibling) — only credential-less and non-owner callers are blocked.

- **FR-002 (GAP-3 — operator gate on mutating/control chaos routes).** The mutating and control
  `/chaos/*` routes — `PUT /chaos/gate`, `POST /chaos/andon-cord`, `POST /chaos/reports`,
  `POST /chaos/reports/plan`, `DELETE /chaos/reports/<id>`, and the dev-gated experiment mutations
  (`POST /chaos/experiments`, `.../start`, `.../stop`, `DELETE /chaos/experiments/<id>`) — MUST
  require the `operator` role via `require_role_middleware("operator")`. No credential / no roles
  claim → **401**; authenticated non-operator → **403**; operator → allowed. The
  `_is_dev_environment()` fail-closed gate on the experiment routes and the service-layer
  `check_environment_allowed()` on gate/andon/health/metrics are **retained** (defense in depth).

- **FR-003 (GAP-3 — read-only chaos routes, dispositioned).** The read-only `/chaos/*` routes
  (`GET /chaos/gate`, `GET /chaos/health`, `GET /chaos/metrics`, `GET /chaos/reports`,
  `GET /chaos/reports/<id>`, `GET /chaos/reports/<id>/compare`,
  `GET /chaos/reports/trends/<scenario_type>`, `GET /chaos/experiments*`) MUST **also** require
  `operator`. **Justification:** every chaos route already requires authentication today (no
  anonymous consumer exists), the only client is the operator-gated admin dashboard
  (`frontend/src/app/(admin)/admin/chaos/page.tsx` behind `(admin)/layout.tsx`'s `useIsOperator`
  guard, whose comment explicitly states "Backend require_role_middleware('operator') remains" the
  enforcement boundary), and the read bodies expose operational internals (environment name,
  baselines, CloudWatch metrics, experiment reports). There is no legitimate free/anonymous read
  flow to preserve, so gating reads carries no UX-regression risk and closes an information-
  disclosure surface. The generic liveness probe remains the anon-ok `GET /health`
  (`handler.py:565`), which is unaffected.

- **FR-004 (tests).** Each closed gap MUST have contract/unit tests asserting the posture:
  - GAP-2: `POST .../refresh` → 401 (no credential), 404 (valid session, non-owner), 202 (owner;
    include an anonymous-session owner case).
  - GAP-3: representative mutating route (`PUT /chaos/gate`, `POST /chaos/andon-cord`) and a
    read-only route (`GET /chaos/gate`) → 401 (no/anonymous), 403 (free authenticated), allowed
    (operator).

- **FR-005 (no regression).** No behavioral change to the legitimate flows: the frontend refresh
  button for an owner still succeeds (202); the operator admin chaos dashboard still functions; the
  anon-ok `GET /health`, market/reference routes, and anonymous-session data paths are untouched.

- **FR-006 (GAP-1 deferral, explicit).** The SSE streaming-Lambda config-stream IDOR (GAP-1,
  CRITICAL) is **out of scope** for this feature and MUST NOT be silently dropped: it is referenced
  in Appendix A (row 101) and carded as a separate CRITICAL-deferred item. This feature's success
  criteria do not include GAP-1; Issue #501 is **not** fully closeable until the deferred SSE work
  lands (this feature closes only the two Dashboard-Lambda gaps and annotates the deferral).

## 4. Non-Functional Requirements

- **NFR-001** No new AWS resources (standing constraint). Changes are code-only in
  `src/lambdas/dashboard/router_v2.py` (GAP-2) and `src/lambdas/dashboard/handler.py` (GAP-3).
- **NFR-002** Backend Bearer + `require_role_middleware` is the sole security boundary; no cookie-
  gating reintroduced (Q-M1-2). CSRF stays orthogonal to identity.
- **NFR-003** No secret/PII logging; reuse `sanitize_for_log` where user input is logged.
- **NFR-004** GPG-signed commits, venv active (checkov/bandit/pre-commit parity).
- **NFR-005 (hotspot serialization).** `router_v2.py` (and `auth.py`) is a hotspot shared with
  **Feature 1384**. The GAP-2 edit is confined to the 5-line `trigger_refresh` function
  (`:1320-1324`) to minimize merge-conflict surface; coordinate/rebase ordering with 1384 before
  landing. GAP-3 lives in `handler.py` (separate file, lower conflict risk).

## 5. Success Criteria

- **SC-001** GAP-2 closed: `POST .../refresh` returns 401 without a credential, 404 for a valid-but-
  non-owner session, 202 for the owner — test-proven.
- **SC-002** GAP-3 closed: mutating chaos controls return 401 (no/anon) and 403 (free authenticated),
  allowed for operator; read-only chaos routes likewise operator-gated — test-proven.
- **SC-003** Zero regression: frontend owner-refresh still 202; operator admin chaos flow intact;
  `GET /health` and anon-ok reference routes unchanged (FR-005 tests green).
- **SC-004** GAP-1 (SSE) explicitly recorded as CRITICAL-deferred in Appendix A + carded elsewhere;
  #501 left open pending that deferred work, with the two Dashboard-Lambda gaps documented as closed.

## 6. Edge Cases

- **OPTIONS preflight:** CORS preflight is answered before the identity/role checks; the new gates
  MUST NOT 401/403 an OPTIONS request or the browser flow breaks. `require_role_middleware` runs on
  the matched route only; confirm preflight is short-circuited by the CORS layer / API Gateway mock
  integration (test: no 401/403 on OPTIONS to `/chaos/gate` and `.../refresh`).
- **Anonymous session owner refresh:** an anonymous session's token equals its user_id;
  `_require_user_id` (anon-ok) resolves it and `_get_config_with_tickers` scopes to that user, so an
  anonymous **owner** can still refresh its own config. Only credential-less callers and non-owners
  are rejected. (This is why GAP-2 uses `_require_user_id`, matching the sibling, **not**
  `_require_authenticated_user_id`.)
- **Non-owner error code:** non-owner refresh MUST return **404** (config-not-found for this user),
  not 403, to avoid a config-existence oracle. Body carries no id echo.
- **Chaos env allowlist retained:** operator gating is additive; `_is_dev_environment()` (experiments)
  and `check_environment_allowed()` (gate/andon/health/metrics, prod→403) remain as defense in depth.
  A role-config drift must not silently re-open prod.
- **Redundant inline non-anon check:** once `require_role_middleware("operator")` is attached, the
  inline `_get_chaos_user_id_from_event(...) is None → 401` becomes redundant (middleware runs
  first). It may be left as a harmless second gate or removed for clarity; if removed, the 401-for-
  anonymous behavior MUST be preserved by the middleware (it is: `user_id is None → 401`).

---

## Adversarial Review #1 (pentester lens — attack the TWO gaps before sign-off)

Attacking only the in-scope surface:

- **[HIGH] H1 — Unauthenticated mutating IDOR on refresh.** Today `POST /configurations/{any}/refresh`
  needs no credential (`router_v2.py:1320-1324`); I enumerate/guess config_ids and hammer refresh →
  cost, cache-stampede, forced upstream fetch on a victim's config. **Resolution:** FR-001
  (`_require_user_id` + ownership; 401/404/202). **Gated — must land with tests.**
- **[HIGH] H2 — IDOR variant via anonymous UUID.** Could an attacker pass a victim's anonymous UUID
  as identity to pass the ownership check? `_require_user_id` derives user_id from the validated
  session/token context (`extract_auth_context`), not a spoofable header — the X-User-ID fallback
  was removed dashboard-wide (Feature 1146). So supplying someone else's UUID does not authenticate
  as them on the Dashboard Lambda. **Resolution:** FR-001 inherits the 1146-clean resolver; the
  header-spoof IDOR that still lives in the SSE Lambda (GAP-1) is the deferred item, not this route.
  **Confirmed not-exploitable on the Dashboard route.**
- **[MEDIUM] M1 — Privilege climb on chaos controls (preprod).** Sign up (free), obtain a JWT, call
  `POST /chaos/andon-cord` or `PUT /chaos/gate` in **preprod** — the non-anon check passes, there is
  no operator check. In **prod** the service layer 403s (env allowlist), but preprod is live and the
  andon-cord sets a real kill-switch / IAM-deny path. **Resolution:** FR-002
  (`require_role_middleware("operator")`; 403 for free). **Gated.**
- **[MEDIUM] M2 — Role-bypass via missing roles claim.** Could a token without a `roles` claim slip
  through? `require_role_middleware` returns 401 "Invalid token structure" when `roles is None`
  (`require_role.py`), and 403 when the required role is absent — anonymous can never be operator
  (`roles.py:51` — anonymous cannot hold any other role). **Resolution:** middleware fails closed;
  no bypass. Test M2 explicitly.
- **[MEDIUM] M3 — Does gating break a legit guest/free flow?** (a) **Refresh:** the frontend refresh
  button sends the session credential (`api.post`), and anonymous **owners** still pass
  (`_require_user_id` anon-ok) → no guest regression. (b) **Chaos reads:** the only chaos client is
  the operator-gated `(admin)` dashboard; no free/guest flow reads chaos data, so operator-gating
  the read routes (FR-003) breaks nothing legitimate. **Resolution:** FR-005 regression tests pin
  owner-refresh 202 and operator chaos access; free/guest chaos access was never legitimate.
- **[LOW] L1 — Info-disclosure via chaos read routes** (environment name, baselines, metrics) to a
  free user. **Resolution:** FR-003 gates reads on operator, closing the disclosure. Justified in §3.

**Does anonymous/free get more than intended?** Today yes — H1 hands an outsider an unauthenticated
mutation, and M1 hands a free user operator-grade control in preprod. Both are gated and MUST be
fixed in-feature with FR-004 tests. **Gate: PASS conditional on GAP-2/GAP-3 closure landing with
tests.** GAP-1 (SSE IDOR) remains CRITICAL but is explicitly deferred (FR-006) — #501 stays open.

---

## Clarifications (self-answered ≤5, with evidence)

1. **Q: Should GAP-2 use `_require_user_id` (anon-ok) or `_require_authenticated_user_id`?**
   A: `_require_user_id`, to mirror the Feature 1249 sibling `get_refresh_status`
   (`router_v2.py:1307`) exactly. An anonymous session can own a config; blocking it would over-lock
   a legitimate owner. Ownership (`_get_config_with_tickers`) is the real gate. Evidence:
   `router_v2.py:1302-1317` vs `:1321-1324`.
2. **Q: Is the chaos surface actually exposed in prod, as the original spec claimed?**
   A: Not for gate/andon/health/metrics — `check_environment_allowed()`
   (`dashboard/chaos.py:922-932`, allowlist `["preprod","dev","test","local"]`) 403s in prod. The
   live exposure is **preprod** and lower envs. The operator gate is still required (correct
   boundary + closes preprod). Original "in prod" phrasing corrected here and in AR#2.
3. **Q: Do the read-only chaos routes get gated or stay open?** A: **Gated on operator** (FR-003).
   All chaos routes already require auth (no anon consumer), the sole client is the operator-gated
   admin dashboard, and reads leak operational internals. Evidence:
   `frontend/src/app/(admin)/layout.tsx:8,30-33` (operator guard + "backend require_role remains").
4. **Q: Will operator-gating break the frontend chaos dashboard?** A: No — the `(admin)` route group
   already redirects non-operators client-side and its layout comment states the backend
   `require_role_middleware("operator")` is the intended enforcement. Backend gating aligns with an
   assumption the frontend already makes. Evidence: `frontend/src/app/(admin)/layout.tsx:30-33`.
5. **Q: Why is GAP-1 (SSE) out of this feature rather than fixed here?** A: The SSE streaming Lambda
   has an inline auth stack (`sse_streaming/handler.py`), a selective-COPY Dockerfile that would
   need shared-auth + transitive `src.lib.*` added (deploy-blocking `ModuleNotFoundError` risk per
   CLAUDE.md), and RESPONSE_STREAM plumbing — a dedicated architectural visit. Owner deferred it as
   CRITICAL-carded-elsewhere. This feature does the two clean Dashboard-Lambda fixes. Evidence:
   Appendix A row 101; §0; §6 FR-006.

---

## Appendix A — Full Route Inventory (supporting evidence for #501; NOT the active scope)

Retained verbatim from the original audit as the #501 deliverable. **Active work is only the two
rows marked ACTIVE.** GAP-1 row is marked DEFERRED; GAP-4/5/6 rows are confirmed-LOW dispositions
recorded for the audit but not implemented in this feature.

Auth legend: **none** = no identity check · **session (anon-ok)** = `_require_user_id` · **auth** =
`_require_authenticated_user_id` (rejects anonymous) · **owner** = session + ownership verified ·
**operator** = `require_role_middleware("operator")` · **dev-gated** = `_is_dev_environment()`→404 ·
**CSRF** = `require_csrf_middleware`.

### A1. Dashboard Lambda — app-level (`handler.py`)

| # | Method + Path | Current auth (file:line) | Intended | Disposition |
|---|---|---|---|---|
| 1 | GET `/` | dev-gated (`:384`) | dev | correct |
| 2 | GET `/favicon.ico` | none (`:405`) | anon-ok | correct |
| 3 | GET `/static/<filename>` | dev-gated (`:426`) | dev | correct |
| 4 | GET `/api` | dev-gated (`:471`) | dev | correct |
| 5 | GET `/health` | none; verbose only if dev (`:565`) | anon-ok | correct |
| 6 | GET `/api/v2/runtime` | none; verbose only if dev (`:612`) | anon-ok | correct |
| 7 | GET `/api/v2/metrics` | session anon-ok (`:637`) | anon-ok | correct |
| 8 | GET `/api/v2/sentiment` | session anon-ok (`:688`) | anon-ok | correct |
| 9 | GET `/api/v2/trends` | session anon-ok (`:754`) | anon-ok | correct |
| 10 | GET `/api/v2/articles` | session anon-ok (`:863`) | anon-ok | correct |
| 11–17 | `/chaos/experiments*` (7) | dev-gated + non-anon (`:954–1207`) | operator + dev | **ACTIVE (GAP-3)** |
| 18–34 | `/chaos/reports*`, `/chaos/health`, `/chaos/gate` GET+PUT, `/chaos/andon-cord`, `/chaos/metrics` | non-anon; env-allowlist on gate/andon/health/metrics (`:1238–1665`) | operator | **ACTIVE (GAP-3)** |

### A2. Dashboard Lambda — auth router (`router_v2.py`)

Rows 35–52: unchanged from audit; `admin/sessions/revoke` (`:775`) and `users/lookup` (`:946`) are
already **operator**-gated ✅ and serve as the pattern GAP-3 mirrors. `check-email` (`:804`,
GAP-5 email-enum, LOW) — confirmed accepted-risk, not implemented here.

### A3. Dashboard Lambda — configurations router (`router_v2.py`)

| # | Method + Path | Current auth (file:line) | Intended | Disposition |
|---|---|---|---|---|
| 55–62 | `/<id>`, `/<id>/{sentiment,heatmap,volatility,correlation}` etc. | owner | owner | correct |
| 63 | GET `/<id>/refresh/status` | owner (`:1301`, Feature 1249) | owner | correct (pattern source) |
| 64 | POST `/<id>/refresh` | **none — direct `trigger_refresh`** (`:1320`) | owner | **ACTIVE (GAP-2)** |
| 65–66 | `/<id>/premarket`, `/<id>/sentiment/<ticker>/history` | owner (svc-side) | owner | correct |
| 67 | GET `/<id>/alerts` | session anon-ok (`:1396`) | owner | GAP-6 (LOW) — not implemented here |
| 68–71 | `/<id>/alerts` write/toggle | auth (`:1416+`) | owner | correct |

### A4. tickers / market / timeseries / notifications (rows 72–93)

All confirmed correct or LOW. `GET /api/v2/timeseries/<ticker>` + `/batch` (`:1605`,`:1676`, GAP-4,
LOW/REVIEW) — ticker-keyed public reference data, dispositioned anon-ok; documentation-only, not
implemented here.

### A5. OHLC router (rows 94–95) — session anon-ok, correct.

### A6. SSE surfaces (rows 96–101) — **DEFERRED, NOT in this feature**

| # | Method + Path | Current auth (file:line) | Gap |
|---|---|---|---|
| 96–98 | Dashboard SSE (`sse.py:264/313/399`) | global none; config Bearer-only | verify ownership (deferred with SSE) |
| 99–100 | SSE Lambda global (`sse_streaming/handler.py:560/564`) | none | correct (global) |
| 101 | SSE Lambda `GET /configurations/<id>/stream` | **raw Bearer / X-User-ID / `?user_token=` → ownership-only** (`handler.py:356–408`) | **GAP-1 — CRITICAL — DEFERRED** (carded separately; needs SSE architectural visit) |

**Total inventoried: 101 routes.** Active in this feature: **2** (GAP-2 row 64, GAP-3 rows 11–34).
