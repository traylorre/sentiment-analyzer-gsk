# Data Model: Feature 1253 — API Gateway Cognito Auth

**Date**: 2026-03-24

## Terraform Resource Model

This feature is infrastructure-only. The "data model" is the Terraform resource graph.

### New Resources

#### Cognito Authorizer (1 resource)

| Resource | Type | Key Attributes |
|----------|------|---------------|
| `aws_api_gateway_authorizer.cognito[0]` | COGNITO_USER_POOLS | `provider_arns = [var.cognito_user_pool_arn]`, `identity_source = "method.request.header.Authorization"` |

*Already exists in module — activated by `enable_cognito_auth = true`.*

#### Gateway Responses (2 resources, updated)

| Resource | Response Type | CORS Headers Required |
|----------|--------------|----------------------|
| `aws_api_gateway_gateway_response.unauthorized[0]` | UNAUTHORIZED | Origin, Headers, Credentials, Methods |
| `aws_api_gateway_gateway_response.missing_auth_token[0]` | MISSING_AUTHENTICATION_TOKEN | Origin, Headers, Credentials, Methods |

#### Intermediate Resources (no methods)

| Resource Key | Path | Purpose |
|-------------|------|---------|
| `api` | `/api` | Parent node |
| `api_v2` | `/api/v2` | Parent node |
| `api_v2_auth` | `/api/v2/auth` | Parent node |
| `api_v2_auth_magic-link` | `/api/v2/auth/magic-link` | Parent for {proxy+} |
| `api_v2_auth_oauth` | `/api/v2/auth/oauth` | Parent for {proxy+} |
| `api_v2_tickers` | `/api/v2/tickers` | Parent for {proxy+} |
| `api_v2_market` | `/api/v2/market` | Parent for {proxy+} |
| `api_v2_timeseries` | `/api/v2/timeseries` | Parent for {proxy+} |

#### Leaf Resources (with ANY + OPTIONS methods)

| Route Group | Leaf Resource | Has {proxy+} Child |
|-------------|--------------|-------------------|
| Auth: anonymous | `/api/v2/auth/anonymous` | No |
| Auth: magic-link | `/api/v2/auth/magic-link/{proxy+}` | Yes |
| Auth: oauth | `/api/v2/auth/oauth/{proxy+}` | Yes |
| Auth: refresh | `/api/v2/auth/refresh` | No |
| Auth: validate | `/api/v2/auth/validate` | No |
| Data: tickers | `/api/v2/tickers/{proxy+}` | Yes |
| Data: market | `/api/v2/market/{proxy+}` | Yes |
| Data: timeseries | `/api/v2/timeseries/{proxy+}` | Yes |
| Infra: health | `/health` | No |
| Infra: runtime | `/api/v2/runtime` | No |

#### Per-Leaf Resource Set (×10)

Each leaf resource creates:
1. `aws_api_gateway_method` (ANY, authorization = "NONE")
2. `aws_api_gateway_integration` (ANY → Lambda AWS_PROXY)
3. `aws_api_gateway_method` (OPTIONS, authorization = "NONE")
4. `aws_api_gateway_integration` (OPTIONS → MOCK)
5. `aws_api_gateway_method_response` (OPTIONS → 200)
6. `aws_api_gateway_integration_response` (OPTIONS → CORS headers)

### State Transitions

No application-level state transitions. The only state change is Terraform:
- `enable_cognito_auth`: `false` → `true`
- `{proxy+}` catch-all authorization: `"NONE"` → `"COGNITO_USER_POOLS"`
- Amplify `NEXT_PUBLIC_API_URL`: Lambda Function URL → API Gateway URL

### Validation Rules

| Rule | Enforcement |
|------|-------------|
| Public routes must have NONE authorization | Terraform variable structure enforces this |
| Protected routes must have COGNITO_USER_POOLS | Conditional on `enable_cognito_auth` flag |
| CORS headers on 401/403 | Gateway Response templates include explicit header list |
| Stage prefix in API URL | Amplify env var includes `/v1` suffix |
| Atomic deployment | All resources in same module, single apply |
