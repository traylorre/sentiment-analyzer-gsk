# Research: Feature 1253 — API Gateway Cognito Auth

**Date**: 2026-03-24 | **Status**: Complete

## R1: API Gateway Resource Tree Priority

**Decision**: Explicit resources take priority over `{proxy+}`.

**Rationale**: AWS API Gateway REST API routes by most-specific-match. `/api/v2/auth/anonymous` matches before `/{proxy+}`. Verified in AWS docs: "API Gateway chooses the route with the most specific match."

**Key findings**:
- `{proxy+}` children under non-proxy parents (e.g., `/api/v2/tickers/{proxy+}`) are valid and coexist with root `/{proxy+}`
- Intermediates without methods return 403 `Missing Authentication Token` — they do NOT fall back to `{proxy+}` (critical for FR-012)
- `ANY` does NOT cover `OPTIONS` for CORS — separate method required
- AWS ref: "A proxy resource can only be a child of a non-proxy resource"

## R2: CORS on Gateway Responses

**Decision**: Add CORS headers to UNAUTHORIZED, MISSING_AUTHENTICATION_TOKEN, and ACCESS_DENIED responses.

**Rationale**: Existing gateway responses (api_gateway/main.tf:61-99) only include `WWW-Authenticate`. Missing: `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers`, `Access-Control-Allow-Credentials`. With `credentials: 'include'`, browser silently drops 401 without CORS headers. Must use explicit header list, NOT `*` (CORS spec: wildcard is literal when credentials enabled).

## R3: Amplify URL Switch

**Decision**: Change `NEXT_PUBLIC_API_URL` from `var.dashboard_lambda_url` to `var.api_gateway_url`.

**Rationale**: Amplify module (modules/amplify/main.tf:42) currently sets `NEXT_PUBLIC_API_URL = var.dashboard_lambda_url` with comment "Feature 1114: Use Lambda Function URL (has CORS) instead of API Gateway (no CORS on proxy)." Feature 1253 adds CORS to API Gateway, removing the original blocker. Pass `module.api_gateway.api_endpoint` from main.tf. No chicken-and-egg — `depends_on` ensures ordering.

## R4: Smoke Test URLs

**Decision**: Add API Gateway health check alongside existing Lambda direct-invoke.

**Rationale**: deploy.yml (lines 1073-1175) uses `terraform output -raw dashboard_function_url` + Lambda direct invoke. After 1253, add parallel check via `terraform output -raw dashboard_api_url`. Keep Lambda test as baseline until Feature 1256 restricts Function URLs.

## R5: Cognito Scope Strategy

**Decision**: JWT signature + expiry only. No scope enforcement.

**Rationale**: Client's `allowed_oauth_scopes = ["email", "openid", "profile"]` excludes custom scopes. Setting `authorization_scopes` would reject ALL tokens. Scope enforcement deferred.

## R6: Frontend 401 Handling

**Decision**: No frontend changes required.

**Rationale**: `client.ts` wraps non-200 in `ApiClientError` (lines 85-110). `use-auth.ts` handles session expiry with auto-refresh (lines 72-129). Existing chain surfaces 401 correctly, provided CORS headers present (FR-008).

## R7: Intermediates as Endpoints (FR-012)

**Decision**: Add methods to intermediates that are also endpoint paths.

**Rationale**: Creating `/api/v2/notifications` as intermediate for `/unsubscribe` breaks `GET /api/v2/notifications`. API Gateway returns 403 when resource exists without method — does NOT fall back to `{proxy+}`. Two affected paths:
- `/api/v2/notifications`: needs `ANY` + `COGNITO_USER_POOLS` (protected endpoint)
- `/api/v2/auth/magic-link`: needs `ANY` + `NONE` (public endpoint)

## R8: Resource Count

| Resource Type | Count |
|---------------|-------|
| Intermediate resources (no methods) | 6 (`/api`, `/api/v2`, `/api/v2/auth`, `/api/v2/auth/oauth`, `/api/v2/tickers`, `/api/v2/market`, `/api/v2/timeseries`) |
| Intermediate-as-endpoint resources (FR-012) | 2 (`/notifications`, `/auth/magic-link`) — each gets ANY+OPTIONS+integrations |
| Leaf/proxy public resources | 10 |
| Per-resource set (ANY method + integration + OPTIONS + MOCK + response) | ×6 each |
| Gateway Responses (CORS update) | 3 (UNAUTHORIZED, MISSING_AUTH_TOKEN, ACCESS_DENIED) |
| **Estimated total** | **~85** |
