# Feature Specification: Route Frontend Through API Gateway + Enable Cognito Auth

**Feature Branch**: `1253-api-gateway-cognito-auth`
**Created**: 2026-03-24
**Status**: Draft (post-adversarial-v1)
**Input**: "Resolve split-brain architecture: route all frontend REST traffic through API Gateway with Cognito JWT auth, keep public endpoints unauthenticated"

## Context

The sentiment analyzer has a split-brain architecture: an API Gateway REST API exists with rate limiting (100 req/s per API key, NOT per IP — per-IP requires WAF in Feature 1254) and a Cognito authorizer built but DISABLED, while two Lambda Function URLs (`authorization_type = NONE`) serve ALL traffic. The Cognito User Pool is fully configured (MFA, OAuth flows, Google/GitHub providers, resource scopes: `read:config`, `write:config`, `read:alerts`, `write:alerts`) but disconnected from the request path.

**Critical scope note**: The Cognito client's `allowed_oauth_scopes` is `["email", "openid", "profile"]` — it does NOT include the custom resource server scopes (`read:config`, etc.). This feature uses JWT signature/expiry validation only (no scope-based authorization at API Gateway level). Scope enforcement remains application-level if needed in the future.

The frontend (`NEXT_PUBLIC_API_URL`) currently points directly to the Dashboard Lambda Function URL. Every request — valid or not — invokes the Lambda, incurring compute cost. Invalid tokens, bots, and scrapers all trigger Lambda invocations at $0.20/million.

The API Gateway already proxies to the same Dashboard Lambda via `{proxy+}` catch-all. Enabling Cognito auth there moves JWT validation to infrastructure level: invalid tokens are rejected by API Gateway before Lambda invocation (zero compute cost for bad requests).

### Threat Model

**State-sponsored attacker assumptions:**
- Attacker has discovered both Lambda Function URLs (via DNS enumeration, CloudTrail leaks, or GitHub search)
- Attacker can generate valid-format UUID tokens (trivial)
- Attacker can perform credential stuffing against Cognito (mitigated by MFA + advanced security)
- Attacker can compromise a dependency in requirements.txt (mitigated by pinned versions + Dependabot)
- Attacker can flood endpoints to exhaust Lambda budget (mitigated by API Gateway rate limiting)

**What this feature prevents:**
- Direct Lambda Function URL access from internet (Feature 1256 completes this)
- Token validation at compute level ($0 cost for invalid tokens via API Gateway)
- Unauthenticated access to protected endpoints at infrastructure level

### Out of Scope

- SSE streaming path (requires CloudFront — Feature 1255)
- WAF rules and per-IP rate limiting (Feature 1254)
- Restricting Lambda Function URLs (Feature 1256)
- Changing application-level auth logic (keeps existing defense-in-depth)
- Migrating from REST API to HTTP API (would require module rewrite)
- Cognito scope-based authorization at API Gateway level (scopes not in client's allowed_oauth_scopes)
- Frontend 401→sign-in redirect logic (frontend already handles 401 via existing auth flow; verify during implementation)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Protected Endpoints Require Cognito JWT (Priority: P1)

All REST API endpoints under `/api/v2/configurations/*`, `/api/v2/alerts/*`, `/api/v2/notifications/*`, `/api/v2/auth/extend`, `/api/v2/auth/signout`, `/api/v2/auth/session`, `/api/v2/auth/me` require a valid Cognito JWT in the Authorization header. Requests without a token or with an expired/invalid token receive 401 from API Gateway before the Lambda is invoked.

**Why this priority**: This is the core value — move authentication from $0.20/M Lambda invocations to $0/invalid-request API Gateway rejection.

**Independent Test**: Call a protected endpoint through API Gateway without a token, verify 401 response from API Gateway (not Lambda).

**Acceptance Scenarios**:

1. **Given** a request to `GET /api/v2/configurations` through API Gateway without an Authorization header, **When** API Gateway processes the request, **Then** it returns HTTP 401 with `{"message":"Unauthorized"}` without invoking the Lambda.
2. **Given** a request with a valid Cognito JWT, **When** it hits `GET /api/v2/configurations`, **Then** the Lambda is invoked and returns the user's configurations.
3. **Given** a request with an expired Cognito JWT, **When** it hits any protected endpoint, **Then** API Gateway returns 401 without invoking the Lambda.

---

### User Story 2 — Public Endpoints Remain Unauthenticated (Priority: P1)

Auth-flow endpoints, public data endpoints, and the health check remain accessible without a Cognito JWT. This is required because: (a) anonymous session creation happens before the user has a JWT, (b) ticker search/validation are intentionally public, (c) deploy smoke tests hit /health without auth.

**Why this priority**: Breaking these endpoints blocks sign-in, search, and deploys.

**Independent Test**: Call `/api/v2/auth/anonymous` through API Gateway without any token, verify 201 success.

**Acceptance Scenarios**:

4. **Given** a request to `POST /api/v2/auth/anonymous` through API Gateway without auth, **When** API Gateway processes it, **Then** it passes through to Lambda (no Cognito check) and returns 201 with a session token.
5. **Given** a request to `GET /api/v2/tickers/search?q=AAPL` without auth, **Then** it returns ticker results (200).
6. **Given** a request to `GET /health` without auth, **Then** it returns `{"status":"healthy"}` (200).
7. **Given** a request to `POST /api/v2/auth/oauth/callback` without auth, **Then** it processes the OAuth flow normally.
8. **Given** a request to `GET /api/v2/market/status` without auth, **Then** it returns market status (200).

---

### User Story 3 — Frontend Points to API Gateway URL (Priority: P1)

The customer frontend (Amplify) uses the API Gateway URL as its API endpoint instead of the Lambda Function URL. This routes all REST traffic through the API Gateway rate limiter and Cognito authorizer.

**Why this priority**: Without this, the Cognito auth on API Gateway is useless — traffic bypasses it via Function URL.

**Independent Test**: Verify Amplify environment variable `NEXT_PUBLIC_API_URL` is set to API Gateway URL.

**Acceptance Scenarios**:

9. **Given** the Amplify deployment configuration, **When** the frontend initializes, **Then** `NEXT_PUBLIC_API_URL` resolves to the API Gateway endpoint including the stage prefix (`https://{id}.execute-api.{region}.amazonaws.com/v1`).
10. **Given** the frontend makes a request to a protected endpoint, **When** the user is authenticated, **Then** the request includes the Cognito JWT in the Authorization header and succeeds via API Gateway.
11. **Given** the deploy pipeline runs smoke tests, **When** it tests the health endpoint, **Then** it uses the API Gateway URL (not the Function URL directly).
14. **Given** a request to a protected endpoint without auth, **When** API Gateway returns 401, **Then** the response includes CORS headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Credentials: true`) so the browser exposes the 401 to JavaScript.
15. **Given** an OPTIONS preflight request to any public override resource, **When** API Gateway processes it, **Then** it returns 200 with CORS headers and no Cognito check.

---

### User Story 4 — Existing Anonymous Sessions Continue Working (Priority: P2)

Users who already have anonymous sessions (UUID Bearer tokens from `/api/v2/auth/anonymous`) can still use public and session-management endpoints. Protected endpoints return 401 from API Gateway for UUID tokens (they're not Cognito JWTs), prompting the frontend to redirect to sign-in.

**Why this priority**: Existing users should not experience broken sessions. The frontend must gracefully handle the 401 and redirect.

**Acceptance Scenarios**:

12. **Given** a user with an anonymous UUID token, **When** they access a public endpoint (`/api/v2/tickers/search`), **Then** it works normally (public endpoints don't check auth).
13. **Given** a user with an anonymous UUID token, **When** they access a protected endpoint (`/api/v2/configurations`), **Then** API Gateway returns 401 (UUID is not a valid Cognito JWT) and the frontend redirects to sign-in.

---

### Edge Cases

- What if Cognito User Pool is deleted or misconfigured? API Gateway returns 500 for all protected endpoints. Mitigation: Cognito has deletion protection in prod.
- What about the `/api/v2/auth/validate` endpoint? It validates existing sessions — it needs the existing session token to work. This endpoint should be public (it's used to check if a session is still valid before redirecting).
- What about `/api/v2/auth/magic-link` and `/api/v2/auth/magic-link/verify`? Both must be public (magic link flow starts unauthenticated). Grouped under `/api/v2/auth/magic-link/{proxy+}`.
- What about `/api/v2/auth/refresh`? This refreshes Cognito tokens — it needs either a valid JWT or the refresh token. Keep it public (Cognito refresh doesn't require a valid access token, just a valid refresh token).
- What about CORS preflight (OPTIONS)? OPTIONS requests must NOT require auth (CORS preflight never includes Authorization headers). **Each new public resource needs its own OPTIONS method** — the existing `{proxy+}` OPTIONS handler does NOT apply to explicit child resources in REST API.
- What if rate limiting (100 req/s) is too aggressive? The existing API Gateway usage plan allows configuration changes without redeployment. Note: this is per API key, not per IP. Per-IP limiting requires WAF (Feature 1254).
- What about partial deployment? If Cognito is enabled on `{proxy+}` before public overrides exist, ALL endpoints require auth (including `/health`). This breaks deploys. **Must be atomic — single terraform apply.** The module should accept a list of public routes and create them in the same resource block as the authorizer.
- What about the Amplify env var chicken-and-egg? API Gateway URL is a terraform output; Amplify needs it as an env var. Solution: use `terraform_data` to patch Amplify env vars after API Gateway is created (same pattern as Cognito callback_urls). Alternatively, the API Gateway URL is deterministic and can be constructed from the REST API ID.
- What about `Access-Control-Allow-Headers: *` with credentials? The existing Gateway Response templates must use explicit header lists, NOT wildcards (CORS spec: `*` is literal when credentials mode is enabled). Verify this in the existing module.
- What about `prevent_destroy` on the Cognito authorizer? Accidental deletion breaks all protected endpoints. Add lifecycle protection.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: API Gateway MUST enable Cognito JWT authorization on the `{proxy+}` catch-all route by setting `enable_cognito_auth = true` and providing `cognito_user_pool_arn`.
- **FR-002**: The following endpoint groups MUST remain unauthenticated (no Cognito check). Implementation uses explicit API Gateway resources with `authorization = "NONE"` and `ANY` method that override the `{proxy+}` catch-all. Each public resource group uses a `{proxy+}` child resource under the group prefix to catch all sub-paths.

  **Implementation strategy**: REST API resources are hierarchical. Explicit resources take priority over the parent `{proxy+}`. For groups like `/api/v2/auth/anonymous`, the intermediate resources (`/api`, `/api/v2`, `/api/v2/auth`) must be created but do NOT need their own methods — they serve as parent nodes only. The leaf resource or its `{proxy+}` child handles requests.

  **Public resource groups** (each gets `ANY` method with `authorization = "NONE"` + `OPTIONS` for CORS):

  Auth flow endpoints (no Cognito — user doesn't have a JWT yet):
  - `/api/v2/auth/anonymous` — session creation
  - `/api/v2/auth/magic-link/{proxy+}` — magic link request + verify
  - `/api/v2/auth/oauth/{proxy+}` — OAuth URLs + callback
  - `/api/v2/auth/refresh` — token refresh
  - `/api/v2/auth/validate` — session validation

  Public data endpoints (intentionally unauthenticated):
  - `/api/v2/tickers/{proxy+}` — ticker search/validation
  - `/api/v2/market/{proxy+}` — market status
  - `/api/v2/timeseries/{proxy+}` — public sentiment data

  Infrastructure endpoints:
  - `/health` — deploy smoke test + monitoring
  - `/api/v2/runtime` — frontend SSE URL discovery

  **Method handling**: All public resources use `ANY` method (not specific HTTP methods) to avoid method-mismatch fallthrough to the Cognito-protected `{proxy+}`. This matches the existing catch-all pattern and avoids subtle auth bypasses.

  **Shared intermediate resources**: `/api`, `/api/v2`, `/api/v2/auth` are created once and shared by all child resources. They do not have methods attached.
- **FR-003**: The Amplify frontend deployment MUST set `NEXT_PUBLIC_API_URL` to the API Gateway endpoint URL.
- **FR-004**: Deploy pipeline smoke tests MUST use the API Gateway URL for health checks (in addition to or instead of Function URL checks).
- **FR-005**: OPTIONS preflight requests MUST pass through without Cognito authorization on all routes. Each new explicit public resource MUST have its own `OPTIONS` method with `authorization = "NONE"` and MOCK integration returning CORS headers. The existing `{proxy+}` OPTIONS handler is NOT inherited by child resources.
- **FR-006**: Application-level auth (session validation, `_require_user_id()`) MUST remain as defense-in-depth. Cognito auth at API Gateway is an additional layer, not a replacement.
- **FR-007**: All public resource overrides and the Cognito authorizer enablement MUST be deployed atomically in a single `terraform apply`. Partial deployment (Cognito enabled on `{proxy+}` without public overrides) would break `/health`, `/api/v2/auth/anonymous`, and deploy smoke tests.
- **FR-008**: The API Gateway 401 (`UNAUTHORIZED`) and 403 (`MISSING_AUTHENTICATION_TOKEN`) Gateway Response templates MUST include CORS headers (`Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Credentials`). Without these, the browser's CORS policy silently drops 401 responses and the frontend cannot detect or handle auth failures. This is critical because `client.ts` uses `credentials: 'include'`.
- **FR-009**: The Cognito authorizer MUST validate JWT signature and expiry only (`authorization_scopes` not set). The Cognito client's `allowed_oauth_scopes` does not include custom resource server scopes, so scope-based authorization would reject all tokens.
- **FR-010**: The Amplify `NEXT_PUBLIC_API_URL` MUST include the API Gateway stage prefix (e.g., `https://{id}.execute-api.{region}.amazonaws.com/v1`). The stage name is `v1` per the module configuration. Frontend routes like `/api/v2/configurations` become `https://...amazonaws.com/v1/api/v2/configurations` in the full URL.

### Key Entities

- **Cognito JWT**: Access token issued by Cognito after authentication. Contains `sub` (user ID), `iss` (Cognito URL), `aud` (client ID), `exp` (expiry). Validated by API Gateway authorizer.
- **Anonymous Session Token**: UUID-format Bearer token created by `/api/v2/auth/anonymous`. NOT a Cognito JWT. Will be rejected by Cognito authorizer on protected endpoints.
- **Public Route**: An API Gateway resource with `authorization = "NONE"` that overrides the `{proxy+}` Cognito-protected catch-all.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Requests to protected endpoints without a valid Cognito JWT return 401 from API Gateway (not from Lambda — verifiable by checking Lambda invocation count doesn't increase).
- **SC-002**: Requests to public endpoints without auth succeed (200/201) through API Gateway.
- **SC-003**: Frontend Amplify deployment uses API Gateway URL as `NEXT_PUBLIC_API_URL`.
- **SC-004**: Deploy smoke tests pass using API Gateway URL.
- **SC-005**: Existing Playwright E2E tests pass through API Gateway path (no functional regression).
- **SC-006**: Invalid/expired tokens on protected endpoints do NOT invoke Lambda (zero compute cost for bad requests).

## Assumptions

- The Cognito User Pool (`module.cognito`) is correctly deployed and its ARN is available as `module.cognito.user_pool_arn` (verified: `outputs.tf` exports it).
- The existing API Gateway module's `{proxy+}` catch-all takes lower priority than explicitly defined resources (standard API Gateway REST API behavior — verified in AWS documentation).
- The frontend sends Bearer tokens in the Authorization header for all requests (`client.ts` lines 135-139 — verified). For authenticated users, this is a Cognito JWT. For anonymous users, this is a UUID. API Gateway Cognito authorizer validates JWT format.
- Amplify environment variables can be set via `terraform_data` post-deploy patch (same pattern as Cognito callback_urls — `lifecycle { ignore_changes }`).
- The Cognito authorizer caches validated tokens for 300 seconds (default), so Lambda is only invoked once per token lifetime per path.
- The API Gateway stage name is `v1` (verified: `stage_name = "v1"` in main.tf line ~810). The full URL pattern is `https://{rest_api_id}.execute-api.{region}.amazonaws.com/v1/{path}`.
- Intermediate API Gateway resources (`/api`, `/api/v2`, `/api/v2/auth`) can exist without methods and serve only as parent nodes in the resource tree.

## Adversarial Review Log

**Review date**: 2026-03-24
**Issues found**: 6 BLOCKING, 5 HIGH, 2 MEDIUM — all resolved in this revision.

| ID | Severity | Issue | Resolution |
|----|----------|-------|------------|
| B1 | BLOCKING | Branch name stale (`H-` prefix) | Updated to `1253-api-gateway-cognito-auth` |
| B2 | BLOCKING | Resource hierarchy for nested paths not addressed | Added implementation strategy in FR-002 (shared intermediates) |
| B3 | BLOCKING | Wildcard paths impossible as written | Changed to `{proxy+}` child resources under group prefixes |
| B4 | BLOCKING | Deployment atomicity not specified | Added FR-007 (single terraform apply) |
| B5 | BLOCKING | Cognito scopes mismatch would reject all tokens | Added FR-009 (signature/expiry only, no scope check) |
| B6 | BLOCKING | 401 responses missing CORS headers | Added FR-008 (CORS on Gateway Responses) |
| H1 | HIGH | Frontend 401 handling unspecified | Added to Out of Scope with verification note |
| H2 | HIGH | Stage prefix `/v1` not explicit | Added FR-010 and clarified in scenarios |
| H3 | HIGH | Amplify env var chicken-and-egg | Added edge case with terraform_data solution |
| H4 | HIGH | OPTIONS needed on each new public resource | Updated FR-005 and edge case |
| H5 | HIGH | Method-specific public routes could leak via fallthrough | Changed to `ANY` method on all public resources |
| M1 | MEDIUM | Rate limit is per API key, not per IP | Clarified in Context and edge cases |
| M2 | MEDIUM | No prevent_destroy on authorizer | Added to edge cases |
