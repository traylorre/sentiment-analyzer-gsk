# Implementation Plan — Feature 1391 anon-access-audit (RE-SCOPED)

**Spec:** `./spec.md`
**Branch:** `1381-session-persistence` (worktree; no new branch)
**Scope:** Two code-only Dashboard-Lambda access-control fixes. No SSE work (deferred), no new AWS
resources, no Terraform, no frontend logic change.
- **GAP-2:** `src/lambdas/dashboard/router_v2.py` — `trigger_refresh` (`:1320-1324`).
- **GAP-3:** `src/lambdas/dashboard/handler.py` — `/chaos/*` routes (`:954-1665`).

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| Two-dashboard hazard | ✅ | Customer Dashboard Lambda only. Zero `src/dashboard/` HTMX touch. |
| No new AWS resources | ✅ | Code-only in two files. Reuses `_require_user_id`, `_get_config_with_tickers`, `require_role_middleware`. |
| Bearer + require_role sole boundary | ✅ | GAP-3 uses `require_role_middleware("operator")`; GAP-2 uses the 1146-clean `_require_user_id` resolver. No cookie-gate (NFR-002). |
| No CORS over-broadening | ✅ | No CORS change; OPTIONS preflight stays pre-auth (edge case + test). |
| No secret/PII logging | ✅ | `sanitize_for_log` retained where used (NFR-003). |
| GPG-signed + venv commits | ✅ | `git commit -S`, venv active for checkov/bandit parity (NFR-004). |
| Least-diff | ✅ | GAP-2 mirrors the sibling exactly; GAP-3 attaches an existing middleware. No new auth stack. |
| Hotspot serialization (1384) | ⚠️ | `router_v2.py`/`auth.py` shared with Feature 1384. GAP-2 confined to a 5-line function; coordinate rebase (NFR-005). |

**Result: PASS (with 1384 serialization flagged).**

---

## Technical Context

- **Language/runtime:** Python 3.13, Dashboard = Powertools `APIGatewayRestResolver` (BUFFERED).
- **Auth primitives (reuse, do not reinvent):**
  - `router_v2.py:272` `_require_user_id(event, table=None, validate_session=True)` — anon-ok;
    derives user_id from `extract_auth_context` (1146-clean, no X-User-ID). Returns
    `(user_id, None)` or `(None, error_response(401/403))`.
  - `router_v2.py:321` `_get_config_with_tickers(table, user_id, config_id)` — ownership check;
    returns `(None, error_response(404, "Configuration not found"))` for a config the user doesn't
    own. This is the existence-oracle-safe 404 path.
  - `src/lambdas/shared/middleware/require_role.py:32` `require_role_middleware("operator")` —
    Powertools middleware factory. Returns 401 (no user_id / no roles claim) or 403 ("Access
    denied") or passes to `next_middleware`. Validates role name at factory time (`VALID_ROLES`).
  - `src/lambdas/shared/auth/roles.py:24` `get_roles_for_user` — `is_operator` flag → operator role;
    anonymous can never be operator (`:51`).
- **Sibling patterns being mirrored:**
  - GAP-2 mirrors `get_refresh_status` (`router_v2.py:1302-1317`, Feature 1249): event →
    `_require_user_id(event, table=table)` → `_get_config_with_tickers(...)` → service call.
  - GAP-3 mirrors the operator routes `revoke_sessions_bulk` (`router_v2.py:773-776`,
    `middlewares=[require_role_middleware("operator")]`) and `users/lookup` (`:946`). Powertools
    supports `middlewares=[...]` on `@app.<verb>(...)` decorators just as on `@router.<verb>(...)`.
- **Chaos service env gating (retained, DiD):** `dashboard/chaos.py:922-932`
  `check_environment_allowed()` — `ALLOWED_ENVIRONMENTS=["preprod","dev","test","local"]`,
  `EnvironmentNotAllowedError`→403 in prod for gate/andon/health/metrics. Experiment routes also
  carry `_is_dev_environment()`→404 at the handler. Operator gating is **additive** to both.
- **Testing:** unit/contract with `moto`. Dashboard route tests build API Gateway events; role tests
  supply JWTs whose `roles` claim contains/omits `operator`. No preprod in local runs (`-m "not
  preprod"`).

---

## Routes That Change (with file:line) — authoritative

| Route | File:line | Current | Target | Gap | Sev |
|---|---|---|---|---|---|
| `POST /configurations/{id}/refresh` | `router_v2.py:1320-1324` | none | `_require_user_id` + ownership (401/404/202) | GAP-2 | HIGH→MED |
| `PUT /chaos/gate` | `handler.py:1578` | non-anon | `+ operator` | GAP-3 | MED |
| `POST /chaos/andon-cord` | `handler.py:1626` | non-anon | `+ operator` | GAP-3 | MED |
| `POST /chaos/reports`, `.../reports/plan`, `DELETE .../reports/<id>` | `handler.py:1238,1302,1484` | non-anon | `+ operator` | GAP-3 | MED |
| `GET /chaos/gate,/health,/metrics,/reports*` (read) | `handler.py:1348,1384,1413,1440,1514,1546,1659` | non-anon | `+ operator` (FR-003 justified) | GAP-3 | MED |
| `/chaos/experiments*` (7) | `handler.py:954-1207` | dev-gated + non-anon | dev-gated + `operator` | GAP-3 | MED |

**Unchanged/confirmed-correct** (documentation only, in spec Appendix A): all owner config routes;
`_require_authenticated_user_id` alert/notification routes; operator `admin/sessions/revoke` +
`users/lookup` (the pattern source); reference anon routes; the anon-ok `GET /health`.

**Explicitly excluded (deferred):** SSE surfaces (rows 96–101), incl. **GAP-1 CRITICAL** (SSE
config-stream IDOR, `sse_streaming/handler.py:356-408`) — carded separately; not touched here.

---

## Remediation Approach

### GAP-2 — `trigger_refresh` (router_v2.py:1320-1324)

Replace the 2-line body with the exact shape of the sibling `get_refresh_status`:

```python
@config_router.post("/api/v2/configurations/<config_id>/refresh")
def trigger_refresh(config_id: str):
    """Trigger manual refresh (T061). Auth + ownership added by Feature 1391 (GAP-2)."""
    event = config_router.current_event.raw_event
    table = get_users_table()

    user_id, err = _require_user_id(event, table=table)   # 401 if no session
    if err:
        return err

    config_data, err = _get_config_with_tickers(table, user_id, config_id)  # 404 if not owner
    if err:
        return err

    result = market_service.trigger_refresh(config_id=config_id)
    return json_response(202, result.model_dump())
```

- Anonymous **session** owners keep access (`_require_user_id` is anon-ok, matching the sibling).
- Non-owner → 404 (no existence oracle). Missing credential → 401. Owner → 202 (unchanged).
- Diff confined to this function (NFR-005, 1384 serialization).

**Rejected alt:** `_require_authenticated_user_id` — would over-lock anonymous owners and diverge from
the 1249 sibling. Rejected.

### GAP-3 — operator-gate `/chaos/*` (handler.py:954-1665)

Attach `middlewares=[require_role_middleware("operator")]` to every `/chaos/*` route decorator
(mutating, control, and read — FR-002 + FR-003):

```python
from src.lambdas.shared.middleware import require_role_middleware  # if not already imported

@app.put("/chaos/gate", middlewares=[require_role_middleware("operator")])
def set_chaos_gate(): ...
@app.post("/chaos/andon-cord", middlewares=[require_role_middleware("operator")])
def pull_chaos_andon_cord(): ...
# ...same for reports*, gate GET, health, metrics, experiments*
```

- The middleware yields 401 (no user_id / no roles claim) and 403 (non-operator), replacing the
  inline `_get_chaos_user_id_from_event → 401` as the primary gate. Keep or drop the inline check;
  if dropped, the middleware preserves 401-for-anonymous (Q in spec §6). Prefer keeping the inline
  check as a harmless second layer to minimize churn, OR remove it in the same commit with a test
  proving 401 still returns for anonymous.
- **Retain** `_is_dev_environment()` on experiment routes and the service-layer
  `check_environment_allowed()` on gate/andon/health/metrics — operator gating is additive DiD, so
  prod stays fail-closed even if role config drifts.
- Powertools attaches `middlewares=` on `@app.<verb>` exactly as on the auth-router operator routes
  (`router_v2.py:773-776`).

**Rejected alt (FR-003):** leave read-only chaos routes on "any authenticated user". Rejected — the
sole consumer is the operator-gated admin dashboard, reads leak operational internals (env name,
baselines, metrics), and no free/anon read flow exists. Gating reads has no UX cost.

### GAP-1 (SSE) — DEFERRED

Not implemented. Referenced in spec §0/§6/Appendix A row 101; carded separately as CRITICAL. #501
stays open pending that work.

---

## Test Strategy (maps FR-004 / FR-005)

- **GAP-2** (`tests/unit/` + `tests/contract/`): `POST .../refresh` → 401 (no auth), 404 (valid
  session, non-owner config), 202 (owner; include an anonymous-session owner). Assert body has no id
  echo on 404.
- **GAP-3** (`tests/unit/`): for a mutating route (`PUT /chaos/gate`, `POST /chaos/andon-cord`) and a
  read route (`GET /chaos/gate`): 401 (no token / anonymous), 403 (free JWT — `roles` without
  `operator`), allowed (operator JWT). Include OPTIONS→not-401/403 (preflight). For experiment
  routes assert the retained `_is_dev_environment()` 404 in a non-dev env stacks with the role gate.
- **Regression (FR-005):** owner-refresh still 202; `GET /health` still anon 200; operator chaos
  access intact.

---

## Adversarial Review #2 (drift + cross-artifact + gate)

- **Drift D1 — "flip the chaos gate in prod" was inaccurate.** The original spec claimed prod
  exposure; `check_environment_allowed()` (`chaos.py:922-932`, allowlist excludes prod) 403s
  gate/andon/health/metrics in prod. **Resolved:** spec §1/Clarification #2 and this plan restate
  the live window as **preprod** (+ lower envs). The operator fix is still required (correct boundary
  + closes preprod). No requirement depends on the false prod claim.
- **Drift D2 — GAP-2 must not over-lock anonymous owners.** Using `_require_authenticated_user_id`
  would break anonymous-session owners and diverge from the 1249 sibling. **Resolved:** plan mandates
  `_require_user_id` (anon-ok) + ownership, matching `router_v2.py:1307`. Cross-checked spec
  Clarification #1 and §6.
- **Drift D3 — OPTIONS preflight.** Adding a role middleware could 401/403 a CORS preflight.
  **Resolved:** `require_role_middleware` runs only on the matched route; preflight is answered by
  the CORS layer / API Gateway mock integration before the handler. Test pins no-401/403-on-OPTIONS.
- **Drift D4 — redundant inline check becomes dead code.** After the middleware lands, the inline
  `_get_chaos_user_id_from_event → 401` is redundant. **Resolved:** plan allows keep-or-remove with a
  test guaranteeing anonymous still 401; not a behavioral gap either way.
- **Drift D5 — GAP-1 silent drop.** SSE IDOR must not vanish. **Resolved:** spec §0/§6/Appendix A row
  101 explicitly mark it CRITICAL-deferred and carded elsewhere; #501 stays open. Cross-artifact:
  tasks.md has NO SSE tasks (verified below) — consistent with deferral, not omission.
- **Cross-artifact C1 — counts.** Active gaps = 2 (GAP-2, GAP-3). Spec FR-001..FR-006, plan two
  fixes, tasks close exactly these two. GAP-1/4/5/6 appear only as Appendix/disposition, never as
  active tasks. Consistent.
- **Cross-artifact C2 — severity labels.** GAP-2 MEDIUM (HIGH abuse potential, MEDIUM rating per
  original), GAP-3 MEDIUM everywhere. Consistent.
- **Cross-artifact C3 — hotspot.** NFR-005 (1384 serialization on `router_v2.py`) is in spec + plan +
  tasks (T-ordering note). Consistent.
- **Gate:** GAP-2 and GAP-3 MUST land with passing FR-004 tests. GAP-1 explicitly deferred; #501 not
  closed by this feature. **PASS.**
