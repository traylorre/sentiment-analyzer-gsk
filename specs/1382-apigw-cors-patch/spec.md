# Feature 1382 — apigw-cors-patch

**Status:** Draft (planning-only; no implementation)
**Branch:** `1382-apigw-cors-patch`
**Type:** Bug fix — Terraform-only (API Gateway CORS)
**Target:** CUSTOMER dashboard API (Amplify → API Gateway → Dashboard Lambda). NOT the HTMX admin dashboard.
**Created:** 2026-07-23

---

## 1. Problem Statement

Saving notification preferences on the customer frontend (Settings → Save Changes) issues
`PATCH /api/v2/notifications/preferences`. The browser first sends a CORS **preflight**
(`OPTIONS`) from the Amplify origin. API Gateway answers the preflight with:

```
Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS
```

PATCH is absent, so the browser blocks the request:

> Method PATCH is not allowed by Access-Control-Allow-Methods in the preflight response.

The Save silently fails for **all** users. This is pre-existing and blocks the feature entirely.

### Root cause (verified, not re-derived)

The backend Lambda is **not** the problem — it already allows PATCH:

- `src/lambdas/dashboard/handler.py:263` → `_CORS_ALLOW_METHODS = "GET,POST,PUT,DELETE,PATCH,OPTIONS"`
- `src/lambdas/dashboard/router_v2.py:1968` → `@notification_router.patch("/api/v2/notifications/preferences")`

The **API Gateway** OPTIONS mock integration that serves this route's preflight advertises a
methods list **without PATCH**. The exact serving path:

1. `/api/v2/notifications/preferences` is **not** an explicit `public_route`. `infrastructure/terraform/main.tf:875-893` declares only `["api","v2","notifications"]` (endpoint, `has_proxy=false`) and `["api","v2","notifications","unsubscribe"]`. Neither creates a `preferences` resource, and `notifications` has no `{proxy+}` child.
2. With no matching explicit resource, the request matches the **root-level `{proxy+}` catch-all** (`aws_api_gateway_resource.proxy`, `main.tf:560`).
3. That catch-all's preflight is served by `aws_api_gateway_integration_response.proxy_options` (`main.tf:619-633`), whose `Access-Control-Allow-Methods` literal is `'GET,POST,PUT,DELETE,OPTIONS'` — **no PATCH** (`main.tf:628`).

Meanwhile the `local.cors_headers` block (`main.tf:217`) **does** include PATCH, but it is only
wired into the explicit leaf/proxy/fr012 OPTIONS integrations (`main.tf:342/411/483/552`). The
`preferences` path never touches those, so the correct value never reaches the browser.

### CORS Allow-Methods audit (entire `api_gateway` module)

`main.tf` is the only file in the module with CORS response params (`variables.tf`/`outputs.tf`
have none). Every occurrence:

| # | Line | Resource / context | Kind | Methods value | PATCH? | Serves the `preferences` preflight? |
|---|------|--------------------|------|---------------|--------|--------------------------------------|
| 1 | 78  | `gateway_response.unauthorized` (401) | gatewayresponse value | `GET,POST,PUT,DELETE,PATCH,OPTIONS` | ✅ | error path only |
| 2 | 103 | `gateway_response.missing_auth_token` (401) | gatewayresponse value | `GET,POST,PUT,DELETE,PATCH,OPTIONS` | ✅ | error path only |
| 3 | 127 | `gateway_response.access_denied` (403) | gatewayresponse value | `GET,POST,PUT,DELETE,PATCH,OPTIONS` | ✅ | error path only |
| 4 | 217 | `local.cors_headers` → explicit OPTIONS integ responses (342/411/483/552) | integration_response value | `GET,POST,PUT,DELETE,PATCH,OPTIONS` | ✅ | ❌ only explicit `public_routes` |
| 5 | 611 | `proxy_options` method_response | header declaration (`true`) | (bool) | n/a | declaration only |
| 6 | **628** | **`proxy_options` integration_response** (root `{proxy+}` catch-all) | **integration_response value** | **`GET,POST,PUT,DELETE,OPTIONS`** | **❌ MISSING** | **✅ YES — the broken one** |
| 7 | 675 | `root_options` method_response | header declaration (`true`) | (bool) | n/a | declaration only |
| 8 | **692** | **`root_options` integration_response** (root `/` OPTIONS) | **integration_response value** | **`GET,POST,PUT,DELETE,OPTIONS`** | **❌ MISSING** | root `/` preflight only |

**Verbs the API actually serves** (grep of `router_v2.py`): GET, POST, **PUT** (1 route:
`config PUT`), **PATCH** (5 routes), DELETE, plus OPTIONS for preflight. Per-verb coverage:

| Verb | 78/103/127 | 217 (cors_headers) | 628 (proxy_options) | 692 (root_options) |
|------|:----------:|:------------------:|:-------------------:|:------------------:|
| GET     | ✅ | ✅ | ✅ | ✅ |
| POST    | ✅ | ✅ | ✅ | ✅ |
| PUT     | ✅ | ✅ | ✅ | ✅ |
| DELETE  | ✅ | ✅ | ✅ | ✅ |
| **PATCH** | ✅ | ✅ | **❌** | **❌** |
| OPTIONS | ✅ | ✅ | ✅ | ✅ |

**Inconsistencies found:** exactly two `Allow-Methods` literals omit PATCH — line **628** (the
one that breaks Save) and line **692** (root path, same drift). No other verb is missing anywhere.

**Secondary drift (out of primary scope, flagged):** the same two literals also carry a *shorter*
`Access-Control-Allow-Headers` list — `'Content-Type,Authorization,X-User-ID,X-Amzn-Trace-Id'`
(lines 627/691) — versus the canonical full list
`'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'` used
at 77/102/126/216 and in the backend `_CORS_ALLOW_HEADERS`. This does **not** block the PATCH
preflight (a JSON PATCH only requests `Content-Type` + `Authorization`, both present), so it is
not required for this fix — see FR-006 for the deliberate decision.

---

## 2. Scope

**In scope**
- Add PATCH to the two API Gateway OPTIONS preflight `Access-Control-Allow-Methods` literals that omit it (lines 628 and 692), so the catch-all and root preflights advertise every verb the API serves.
- Eliminate the drift by consolidating the methods list to a **single canonical `local`** referenced by every `Allow-Methods` occurrence (recommended — see FR-004), so the same literal cannot desync again.

**Out of scope**
- Any backend/Lambda change (already correct).
- The `Access-Control-Allow-Headers` drift (FR-006 records the decision to leave it or fold it into the same consolidation — non-blocking).
- The HTMX admin dashboard, Function URL CORS, SSE Lambda CORS.
- Broadening origins, credentials, or adding new verbs beyond what routes serve.
- Any new AWS resource.

---

## 3. User Scenarios

### US-1 (Primary) — Save notification preferences
**As** a signed-in customer, **when** I toggle a notification setting and click Save Changes,
**then** the `PATCH /api/v2/notifications/preferences` request completes and my preferences persist —
no CORS preflight error.

**Acceptance:**
- From the Amplify origin, the `OPTIONS /api/v2/notifications/preferences` preflight returns 200 with `Access-Control-Allow-Methods` containing `PATCH`.
- The subsequent `PATCH` returns 2xx and the change is saved.
- `Access-Control-Allow-Origin` echoes the Amplify origin from the existing allowlist (never `*`), and `Access-Control-Allow-Credentials: true` is present.

### US-2 — No verb silently missing
**As** an operator, **when** I inspect the preflight for the catch-all and root resources,
**then** every verb the API serves (GET, POST, PUT, DELETE, PATCH, OPTIONS) is advertised, and no
verb the API does *not* serve is added.

### US-3 — Drift cannot recur silently
**As** a maintainer adding a future verb, **when** I update the canonical methods list in one place,
**then** all preflight and gateway-response headers reflect it, with no scattered literal left behind.

---

## 4. Functional Requirements

- **FR-001** The `OPTIONS` preflight for `/api/v2/notifications/preferences` (served by the root `{proxy+}` catch-all, `proxy_options` integration response) MUST advertise `PATCH` in `Access-Control-Allow-Methods`.
- **FR-002** The root `/` OPTIONS preflight (`root_options` integration response, line 692) MUST advertise `PATCH` as well, keeping all preflight surfaces consistent.
- **FR-003** The advertised method set MUST equal exactly the verbs the API serves — `GET,POST,PUT,DELETE,PATCH,OPTIONS` — with **no** verb added that no route uses.
- **FR-004** The methods list SHOULD be defined **once** as a Terraform `local` (e.g. `local.cors_allow_methods = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"`) and referenced by every `Access-Control-Allow-Methods` occurrence (lines 78, 103, 127, 217, 628, 692), so future changes are single-edit and drift is structurally impossible.
- **FR-005** `Access-Control-Allow-Origin` MUST remain the existing explicit allowlist behavior (`local.cors_origin` / `method.request.header.origin`), never `*`. `Access-Control-Allow-Credentials: true` MUST be preserved. No origin/credentials semantics change.
- **FR-006** The `Access-Control-Allow-Headers` value on the two catch-all/root literals MAY be folded into the same consolidation for consistency, but this is **non-blocking** for the PATCH fix; if folded, it MUST match the canonical full header list and MUST NOT use `*` (documented "CORS wildcard + credentials" gotcha). If not folded, the divergence is recorded as a known, accepted low-severity item.
- **FR-007** The change MUST be Terraform-only, introduce **no** new AWS resources, and MUST re-deploy the API Gateway stage so the new integration response takes effect (a deployment redeploy trigger already covers method/integration changes).
- **FR-008** After `terraform apply` to **preprod** (real AWS), the fix MUST be verified against the live API Gateway from the Amplify origin: the preflight advertises PATCH and the `PATCH` succeeds end-to-end.

## 5. Non-Functional Requirements

- **NFR-001 (Security)** Do not broaden CORS. Origin stays on the explicit allowlist; credentials unchanged; only verbs the API serves are advertised.
- **NFR-002 (No infra growth)** Reuse the existing API Gateway; zero new resources; standing "no new AWS resources" constraint honored.
- **NFR-003 (Idempotent/least-diff)** Prefer the smallest correct diff that also removes the drift class (one `local` + reference swaps).
- **NFR-004 (Deploy safety)** GPG-signed commits; validated via `terraform fmt`/`validate` before push; preprod-first, prod later via the normal pipeline.

## 6. Success Criteria

1. `OPTIONS` preflight for `/api/v2/notifications/preferences` from the Amplify origin returns `Access-Control-Allow-Methods` including `PATCH`.
2. `PATCH /api/v2/notifications/preferences` succeeds from the customer dashboard; Save Changes persists.
3. No other verb the API serves is missing from any preflight; no unused verb is added.
4. `Access-Control-Allow-Origin` is the explicit Amplify origin (not `*`); credentials preserved.
5. Verified on real preprod after apply. Terraform-only change; no new resources.

## 7. Assumptions & Dependencies

- The API Gateway deployment/stage redeploys on integration-response change (existing `public_route_resource_ids` trigger + standard deploy pipeline handle this).
- Preprod `cors_allowed_origins` already contains the Amplify origin (`main.tf:868`, non-empty enforced for prod; preprod set via tfvars).
- Preflight caching (`Access-Control-Max-Age`) is not currently emitted by these OPTIONS responses; if a browser cached a *failed* preflight, a hard refresh / cache bust may be needed to observe the fix (see Adversarial Review #1).

## 8. Out-of-Scope / Deferred

- Header-list consolidation beyond methods (FR-006) — decided non-blocking.
- Any refactor of the explicit-vs-catch-all routing model.

---

## Adversarial Review #1

**Reviewer stance:** assume the one-line fix is a trap. Attack redeploy semantics, drift
recurrence, preflight caching, and credentials/origin correctness.

### Findings

| ID | Sev | Attack | Finding | Resolution |
|----|-----|--------|---------|-----------|
| H1 | HIGH | "It applies but nothing changes." | The `aws_api_gateway_deployment` redeploy trigger (`main.tf:739-756`) hashes resource **`.id`** values. An `integration_response` `.id` is derived from rest_api/resource/method/status — it does **not** change when only `response_parameters` change. So editing the `Allow-Methods` literal at line 628/692 alone leaves the trigger hash unchanged → **no new deployment → the stage keeps serving the old preflight** and the fix appears to do nothing after `apply`. This is the classic API Gateway "changed config, forgot to redeploy" trap. | **Amend FR-007:** the redeployment `triggers` MUST incorporate the CORS methods **value** (e.g. hash `local.cors_allow_methods` / the integration-response param maps), not just resource IDs, so any verb-list change forces a stage redeploy. Added as FR-007a below. |
| M1 | MED | "You fixed 628, forgot 692." | Root `/` OPTIONS (line 692) has the identical PATCH omission. | Already covered by FR-002; consolidation (FR-004) fixes both at once. No spec change. |
| M2 | MED | "Preflight still fails on headers." | Lines 627/691 carry a shorter `Allow-Headers` list. | Non-blocking for a JSON PATCH (only `Content-Type`+`Authorization` requested, both present). Recorded by FR-006 as accepted; may be folded into the same `local`. No gate impact. |
| L1 | LOW | "Preflight cache hides the result." | No `Access-Control-Max-Age` is emitted by these OPTIONS responses (`grep` = none), so there's no long server-set cache. But browsers still cache preflights per their own default heuristic; a previously-cached **failed** preflight can linger for the session. | Verification (FR-008) MUST use a fresh browser context / cache-bust (or `curl -X OPTIONS`) so a stale negative cache doesn't mask the fix. Added to plan validation steps. |
| L2 | LOW | "Consolidation breaks the mapping." | API Gateway response-parameter values must be single-quote-wrapped (`'GET,...'`). A `local` that drops the quotes would break every reference. | The canonical `local` MUST retain the `'…'` wrapping exactly as the current literals. Captured for the plan. |
| L3 | LOW | "You broadened CORS." | Confirm origin/credentials unchanged. | `Allow-Origin` stays `'${local.cors_origin}'` (allowlist, never `*`; validation at `variables.tf:143`); `Allow-Credentials: true` preserved. Verb set equals exactly the routes served. No broadening. Confirmed, no change. |

### Spec edits applied
- **FR-007a (new):** The `aws_api_gateway_deployment.dashboard` `triggers` map MUST include the CORS methods value (and, if FR-006 folds headers, the headers value) so a verb/header change produces a new deployment. Without this, the stage will not serve the corrected preflight.
- FR-008 clarified to require a cache-busted / fresh-context preflight check.

### Gate
- CRITICAL: **0**
- HIGH: **0** (H1 resolved by FR-007a)

**PASS — 0 CRITICAL / 0 HIGH.** Proceed to Plan.

---

## Clarifications

Self-answered from the codebase (no owner input required). Max 5.

**C1 — Does the preflight `Allow-Origin` actually resolve to the Amplify origin in preprod, or `*`?**
Resolved. `local.cors_origin = cors_allowed_origins[0]` (`main.tf:213`). `preprod.tfvars:25-30`
sets `cors_allowed_origins[0] = "https://main.d29tlmksqcx494.amplifyapp.com"` (the customer
Amplify origin). So the MOCK preflight returns that exact origin, never `*`. FR-005 satisfied by
existing config; no change needed. (Note: MOCK integrations can't echo `method.request.header.origin`,
so it's a single static allowlisted origin — correct for the customer dashboard.)

**C2 — Do the explicit `public_route` OPTIONS integrations already carry PATCH (i.e., is the bug
truly only the catch-all)?**
Resolved. `fr012_options`, `public_leaf_options`, `public_proxy_options`, `fr012_proxy_options`
integration responses all set `response_parameters = local.cors_headers` (`main.tf:342/411/483/552`),
and `local.cors_headers` includes PATCH (`main.tf:217`). So every explicit route is already correct;
the omission is isolated to the two hardcoded literals (628 `proxy_options`, 692 `root_options`).
Confirms the audit.

**C3 — Which verbs must the advertised set contain — exactly?**
Resolved. `router_v2.py` decorators: GET, POST, **PUT** (1: `config_router.put`), **PATCH** (5),
DELETE, + OPTIONS for preflight. Canonical set = `GET,POST,PUT,DELETE,PATCH,OPTIONS` — identical to
the backend `_CORS_ALLOW_METHODS` (`handler.py:263`). No verb beyond these is served, so none should
be advertised beyond them (FR-003).

**C4 — Will a param-only edit actually redeploy the stage?**
Resolved (from AR#1 H1). No — the `aws_api_gateway_deployment` trigger hashes resource `.id`s
(`main.tf:741-755`), unchanged by param-only edits. FR-007a requires adding the methods value to the
trigger. This is a required part of the fix, not optional.

**C5 — Is the `Allow-Headers` short-list at 627/691 a blocker for the PATCH Save?**
Resolved. No. A JSON PATCH from the frontend requests only `Content-Type` + `Authorization`, both
present in the short list, so the preflight passes on headers. The divergence is cosmetic/drift, not
functional for US-1. FR-006 folds it into the consolidation opportunistically; dropping it does not
affect the fix.

**Deferred to owner:** none. All questions resolved from code + tfvars.
