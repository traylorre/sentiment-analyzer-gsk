# Data Model: Feature 1253 — API Gateway Cognito Auth

**Date**: 2026-03-24

## Terraform Resource Model

Infrastructure-only feature. The "data model" is the Terraform resource graph.

### Resource Categories

#### 1. Cognito Authorizer (existing, activated)

Activated by `enable_cognito_auth = true`. Already exists in module code.

#### 2. Gateway Responses (3 resources, CORS headers added)

| Response Type | Status | CORS Headers |
|---------------|--------|-------------|
| UNAUTHORIZED | 401 | Origin, Headers, Credentials, Methods |
| MISSING_AUTHENTICATION_TOKEN | 401 | Origin, Headers, Credentials, Methods |
| ACCESS_DENIED | 403 | Origin, Headers, Credentials, Methods |

#### 3. Pure Intermediates (no methods — parent nodes only)

`/api`, `/api/v2`, `/api/v2/auth`, `/api/v2/auth/oauth`, `/api/v2/tickers`, `/api/v2/market`, `/api/v2/timeseries`

#### 4. FR-012 Intermediates (have methods — are also endpoints)

| Resource | Auth | Method | Reason |
|----------|------|--------|--------|
| `/api/v2/notifications` | COGNITO_USER_POOLS | ANY + OPTIONS | Lists user notifications |
| `/api/v2/auth/magic-link` | NONE | ANY + OPTIONS | Sends magic link email |

Each gets: method + integration + OPTIONS + MOCK + method_response + integration_response = 6 resources.

#### 5. Public Leaf/Proxy Resources (11 groups)

| Group | Resource Path | Has {proxy+} |
|-------|--------------|-------------|
| anonymous | `/api/v2/auth/anonymous` | No |
| magic-link child | `/api/v2/auth/magic-link/{proxy+}` | Yes |
| oauth | `/api/v2/auth/oauth/{proxy+}` | Yes |
| refresh | `/api/v2/auth/refresh` | No |
| validate | `/api/v2/auth/validate` | No |
| tickers | `/api/v2/tickers/{proxy+}` | Yes |
| market | `/api/v2/market/{proxy+}` | Yes |
| timeseries | `/api/v2/timeseries/{proxy+}` | Yes |
| unsubscribe | `/api/v2/notifications/unsubscribe` | No |
| health | `/health` | No |
| runtime | `/api/v2/runtime` | No |

Each gets: resource + ANY method + integration + OPTIONS + MOCK + method_response + integration_response = 7 resources (6 for groups that reuse parent's resource).

### Validation Rules

| Rule | Enforcement |
|------|-------------|
| Public routes: authorization = "NONE" | `public_routes` variable structure |
| Protected routes: authorization = "COGNITO_USER_POOLS" | Conditional on `enable_cognito_auth` |
| CORS headers use explicit list, not wildcard | Hardcoded in Gateway Response templates |
| Atomic deployment | All resources in same module, single apply |
| FR-012 intermediates have methods | `is_endpoint = true` in route config |
