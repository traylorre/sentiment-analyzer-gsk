# Feature Specification: Route Frontend Through API Gateway + Enable Cognito Auth

**Feature Branch**: `1253-api-gateway-cognito-auth`
**Created**: 2026-03-24
**Status**: Draft
**Input**: "Resolve split-brain architecture: route all frontend REST traffic through API Gateway with Cognito JWT auth, keep public endpoints unauthenticated. Feature 1253 in DDoS/auth hardening series. Threat model: state-sponsored attacker. Consider all authorization levels, orphaned endpoints, dependency compromise vectors."

## Context

### Current Architecture (Split-Brain)

The sentiment analyzer has a split-brain architecture where two parallel request paths exist:

1. **API Gateway** (REST API, stage `v1`): Rate limiting at 100 req/s per API key (NOT per IP). Cognito authorizer built but **DISABLED** (`enable_cognito_auth = false`). Proxies to Dashboard Lambda via `{proxy+}` catch-all.

2. **Lambda Function URLs** (`authorization_type = NONE`): ALL frontend traffic currently flows here. Every request — valid or not — invokes Lambda at $0.20/million. No infrastructure-level auth.

The frontend (`NEXT_PUBLIC_API_URL`) points to the Dashboard Lambda Function URL, bypassing API Gateway entirely. The Amplify module comment reads: "Feature 1114: Use Lambda Function URL (has CORS) instead of API Gateway (no CORS on proxy)."

### Cognito State

The Cognito User Pool is fully configured:
- MFA: Optional (software token enabled)
- OAuth: Google + GitHub providers, PKCE code flow
- Client scopes: `["email", "openid", "profile"]` — does NOT include custom resource server scopes (`read:config`, `write:config`, `read:alerts`, `write:alerts`)
- Token validity: Access=1h, ID=1h, Refresh=30d
- Advanced security: AUDIT (dev), ENFORCED (prod)
- Deletion protection: ACTIVE in prod

**Scope decision**: This feature uses JWT signature + expiry validation only (no scope-based authorization at API Gateway). The client's `allowed_oauth_scopes` does not include custom scopes, so scope enforcement would reject all tokens.

### Endpoint Inventory (65 endpoints audited)

Full audit of `handler.py`, `router_v2.py`, and SSE handler reveals 65 endpoints across 4 security zones. Classification for this feature:

**Public at API Gateway** (no Cognito JWT required — these serve pre-auth flows, public data, or infrastructure):

| Endpoint | Method | Reason Public |
|----------|--------|---------------|
| `/health` | GET | Deploy smoke tests, monitoring |
| `/api/v2/runtime` | GET | Frontend app initialization (SSE URL discovery) |
| `/api/v2/auth/anonymous` | POST | Session creation (user has no token yet) |
| `/api/v2/auth/magic-link` | POST | Magic link request (pre-auth flow) |
| `/api/v2/auth/magic-link/verify` | GET | Magic link verification (pre-auth) |
| `/api/v2/auth/oauth/urls` | GET | OAuth provider URLs (pre-auth) |
| `/api/v2/auth/oauth/callback` | POST | OAuth callback processing (pre-auth) |
| `/api/v2/auth/refresh` | POST | Token refresh (uses httpOnly cookie, not JWT) |
| `/api/v2/auth/validate` | GET | Session validation (checks existing token validity) |
| `/api/v2/tickers/*` | GET | Ticker search/validate (anonymous users need this) |
| `/api/v2/market/*` | GET | Market status (anonymous users need this) |
| `/api/v2/timeseries/*` | GET | Public sentiment data (anonymous users need this) |
| `/api/v2/notifications/unsubscribe` | GET | Email unsubscribe link (token in query param) |

**Protected at API Gateway** (Cognito JWT required — user data, state changes, admin):

| Endpoint Group | Reason Protected |
|----------------|-----------------|
| `/api/v2/configurations/*` | User-specific config data (CRUD + analytics) |
| `/api/v2/alerts/*` | User-specific alert rules |
| `/api/v2/notifications/*` (except unsubscribe) | User-specific notification preferences |
| `/api/v2/auth/extend` | Extends authenticated session |
| `/api/v2/auth/signout` | Revokes session |
| `/api/v2/auth/session` | Session details |
| `/api/v2/auth/me` | User profile |
| `/api/v2/auth/revoke-sessions` | ADMIN: Bulk revoke (orphaned — never called by frontend) |
| `/api/v2/auth/check-email` | Email enumeration risk — should be auth-protected |
| `/api/v2/auth/link-accounts` | Account linking (orphaned) |
| `/api/v2/auth/merge-status` | Account merging (orphaned) |
| `/api/v2/auth/merge` | Account merging (orphaned) |
| `/api/v2/users/lookup` | ADMIN: User lookup (orphaned) |
| `/api/v2/metrics` | Dashboard metrics (orphaned) |
| `/api/v2/sentiment` | Sentiment by tags (orphaned) |
| `/api/v2/trends` | Trend data (orphaned) |
| `/api/v2/articles` | News articles (orphaned) |

**Admin-only** (dev environment gate — blocked in prod before any auth check):

| Endpoint | Gate |
|----------|------|
| `/` (index), `/favicon.ico`, `/chaos`, `/static/*`, `/api` | `_is_dev_environment()` → 404 in prod |
| `/chaos/experiments/*` (7 routes) | `check_environment_allowed()` + auth |

**SSE Streaming** (separate Lambda — out of scope for Feature 1253):

| Endpoint | Auth | Note |
|----------|------|------|
| `/api/v2/stream` | Optional Bearer | Global SSE stream |
| `/api/v2/stream/status` | None | Connection pool JSON |
| `/api/v2/configurations/{id}/stream` | Bearer required | Config-specific SSE |

### Orphaned Endpoints (15 identified)

Endpoints defined in handler.py/router_v2.py but **never called by any frontend code**:

1. `/api/v2/sentiment` — defined in handler.py, no frontend caller
2. `/api/v2/trends` — defined in handler.py, no frontend caller
3. `/api/v2/articles` — defined in handler.py, no frontend caller
4. `/api/v2/metrics` — defined in handler.py, no frontend caller
5. `/api/v2/auth/revoke-sessions` — admin endpoint, no UI
6. `/api/v2/auth/check-email` — account linking, no UI
7. `/api/v2/auth/link-accounts` — account linking, no UI
8. `/api/v2/auth/merge-status` — account merging, no UI
9. `/api/v2/auth/merge` — account merging, no UI
10. `/api/v2/auth/session/refresh` — duplicate of `/refresh`
11. `/api/v2/configurations/{id}/heatmap` — advanced analytics, no UI
12. `/api/v2/configurations/{id}/volatility` — advanced analytics, no UI
13. `/api/v2/configurations/{id}/correlation` — advanced analytics, no UI
14. `/api/v2/configurations/{id}/premarket` — pre-market data, no UI
15. `/api/v2/users/lookup` — admin endpoint, no UI

These are still Cognito-protected (they fall through to `{proxy+}` catch-all) — no security gap, but they represent dead code.

### Threat Model

**Attacker profile**: State-sponsored, persistent, with resources for:
- Lambda Function URL discovery (DNS enumeration, CloudTrail leaks, GitHub search)
- Credential stuffing against Cognito (mitigated by MFA + advanced security)
- Dependency compromise via supply chain (torch 2.9.1 = 2GB binary, transformers 4.57.3, PyJWT 2.10.1)
- Network interception if HTTPS not enforced
- Token brute force (magic link: 6-char token ≈ 19B combinations)
- Email enumeration via `/api/v2/auth/magic-link` and `/api/v2/auth/check-email`
- XSS exploitation to steal CSRF token (stored in non-httpOnly cookie)
- Budget exhaustion via flooding public endpoints

**What this feature prevents**:
- Unauthenticated access to protected endpoints at infrastructure level ($0 cost for invalid tokens)
- Token validation at compute level (Cognito validates before Lambda invocation)
- Direct Lambda Function URL access from internet (Feature 1256 completes this restriction)

**What this feature does NOT prevent** (deferred to other features):
- Per-IP rate limiting (Feature 1254: WAF)
- SSE stream abuse (Feature 1255: CloudFront + WAF)
- Direct Function URL bypass (Feature 1256: resource policy restriction)
- Magic link token brute force (separate hardening task)
- Email enumeration (separate hardening task)
- Missing CSP/HSTS headers (separate hardening task)

### Out of Scope

- SSE streaming path (requires CloudFront — Feature 1255)
- WAF rules and per-IP rate limiting (Feature 1254)
- Restricting Lambda Function URLs (Feature 1256)
- Changing application-level auth logic (keeps existing defense-in-depth)
- Migrating from REST API to HTTP API (would require module rewrite)
- Cognito scope-based authorization at API Gateway level (scopes not in client's `allowed_oauth_scopes`)
- Frontend 401→sign-in redirect logic (frontend's `ApiClientError` chain already handles 401; `use-auth.ts` auto-refreshes tokens and signs out on failure)
- Orphaned endpoint cleanup (separate task — no security impact since they're Cognito-protected)
- Magic link token entropy increase (separate security task)
- Email enumeration mitigation (separate security task)
- CSP/HSTS security headers (separate security task)

### Security Zone Map (After Feature 1253)

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERNET                                  │
│                       │                                      │
│    ┌──────────────────▼──────────────────┐                  │
│    │      API GATEWAY (REST API v1)       │                  │
│    │  Rate: 100 req/s per API key         │                  │
│    │                                      │                  │
│    │  ┌────────────────────────────────┐  │                  │
│    │  │  ZONE A: Public Routes         │  │                  │
│    │  │  auth=NONE, ANY method         │  │                  │
│    │  │  /health, /auth/anonymous,     │  │                  │
│    │  │  /auth/magic-link/*, /oauth/*, │  │                  │
│    │  │  /auth/refresh, /auth/validate,│  │                  │
│    │  │  /tickers/*, /market/*,        │  │                  │
│    │  │  /timeseries/*, /runtime,      │  │                  │
│    │  │  /notifications/unsubscribe    │  │                  │
│    │  └───────────────┬────────────────┘  │                  │
│    │                  │                    │                  │
│    │  ┌───────────────▼────────────────┐  │                  │
│    │  │  ZONE B: Cognito Protected     │  │                  │
│    │  │  auth=COGNITO_USER_POOLS       │  │                  │
│    │  │  /{proxy+} catch-all           │  │                  │
│    │  │  Invalid JWT → 401 + CORS      │  │                  │
│    │  │  UUID token → 401 + CORS       │  │                  │
│    │  │  Valid JWT → pass to Lambda     │  │                  │
│    │  └───────────────┬────────────────┘  │                  │
│    └──────────────────┼──────────────────┘                  │
│                       │                                      │
│    ┌──────────────────▼──────────────────┐                  │
│    │      DASHBOARD LAMBDA               │                  │
│    │                                      │                  │
│    │  ┌────────────────────────────────┐  │                  │
│    │  │  ZONE C: Application Auth      │  │                  │
│    │  │  Bearer token → DynamoDB       │  │                  │
│    │  │  Session validation            │  │                  │
│    │  │  Per-user data isolation       │  │                  │
│    │  │  CSRF on state-changing ops    │  │                  │
│    │  └────────────────────────────────┘  │                  │
│    │                                      │                  │
│    │  ┌────────────────────────────────┐  │                  │
│    │  │  ZONE D: Admin/Dev-Only        │  │                  │
│    │  │  Environment gate → 404 prod   │  │                  │
│    │  │  /, /chaos, /static/*, /api    │  │                  │
│    │  └────────────────────────────────┘  │                  │
│    └─────────────────────────────────────┘                  │
│                                                              │
│    ┌─────────────────────────────────────┐   DIRECT ACCESS  │
│    │   LAMBDA FUNCTION URLs (NONE auth)  │ ◄── Still open   │
│    │   Dashboard + SSE streaming         │   (Feature 1256) │
│    └─────────────────────────────────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### Dependency Risk Assessment

High-risk dependencies that handle auth/crypto or have large attack surface:

| Package | Risk | Relevance to Feature 1253 |
|---------|------|--------------------------|
| `PyJWT 2.10.1` | JWT handling — no algorithm enforcement if misconfigured | Direct: Cognito JWT validation at API Gateway bypasses this, but application-level JWT decode must enforce algorithm |
| `sendgrid 6.12.5` | Email API key in Secrets Manager | Indirect: magic link emails sent via this |
| `stripe 14.1.0` | Payment API key in Secrets Manager | None: unrelated to auth |
| `torch 2.9.1` + `transformers 4.57.3` | 2GB+ binary, supply chain risk | None: ML inference, not in auth path |
| `requests 2.32.5` | SSRF if attacker controls URL | Indirect: used for external API calls |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Protected Endpoints Reject Invalid Tokens at API Gateway (Priority: P1)

All endpoints under `/api/v2/configurations/*`, `/api/v2/alerts/*`, `/api/v2/notifications/*` (except unsubscribe), `/api/v2/auth/extend`, `/api/v2/auth/signout`, `/api/v2/auth/session`, `/api/v2/auth/me`, and all orphaned endpoints require a valid Cognito JWT. Requests without a token, with a UUID token, or with an expired JWT receive 401 from API Gateway **before Lambda is invoked** — zero compute cost.

**Why this priority**: Core value — shifts auth from $0.20/M Lambda invocations to $0 API Gateway rejection for invalid requests.

**Independent Test**: Send a request to `GET /api/v2/configurations` through API Gateway without a token. Verify 401 response and that Lambda invocation count does NOT increase.

**Acceptance Scenarios**:

1. **Given** a request to `GET /api/v2/configurations` through API Gateway without an Authorization header, **When** API Gateway processes it, **Then** it returns 401 with `{"message":"Unauthorized"}` and CORS headers, without invoking Lambda.
2. **Given** a request with a valid Cognito JWT to `GET /api/v2/configurations`, **When** API Gateway validates the JWT, **Then** Lambda is invoked and returns the user's configurations.
3. **Given** a request with an expired Cognito JWT to any protected endpoint, **Then** API Gateway returns 401 with CORS headers, without invoking Lambda.
4. **Given** a request with a UUID anonymous token (not a Cognito JWT) to `GET /api/v2/configurations`, **Then** API Gateway returns 401 (UUID format is not a valid JWT).
5. **Given** a request to an orphaned endpoint (`GET /api/v2/sentiment`) without a Cognito JWT, **Then** API Gateway returns 401 (falls through to protected `{proxy+}` catch-all).

---

### User Story 2 — Public Endpoints Remain Accessible Without Cognito JWT (Priority: P1)

Auth-flow endpoints, public data endpoints, the health check, and the email unsubscribe link remain accessible without a Cognito JWT. This is required because: (a) anonymous session creation happens before the user has a JWT, (b) anonymous users search tickers and view market data using UUID session tokens, (c) deploy smoke tests hit `/health` without auth, (d) email unsubscribe links use query-param tokens.

**Why this priority**: Breaking these endpoints blocks sign-in, anonymous user experience, deploys, and email unsubscribe compliance.

**Independent Test**: Send `POST /api/v2/auth/anonymous` through API Gateway without any token. Verify 201 success.

**Acceptance Scenarios**:

6. **Given** a request to `POST /api/v2/auth/anonymous` through API Gateway without auth, **Then** Lambda is invoked and returns 201 with a session token.
7. **Given** a request to `GET /api/v2/tickers/search?q=AAPL` with a UUID token (not Cognito JWT), **Then** API Gateway passes it through (no Cognito check), Lambda validates the UUID session, returns 200.
8. **Given** a request to `GET /health` without auth, **Then** returns 200 `{"status":"healthy"}`.
9. **Given** a request to `POST /api/v2/auth/oauth/callback` without auth, **Then** processes OAuth flow normally.
10. **Given** a request to `GET /api/v2/market/status` with a UUID token, **Then** passes through to Lambda (no Cognito check).
11. **Given** a request to `GET /api/v2/notifications/unsubscribe?token=xxx`, **Then** passes through (no Cognito check), Lambda validates the unsubscribe token.

---

### User Story 3 — Frontend Routes Through API Gateway (Priority: P1)

The customer frontend (Amplify/Next.js) uses the API Gateway URL as its API endpoint instead of the Lambda Function URL. This routes all REST traffic through the API Gateway rate limiter and Cognito authorizer.

**Why this priority**: Without this, Cognito auth on API Gateway is useless — traffic bypasses it via Function URL.

**Independent Test**: Verify Amplify environment variable `NEXT_PUBLIC_API_URL` is set to API Gateway URL including stage prefix `/v1`.

**Acceptance Scenarios**:

12. **Given** the Amplify deployment, **When** the frontend initializes, **Then** `NEXT_PUBLIC_API_URL` resolves to `https://{rest_api_id}.execute-api.{region}.amazonaws.com/v1`.
13. **Given** the frontend makes a request to a protected endpoint with a valid Cognito JWT, **Then** the request succeeds through API Gateway.
14. **Given** the deploy pipeline runs smoke tests, **Then** it verifies the health endpoint through the API Gateway URL.

---

### User Story 4 — 401 Responses Include CORS Headers (Priority: P1)

When API Gateway returns 401 for unauthorized requests, the response MUST include CORS headers so the browser exposes the error to JavaScript. Without CORS headers, the browser silently drops the 401 body (the frontend uses `credentials: 'include'`).

**Why this priority**: Without this, the frontend cannot detect auth failures and cannot redirect to sign-in. The entire auth UX breaks silently.

**Independent Test**: Send a request without auth to a protected endpoint. Verify the 401 response includes `Access-Control-Allow-Origin` and `Access-Control-Allow-Credentials: true`.

**Acceptance Scenarios**:

15. **Given** a request to a protected endpoint without auth, **When** API Gateway returns 401, **Then** the response includes `Access-Control-Allow-Origin` (matching the request Origin), `Access-Control-Allow-Credentials: true`, and explicit `Access-Control-Allow-Headers` list (NOT wildcard `*`).
16. **Given** an OPTIONS preflight request to any public or protected resource, **Then** it returns 200 with CORS headers and no Cognito check.

---

### User Story 5 — Existing Anonymous Sessions Continue Working (Priority: P2)

Users with anonymous sessions (UUID Bearer tokens from `/api/v2/auth/anonymous`) can still use public and session-management endpoints. Protected endpoints return 401 from API Gateway (UUID is not a valid Cognito JWT), and the frontend's existing auth error handling redirects to sign-in.

**Why this priority**: Existing anonymous users should not experience sudden breakage. Graceful degradation.

**Acceptance Scenarios**:

17. **Given** an anonymous user with a UUID token accessing `GET /api/v2/tickers/search`, **Then** it works (public route, no Cognito check, Lambda validates UUID session).
18. **Given** an anonymous user with a UUID token accessing `GET /api/v2/configurations`, **Then** API Gateway returns 401 (UUID is not a valid Cognito JWT). The frontend's `ApiClientError` chain detects the 401, and `use-auth.ts` redirects to sign-in.

---

### Edge Cases

- **Cognito User Pool deleted/misconfigured**: API Gateway returns 500 for all protected endpoints. Mitigation: Cognito has `deletion_protection = ACTIVE` in prod.
- **CORS wildcard with credentials**: `Access-Control-Allow-Headers: *` is treated as literal `*` when `credentials: 'include'` is used. MUST use explicit header list: `Content-Type, Authorization, Accept, Cache-Control, Last-Event-ID, X-Amzn-Trace-Id, X-User-ID`.
- **Partial deployment**: If Cognito enabled on `{proxy+}` before public overrides exist, ALL endpoints require auth (including `/health`). Breaks deploys. MUST be atomic — single `terraform apply`.
- **Amplify env var timing**: API Gateway URL is a Terraform output; Amplify needs it as env var. Solution: pass `module.api_gateway.api_endpoint` to Amplify module via variable. No chicken-and-egg — `depends_on` ensures ordering.
- **API Gateway resource hierarchy**: Explicit resources override `{proxy+}`. Intermediate resources (`/api`, `/api/v2`, `/api/v2/auth`) serve as parent nodes without methods. `{proxy+}` children under group prefixes (e.g., `/api/v2/tickers/{proxy+}`) are valid — each is a child of a non-proxy resource.
- **`ANY` vs specific HTTP methods on public routes**: Using `ANY` method prevents method-mismatch fallthrough to Cognito-protected `{proxy+}`. A `GET`-only public override would let `POST` requests fall through and require Cognito auth unexpectedly.
- **OPTIONS preflight**: Each new explicit public resource needs its own `OPTIONS` method with `authorization = "NONE"` and MOCK integration. The existing `{proxy+}` OPTIONS handler does NOT apply to child resources.
- **Rate limiting scope**: Current 100 req/s is per API key, not per IP. A single attacker can consume the entire quota. Per-IP limiting requires WAF (Feature 1254).
- **`prevent_destroy` on authorizer**: Accidental deletion of the Cognito authorizer breaks all protected endpoints. Add lifecycle protection.
- **`/api/v2/notifications/unsubscribe`**: This endpoint uses a query-param token (not Bearer), must be public. It was not in the original public endpoint list — added after audit.
- **`/api/v2/auth/check-email`**: Currently public (CSRF only). This is an email enumeration vector. Classify as protected (Cognito JWT required) to reduce attack surface.
- **Intermediate resources that are also endpoints**: Creating `/api/v2/notifications` as an intermediate (parent of `/unsubscribe`) would break `GET /api/v2/notifications` — API Gateway returns 403 when a resource exists but has no matching method (does NOT fall back to `{proxy+}`). Fix: add `ANY` method with appropriate auth on intermediates that serve double duty. Same applies to `/api/v2/auth/magic-link` (parent of `/{proxy+}` for verify, but also handles POST directly).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: API Gateway MUST enable Cognito JWT authorization on the `{proxy+}` catch-all route by setting `enable_cognito_auth = true` and providing `cognito_user_pool_arn`.
- **FR-002**: The following 11 public resource groups (covering 13+ individual endpoints) MUST remain unauthenticated at API Gateway level. Implementation uses explicit API Gateway resources with `authorization = "NONE"` and `ANY` method that override the `{proxy+}` catch-all.

  **Implementation**: REST API resources are hierarchical — explicit paths take priority over `{proxy+}`. Intermediate resources (`/api`, `/api/v2`, `/api/v2/auth`) are parent nodes without methods — **EXCEPT** when an intermediate is also an endpoint path (see FR-012).

  Public resource groups (each gets `ANY` + `OPTIONS`):
  - `/api/v2/auth/anonymous` — session creation (pre-auth)
  - `/api/v2/auth/magic-link` + `/api/v2/auth/magic-link/{proxy+}` — magic link request (POST on parent) + verify (GET on child). **The parent resource IS an endpoint** — it needs its own `ANY` method with `NONE` auth.
  - `/api/v2/auth/oauth/{proxy+}` — OAuth URLs + callback (pre-auth)
  - `/api/v2/auth/refresh` — token refresh (uses httpOnly cookie, not JWT)
  - `/api/v2/auth/validate` — session validation (pre-auth check)
  - `/api/v2/tickers/{proxy+}` — ticker search/validate (anonymous users)
  - `/api/v2/market/{proxy+}` — market status (anonymous users)
  - `/api/v2/timeseries/{proxy+}` — public sentiment data (anonymous users)
  - `/api/v2/notifications/unsubscribe` — email unsubscribe (token in query param)
  - `/health` — deploy smoke tests + monitoring
  - `/api/v2/runtime` — SSE URL discovery + app initialization

- **FR-003**: The Amplify frontend MUST set `NEXT_PUBLIC_API_URL` to the API Gateway endpoint URL including stage prefix `/v1`.
- **FR-004**: Deploy pipeline smoke tests MUST verify the health endpoint through the API Gateway URL (in addition to existing Lambda direct-invoke test).
- **FR-005**: Every new explicit public resource MUST have its own `OPTIONS` method with `authorization = "NONE"` and MOCK integration returning CORS headers. The existing `{proxy+}` OPTIONS handler does NOT apply to child resources.
- **FR-006**: Application-level auth (session validation, `_require_user_id()`, CSRF checks) MUST remain as defense-in-depth. Cognito auth at API Gateway is an additional layer, not a replacement.
- **FR-007**: All public resource overrides and the Cognito authorizer enablement MUST be deployed atomically in a single `terraform apply`.
- **FR-008**: API Gateway 401 (`UNAUTHORIZED`), 401 (`MISSING_AUTHENTICATION_TOKEN`), and 403 (`ACCESS_DENIED`) Gateway Response templates MUST include CORS headers: `Access-Control-Allow-Origin` (from request Origin), `Access-Control-Allow-Headers` (explicit list, NOT `*`), `Access-Control-Allow-Credentials: true`, `Access-Control-Allow-Methods`.
- **FR-009**: The Cognito authorizer MUST validate JWT signature and expiry only (`authorization_scopes` not set). Setting scopes would reject all tokens because the client's `allowed_oauth_scopes` doesn't include custom resource server scopes.
- **FR-010**: The Amplify `NEXT_PUBLIC_API_URL` MUST include the stage prefix `/v1`. Frontend routes like `/api/v2/configurations` become `https://...amazonaws.com/v1/api/v2/configurations`.
- **FR-011**: `/api/v2/auth/check-email` MUST be classified as protected (Cognito JWT required) — it currently accepts unauthenticated requests and is an email enumeration vector.
- **FR-012**: Intermediate resources that are ALSO endpoint paths MUST have their own methods. Without methods, API Gateway returns 403 `Missing Authentication Token` instead of routing to `{proxy+}` — breaking the endpoint for all users. Affected paths:
  - `/api/v2/notifications` — MUST have `ANY` method with `authorization = "COGNITO_USER_POOLS"` + Lambda proxy integration (it serves `GET /api/v2/notifications` to list notifications, which is a protected endpoint)
  - `/api/v2/auth/magic-link` — MUST have `ANY` method with `authorization = "NONE"` + Lambda proxy integration (it serves `POST /api/v2/auth/magic-link` to send magic link, which is a public endpoint)

### Key Entities

- **Cognito JWT**: Access token issued by Cognito after authentication. Contains `sub`, `iss`, `aud`, `exp`. Validated by API Gateway authorizer (signature + expiry). Cached for 300 seconds.
- **Anonymous Session Token**: UUID-format Bearer token created by `/api/v2/auth/anonymous`. NOT a Cognito JWT. Rejected by Cognito authorizer on protected endpoints. Accepted by application-level auth on public endpoints.
- **Public Route**: An API Gateway resource with `authorization = "NONE"` that overrides the `{proxy+}` Cognito-protected catch-all. Uses `ANY` method to prevent method-mismatch fallthrough.
- **Gateway Response**: API Gateway's response for auth failures (401/403). Must include CORS headers for browser compatibility with `credentials: 'include'`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Requests to protected endpoints without a valid Cognito JWT return 401 from API Gateway (verifiable: Lambda invocation count does NOT increase).
- **SC-002**: All 11 public resource groups (covering 13+ individual endpoints) return 200/201 through API Gateway without a Cognito JWT.
- **SC-003**: Frontend Amplify deployment uses API Gateway URL (with `/v1` prefix) as `NEXT_PUBLIC_API_URL`.
- **SC-004**: Deploy smoke tests pass using API Gateway URL.
- **SC-005**: Existing Playwright E2E tests pass through API Gateway path (zero functional regression).
- **SC-006**: 401 responses from API Gateway include CORS headers and are visible to browser JavaScript (not silently dropped).
- **SC-007**: Anonymous users with UUID tokens can still search tickers and view market data through public endpoints.
- **SC-008**: All 15 orphaned endpoints are Cognito-protected (they fall through to `{proxy+}` catch-all).

## Assumptions

- Cognito User Pool ARN available as `module.cognito.user_pool_arn` (verified: `outputs.tf`).
- Explicit API Gateway resources take priority over `{proxy+}` (verified: AWS documentation).
- Frontend sends Bearer tokens via `Authorization` header for all requests (`client.ts` lines 135-139, verified). Cognito JWT for authenticated, UUID for anonymous.
- API Gateway stage name is `v1` (verified: `stage_name = "v1"` in main.tf).
- Intermediate resources can exist without methods as parent nodes (verified: AWS documentation).
- `{proxy+}` children under group prefixes are valid — each is a child of a non-proxy resource, not a child of another `{proxy+}` (verified: "A proxy resource can only be a child of a non-proxy resource").
- Cognito authorizer caches validated tokens for 300 seconds (default TTL).
- The frontend's `ApiClientError` chain in `client.ts` correctly surfaces 401 responses, and `use-auth.ts` handles session expiry with auto-refresh (verified: lines 72-129).
