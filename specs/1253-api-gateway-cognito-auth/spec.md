# Feature Specification: Route Frontend Through API Gateway + Enable Cognito Auth

**Feature Branch**: `H-api-gateway-cognito-auth`
**Created**: 2026-03-24
**Status**: Draft
**Input**: "Resolve split-brain architecture: route all frontend REST traffic through API Gateway with Cognito JWT auth, keep public endpoints unauthenticated"

## Context

The sentiment analyzer has a split-brain architecture: an API Gateway REST API exists with rate limiting (100 req/s) and a Cognito authorizer built but DISABLED, while two Lambda Function URLs (`authorization_type = NONE`) serve ALL traffic. The Cognito User Pool is fully configured (MFA, OAuth flows, Google/GitHub providers, resource scopes: `read:config`, `write:config`, `read:alerts`, `write:alerts`) but disconnected from the request path.

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
- WAF rules (Feature 1254)
- Restricting Lambda Function URLs (Feature 1256)
- Changing application-level auth logic (keeps existing defense-in-depth)
- Migrating from REST API to HTTP API (would require module rewrite)

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

9. **Given** the Amplify deployment configuration, **When** the frontend initializes, **Then** `NEXT_PUBLIC_API_URL` resolves to the API Gateway endpoint (`https://{id}.execute-api.{region}.amazonaws.com/v1`).
10. **Given** the frontend makes a request to a protected endpoint, **When** the user is authenticated, **Then** the request includes the Cognito JWT in the Authorization header and succeeds via API Gateway.
11. **Given** the deploy pipeline runs smoke tests, **When** it tests the health endpoint, **Then** it uses the API Gateway URL (not the Function URL directly).

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
- What about `/api/v2/auth/magic-link` and `/api/v2/auth/magic-link/verify`? Both must be public (magic link flow starts unauthenticated).
- What about `/api/v2/auth/refresh`? This refreshes Cognito tokens — it needs either a valid JWT or the refresh token. Keep it public (Cognito refresh doesn't require a valid access token, just a valid refresh token).
- What about CORS preflight (OPTIONS)? OPTIONS requests must NOT require auth (CORS preflight never includes Authorization headers). The existing module handles this (lines 123-231).
- What if rate limiting (100 req/s) is too aggressive? The existing API Gateway usage plan allows configuration changes without redeployment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: API Gateway MUST enable Cognito JWT authorization on the `{proxy+}` catch-all route by setting `enable_cognito_auth = true` and providing `cognito_user_pool_arn`.
- **FR-002**: The following endpoint prefixes MUST remain unauthenticated (no Cognito check) by creating explicit API Gateway resources that override the `{proxy+}` catch-all:
  - `POST /api/v2/auth/anonymous` — session creation
  - `POST /api/v2/auth/magic-link` — magic link request
  - `GET /api/v2/auth/magic-link/verify` — magic link verification
  - `GET /api/v2/auth/oauth/urls` — OAuth provider URLs
  - `POST /api/v2/auth/oauth/callback` — OAuth callback
  - `POST /api/v2/auth/refresh` — token refresh
  - `GET /api/v2/auth/validate` — session validation
  - `GET /api/v2/tickers/*` — ticker search/validation
  - `GET /api/v2/market/*` — market status
  - `GET /api/v2/timeseries/*` — public sentiment data
  - `GET /health` — deploy smoke test + monitoring
  - `GET /api/v2/runtime` — frontend SSE URL discovery
- **FR-003**: The Amplify frontend deployment MUST set `NEXT_PUBLIC_API_URL` to the API Gateway endpoint URL.
- **FR-004**: Deploy pipeline smoke tests MUST use the API Gateway URL for health checks (in addition to or instead of Function URL checks).
- **FR-005**: OPTIONS preflight requests MUST pass through without Cognito authorization on all routes (existing behavior, verify preservation).
- **FR-006**: Application-level auth (session validation, `_require_user_id()`) MUST remain as defense-in-depth. Cognito auth at API Gateway is an additional layer, not a replacement.

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

- The Cognito User Pool (`module.cognito`) is correctly deployed and its ARN is available as a Terraform output.
- The existing API Gateway module's `{proxy+}` catch-all takes lower priority than explicitly defined resources (standard API Gateway REST API behavior).
- The frontend already sends Cognito JWTs in the Authorization header for authenticated users (verify in `frontend/src/lib/api/client.ts`).
- Amplify environment variables can be set via Terraform or deployment scripts.
- The Cognito authorizer caches validated tokens for 300 seconds (default), so Lambda is only invoked once per token lifetime per path.
