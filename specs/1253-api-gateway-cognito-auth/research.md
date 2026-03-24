# Research: Feature 1253 — API Gateway Cognito Auth

**Date**: 2026-03-24 | **Status**: Complete

## R1: API Gateway REST API Resource Tree Priority

**Decision**: Explicit resources take priority over `{proxy+}` catch-all.

**Rationale**: In AWS API Gateway REST APIs, the routing engine resolves the most specific resource path first. A request to `/api/v2/auth/anonymous` matches an explicit `/api/v2/auth/anonymous` resource before falling through to `/{proxy+}`. This is standard REST API behavior documented in the AWS API Gateway developer guide.

**Key findings** (confirmed by AWS docs research):
- Explicit `/api/v2/tickers/{proxy+}` works alongside top-level `/{proxy+}` — the more specific path wins. Note: `{proxy+}` cannot have child resources, but `/api/v2/tickers/{proxy+}` is a child of `/api/v2/tickers` (non-proxy), which is valid
- Intermediate resources (`/api`, `/api/v2`, `/api/v2/auth`) can exist without methods — they serve as parent nodes only. Requests to method-less intermediates return 403 Missing Authentication Token (acceptable)
- `ANY` method routes OPTIONS at the routing level but a separate `OPTIONS` method with MOCK integration is recommended for proper CORS preflight handling (faster, cheaper, no Lambda invocation)
- Each public resource override needs: (1) `ANY` method with `authorization = "NONE"`, (2) `OPTIONS` method with MOCK integration for CORS, (3) Lambda proxy integration on the `ANY` method
- AWS reference: "A proxy resource can only be a child of a non-proxy resource" — this means `{proxy+}` can't have children, not that multiple `{proxy+}` resources at different tree levels conflict

**Alternatives considered**:
- HTTP API (v2) instead of REST API: Would simplify routing (uses `$default` instead of `{proxy+}`) but requires rewriting the entire API Gateway module — out of scope per spec
- Individual HTTP method resources (e.g., only `POST` for `/auth/anonymous`): Rejected because unmatched methods fall through to `{proxy+}` and would require Cognito auth, creating subtle auth bypass failures

## R2: CORS on Gateway Responses (401/403)

**Decision**: Add CORS headers to all Gateway Response templates for 401 and 403 status codes.

**Rationale**: The existing gateway responses (UNAUTHORIZED, MISSING_AUTHENTICATION_TOKEN) at `api_gateway/main.tf:61-99` only include `WWW-Authenticate` header. They are MISSING:
- `Access-Control-Allow-Origin`
- `Access-Control-Allow-Headers`
- `Access-Control-Allow-Credentials`

The frontend uses `credentials: 'include'` on fetch requests. Without CORS headers on 401 responses, the browser silently drops the response body per CORS spec, making it impossible for JavaScript to detect and handle auth failures.

**Important**: Must use explicit header list for `Access-Control-Allow-Headers`, NOT wildcard `*` (per CORS spec, wildcard is treated as literal string when credentials mode is enabled — documented in CLAUDE.md lessons learned).

**Alternatives considered**:
- Relying on DEFAULT_4XX Gateway Response: Works but is less explicit and harder to debug. Explicit per-type responses preferred.
- Adding a 403 ACCESS_DENIED response: Added for completeness — Cognito can return 403 for insufficient scope.

## R3: Amplify Environment Variable Wiring

**Decision**: Change `var.dashboard_lambda_url` to API Gateway URL in the Amplify module.

**Rationale**: The Amplify module at `modules/amplify/main.tf:23-99` sets:
```
NEXT_PUBLIC_API_URL = var.dashboard_lambda_url
```
With a comment: "Feature 1114: Use Lambda Function URL (has CORS) instead of API Gateway (no CORS on proxy)."

This was the original choice because API Gateway lacked proper CORS. Feature 1253 fixes CORS on API Gateway, making it viable as the frontend's API endpoint.

**Implementation**:
1. Add `api_gateway_url` variable to the Amplify module
2. Change `NEXT_PUBLIC_API_URL` to use `var.api_gateway_url` when provided, fallback to `var.dashboard_lambda_url`
3. Pass `module.api_gateway.api_endpoint` from main.tf to the Amplify module
4. No chicken-and-egg: API Gateway URL is deterministic from REST API ID, and Amplify deploys after API Gateway via `depends_on`

**Alternatives considered**:
- `terraform_data` post-deploy patch: Unnecessary — the `depends_on` chain ensures ordering
- Constructing URL from REST API ID: More fragile than using the module output

## R4: Deploy Pipeline Smoke Tests

**Decision**: Update smoke test URLs to use API Gateway endpoint.

**Rationale**: The deploy.yml pipeline uses Lambda Function URLs for smoke tests (health checks). After Feature 1253, the primary API path is API Gateway. Smoke tests should verify:
1. API Gateway health endpoint works (`GET /v1/health`)
2. Protected endpoint returns 401 without auth (proves Cognito is active)
3. Public endpoint works without auth (proves overrides are in place)

The Lambda Function URL smoke test should remain as a secondary check until Feature 1256 restricts direct Function URL access.

## R5: Cognito Authorizer Scope Strategy

**Decision**: JWT signature + expiry validation only. No scope enforcement at API Gateway level.

**Rationale**: The Cognito client's `allowed_oauth_scopes = ["email", "openid", "profile"]` does NOT include custom resource server scopes (`read:config`, `write:config`, `read:alerts`, `write:alerts`). Setting `authorization_scopes` on the API Gateway authorizer would reject ALL tokens because they don't contain the custom scopes.

Scope enforcement can be added in the future by:
1. Adding custom scopes to the Cognito client's `allowed_oauth_scopes`
2. Setting `authorization_scopes` on specific API Gateway methods
3. This is a separate feature and out of scope for 1253.

## R6: Terraform Resource Count

**Estimated new Terraform resources** (for planning):

| Resource Type | Count | Purpose |
|---------------|-------|---------|
| `aws_api_gateway_resource` (intermediate) | 5 | /api, /api/v2, /api/v2/auth, /api/v2/auth/magic-link, /api/v2/auth/oauth |
| `aws_api_gateway_resource` (leaf) | 10 | /anonymous, /refresh, /validate, /runtime, /health + {proxy+} children for magic-link, oauth, tickers, market, timeseries |
| `aws_api_gateway_method` (ANY) | 10 | One per leaf/proxy resource |
| `aws_api_gateway_method` (OPTIONS) | 10 | CORS preflight per resource |
| `aws_api_gateway_integration` (ANY→Lambda) | 10 | Lambda proxy integration |
| `aws_api_gateway_integration` (OPTIONS→MOCK) | 10 | CORS mock integration |
| `aws_api_gateway_method_response` | 10 | OPTIONS 200 responses |
| `aws_api_gateway_integration_response` | 10 | OPTIONS CORS headers |
| `aws_api_gateway_gateway_response` (updates) | 2 | CORS on 401 UNAUTHORIZED + MISSING_AUTH_TOKEN |
| **Total new resources** | **~77** | |

This is a significant Terraform change. All resources must be created in a single `terraform apply` to avoid partial deployment (FR-007).

## R7: Smoke Test URL Configuration (from codebase exploration)

**Decision**: Add API Gateway health check alongside existing Lambda direct-invoke smoke test.

**Rationale**: The deploy.yml smoke test (lines 1073-1175) uses:
- `terraform output -raw dashboard_function_url` for the Lambda Function URL
- Direct Lambda invoke via `aws lambda invoke` on the "live" alias (bypasses CloudFront propagation delay)
- Curl to `${DASHBOARD_URL}/health` for JSON validation

After Feature 1253, add a parallel check via API Gateway URL (`terraform output -raw dashboard_api_url`). Keep the Lambda direct-invoke test as a baseline.

## R8: Frontend 401 Handling (from codebase exploration)

**Decision**: No frontend changes required for Feature 1253.

**Rationale**: `client.ts` (lines 85-177) wraps all non-200 responses in `ApiClientError` and throws. The `use-auth.ts` hook (lines 72-129) handles session expiry with automatic token refresh 5 minutes before expiry. On complete auth failure, it signs out and redirects. The existing error handling chain will correctly surface API Gateway 401 responses, provided CORS headers are present (FR-008).

## R9: Amplify Module Wiring (from codebase exploration)

**Decision**: Change `NEXT_PUBLIC_API_URL` from `var.dashboard_lambda_url` to `var.api_gateway_url` in the Amplify module.

**Current state** (modules/amplify/main.tf:42):
```
NEXT_PUBLIC_API_URL = var.dashboard_lambda_url
```
Comment: "Feature 1114: Use Lambda Function URL (has CORS) instead of API Gateway (no CORS on proxy)"

**After Feature 1253**: API Gateway will have proper CORS on all responses including errors, making it viable.

**Wiring**:
1. `main.tf`: Pass `api_gateway_url = module.api_gateway.api_endpoint` to `module.amplify_frontend`
2. `modules/amplify/variables.tf`: Add `variable "api_gateway_url" { type = string }`
3. `modules/amplify/main.tf`: Change `NEXT_PUBLIC_API_URL = var.api_gateway_url`
4. `depends_on`: Add `module.api_gateway` to the Amplify module's dependency chain

The `terraform_data.cognito_callback_patch` (main.tf:1128-1150) does NOT need changes — it patches Cognito callback URLs based on the Amplify production URL, not the API URL.
