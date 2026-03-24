# Implementation Plan: Route Frontend Through API Gateway + Enable Cognito Auth

**Branch**: `1253-api-gateway-cognito-auth` | **Date**: 2026-03-24 | **Spec**: `specs/1253-api-gateway-cognito-auth/spec.md`
**Input**: Feature specification from `/specs/1253-api-gateway-cognito-auth/spec.md`

## Summary

Enable Cognito JWT authorization on the API Gateway `{proxy+}` catch-all route while creating explicit unauthenticated override resources for public endpoints. Switch the Amplify frontend from Lambda Function URL to API Gateway URL. Add CORS headers to 401/403 Gateway Responses so the browser can surface auth failures to JavaScript. All changes deploy atomically in one `terraform apply`.

## Technical Context

**Language/Version**: HCL (Terraform 1.5+, AWS Provider ~> 5.0), TypeScript (Next.js frontend)
**Primary Dependencies**: AWS API Gateway (REST API), AWS Cognito, AWS Amplify, AWS Lambda
**Storage**: N/A (infrastructure-only changes)
**Testing**: Terraform plan validation, pytest (unit + E2E), Playwright (frontend E2E)
**Target Platform**: AWS (us-east-1)
**Project Type**: Web application (Terraform IaC + Next.js frontend)
**Performance Goals**: Zero compute cost for invalid tokens; <50ms added latency for Cognito JWT validation (authorizer caches 300s)
**Constraints**: Must be atomic deployment (no partial state where public endpoints require auth); must not break existing Playwright E2E tests
**Scale/Scope**: ~78 new Terraform resources (10 public route groups × 6 resources each + 8 intermediate resources + 3 gateway responses + authorizer enablement)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Constitution Section | Status | Notes |
|------|---------------------|--------|-------|
| Auth on management endpoints | §3 Security & Access Control | PASS | Cognito JWT auth added at infrastructure level for protected endpoints |
| TLS in transit | §3 Security & Access Control | PASS | API Gateway enforces HTTPS by default |
| Secrets not in source control | §3 Security & Access Control | PASS | Cognito ARN referenced via Terraform module output, not hardcoded |
| IaC deployment | §5 Deployment | PASS | All changes via Terraform modules |
| Health check endpoints | §5 Deployment | PASS | /health kept as public endpoint (FR-002) |
| Unit tests for new code | §7 Testing (Implementation Accompaniment) | PASS | Unit tests for new Terraform resources via `terraform plan`; E2E tests for auth behavior |
| GPG-signed commits | §8 Git Workflow | PASS | All commits signed |
| No pipeline bypass | §8 Git Workflow | PASS | Standard PR flow |
| SAST before push | §10 Local SAST | N/A | Infrastructure-only change, no Python code modified |

**Pre-design gate**: PASS — no violations.

## Project Structure

### Documentation (this feature)

```text
specs/1253-api-gateway-cognito-auth/
├── spec.md              # Feature specification (post-adversarial-v1)
├── plan.md              # This file
├── research.md          # Phase 0: API GW resource tree, CORS, Amplify wiring
├── data-model.md        # Phase 1: Terraform resource model
├── quickstart.md        # Phase 1: Implementation quickstart
├── contracts/           # Phase 1: API Gateway route contracts
└── tasks.md             # Phase 2: Implementation tasks (/speckit.tasks)
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── modules/api_gateway/
│   ├── main.tf              # MODIFY: Add public route overrides, CORS on 401/403
│   ├── variables.tf         # MODIFY: Add public_routes variable
│   └── outputs.tf           # No changes needed
├── modules/amplify/
│   ├── main.tf              # MODIFY: Switch NEXT_PUBLIC_API_URL to API Gateway
│   └── variables.tf         # MODIFY: Add api_gateway_url variable
├── modules/cognito/         # No changes needed (already exports user_pool_arn)
└── main.tf                  # MODIFY: Pass enable_cognito_auth + cognito_user_pool_arn + api_gateway_url

.github/workflows/
└── deploy.yml               # MODIFY: Add API Gateway smoke test URL

tests/
├── unit/
│   └── test_api_gateway_cognito.py  # NEW: Unit tests for auth behavior
└── e2e/
    └── test_cognito_auth.py         # NEW: E2E tests verifying 401/200 through API GW
```

**Structure Decision**: Infrastructure-only feature. Primary changes in `modules/api_gateway/main.tf` (Terraform). Secondary changes in `modules/amplify/main.tf` (env var switch) and `main.tf` (module wiring). No Python source code changes.

## Architecture

### Request Flow (After Feature 1253)

```
Browser → API Gateway (REST API, stage: v1)
  ├── Public endpoints (authorization = "NONE")
  │   ├── /health → Lambda (no Cognito check)
  │   ├── /api/v2/auth/anonymous → Lambda (session creation)
  │   ├── /api/v2/auth/magic-link/{proxy+} → Lambda
  │   ├── /api/v2/auth/oauth/{proxy+} → Lambda
  │   ├── /api/v2/auth/refresh → Lambda
  │   ├── /api/v2/auth/validate → Lambda
  │   ├── /api/v2/tickers/{proxy+} → Lambda
  │   ├── /api/v2/market/{proxy+} → Lambda
  │   ├── /api/v2/timeseries/{proxy+} → Lambda
  │   └── /api/v2/runtime → Lambda
  └── Protected endpoints (authorization = "COGNITO_USER_POOLS")
      └── /{proxy+} catch-all → Cognito JWT validation → Lambda
          ├── Valid JWT → Lambda invoked (200)
          ├── Invalid/expired JWT → 401 (with CORS headers, no Lambda invocation)
          └── Missing token → 401 (with CORS headers, no Lambda invocation)
```

### API Gateway Resource Tree

```
/ (root)
├── health                          [ANY: NONE, OPTIONS: MOCK]
└── api/                            [no method — intermediate]
    └── v2/                         [no method — intermediate]
        ├── auth/                   [no method — intermediate]
        │   ├── anonymous           [ANY: NONE, OPTIONS: MOCK]
        │   ├── magic-link/
        │   │   └── {proxy+}       [ANY: NONE, OPTIONS: MOCK]
        │   ├── oauth/
        │   │   └── {proxy+}       [ANY: NONE, OPTIONS: MOCK]
        │   ├── refresh             [ANY: NONE, OPTIONS: MOCK]
        │   └── validate            [ANY: NONE, OPTIONS: MOCK]
        ├── tickers/
        │   └── {proxy+}           [ANY: NONE, OPTIONS: MOCK]
        ├── market/
        │   └── {proxy+}           [ANY: NONE, OPTIONS: MOCK]
        ├── timeseries/
        │   └── {proxy+}           [ANY: NONE, OPTIONS: MOCK]
        └── runtime                 [ANY: NONE, OPTIONS: MOCK]

{proxy+}                            [ANY: COGNITO_USER_POOLS, OPTIONS: MOCK] (existing catch-all)
```

### Implementation Strategy

The API Gateway module (`modules/api_gateway/main.tf`) will accept a `public_routes` variable containing the list of unauthenticated route configurations. A `locals` block computes the intermediate and leaf resources. All resources are created via `for_each` to keep the code DRY and ensure atomic deployment.

```hcl
variable "public_routes" {
  description = "Routes that bypass Cognito authorization"
  type = list(object({
    path_parts = list(string)   # e.g., ["api", "v2", "auth", "anonymous"]
    has_proxy  = bool           # true if needs {proxy+} child
  }))
  default = []
}
```

This approach:
- Creates all intermediates and leaves automatically from the path_parts
- Handles `{proxy+}` children where needed (tickers, market, timeseries, magic-link, oauth)
- Attaches `ANY` method with `NONE` authorization + Lambda integration
- Attaches `OPTIONS` method with MOCK integration + CORS headers
- Is idempotent and safe for `terraform plan` review

## Complexity Tracking

No constitution violations requiring justification. The ~77 new resources are necessary for the 10 public route groups and are generated from a compact data structure.

## Post-Design Constitution Re-Check

| Gate | Status | Notes |
|------|--------|-------|
| Auth on management endpoints | PASS | Protected endpoints now require Cognito JWT at infrastructure level |
| Unit tests | PASS | New unit tests for auth behavior + Terraform plan validation |
| E2E tests | PASS | New E2E tests verify 401/200 through API Gateway |
| Atomic deployment | PASS | Single `terraform apply` creates all resources (FR-007) |
| CORS on error responses | PASS | 401/403 Gateway Responses include CORS headers (FR-008) |
| No scope validation | PASS | Authorizer validates JWT signature/expiry only (FR-009) |
