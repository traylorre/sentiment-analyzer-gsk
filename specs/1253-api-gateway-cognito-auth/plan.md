# Implementation Plan: Route Frontend Through API Gateway + Enable Cognito Auth

**Branch**: `1253-api-gateway-cognito-auth` | **Date**: 2026-03-24 | **Spec**: `specs/1253-api-gateway-cognito-auth/spec.md`
**Input**: Feature specification from `/specs/1253-api-gateway-cognito-auth/spec.md`

## Summary

Enable Cognito JWT authorization on the API Gateway `{proxy+}` catch-all while creating 11 explicit public resource groups (covering 13+ endpoints) with `authorization = "NONE"`. Switch Amplify frontend from Lambda Function URL to API Gateway URL. Add CORS headers to 401/403 Gateway Responses. Handle two intermediates that double as endpoint paths (FR-012). All changes deploy atomically in one `terraform apply`.

## Technical Context

**Language/Version**: HCL (Terraform 1.5+, AWS Provider ~> 5.0)
**Primary Dependencies**: AWS API Gateway (REST API), AWS Cognito, AWS Amplify, AWS Lambda
**Storage**: N/A (infrastructure-only changes)
**Testing**: `terraform plan` validation, pytest (unit + E2E), Playwright (frontend regression)
**Target Platform**: AWS (us-east-1)
**Project Type**: Infrastructure-as-code (Terraform modules)
**Performance Goals**: Zero compute cost for invalid tokens; Cognito authorizer adds <50ms (cached 300s)
**Constraints**: Atomic deployment required (FR-007); CORS on error responses (FR-008); no scope validation (FR-009)
**Scale/Scope**: ~85 new Terraform resources (11 public groups × ~7 resources + 8 intermediates + 3 gateway responses + 2 intermediate-as-endpoint methods)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Section | Status | Notes |
|------|---------|--------|-------|
| Auth on management endpoints | §3 Security | PASS | Cognito JWT at infrastructure level for protected endpoints |
| TLS in transit | §3 Security | PASS | API Gateway enforces HTTPS |
| Secrets not in source control | §3 Security | PASS | Cognito ARN via Terraform module output |
| IaC deployment | §5 Deployment | PASS | All changes via Terraform modules |
| Health check endpoints | §5 Deployment | PASS | /health kept as public endpoint |
| Unit tests for new code | §7 Testing | PASS | Terraform plan validation + E2E auth tests |
| GPG-signed commits | §8 Git Workflow | PASS | All commits signed |
| No pipeline bypass | §8 Git Workflow | PASS | Standard PR flow |
| SAST before push | §10 Local SAST | N/A | No Python code modified |

**Pre-design gate**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/1253-api-gateway-cognito-auth/
├── spec.md              # Feature specification (post-adversarial)
├── plan.md              # This file
├── research.md          # Phase 0: API GW behavior, CORS, Amplify, intermediates
├── data-model.md        # Phase 1: Terraform resource model
├── quickstart.md        # Phase 1: Implementation quickstart
├── contracts/           # Phase 1: Route contracts
│   └── api-gateway-routes.yaml
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 (/speckit.tasks)
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── modules/api_gateway/
│   ├── main.tf              # MODIFY: Public routes, CORS on 401/403, FR-012 intermediates
│   ├── variables.tf         # MODIFY: public_routes variable
│   └── outputs.tf           # No changes
├── modules/amplify/
│   ├── main.tf              # MODIFY: NEXT_PUBLIC_API_URL → API Gateway
│   └── variables.tf         # MODIFY: Add api_gateway_url variable
├── modules/cognito/         # No changes (already exports user_pool_arn)
└── main.tf                  # MODIFY: Wire enable_cognito_auth + cognito_user_pool_arn + api_gateway_url

.github/workflows/
└── deploy.yml               # MODIFY: Add API Gateway smoke test

tests/
├── unit/
│   └── test_api_gateway_cognito.py  # NEW: Auth behavior unit tests
└── e2e/
    └── test_cognito_auth.py         # NEW: E2E 401/200/CORS tests
```

**Structure Decision**: Infrastructure-only. Primary changes in `modules/api_gateway/main.tf`. No Python source changes.

## Architecture

### API Gateway Resource Tree (Final)

```
/ (root)
├── health                              [ANY:NONE, OPTIONS:MOCK]
└── api/                                [no method — intermediate only]
    └── v2/                             [no method — intermediate only]
        ├── auth/                       [no method — intermediate only]
        │   ├── anonymous               [ANY:NONE, OPTIONS:MOCK]
        │   ├── magic-link              [ANY:NONE, OPTIONS:MOCK] ← FR-012: IS an endpoint
        │   │   └── {proxy+}            [ANY:NONE, OPTIONS:MOCK]
        │   ├── oauth/                  [no method — intermediate only]
        │   │   └── {proxy+}            [ANY:NONE, OPTIONS:MOCK]
        │   ├── refresh                 [ANY:NONE, OPTIONS:MOCK]
        │   └── validate                [ANY:NONE, OPTIONS:MOCK]
        ├── notifications/              [no method — intermediate only]
        │   │                           ↑ WAIT: /api/v2/notifications IS an endpoint!
        │   │                           [ANY:COGNITO, OPTIONS:MOCK] ← FR-012
        │   └── unsubscribe            [ANY:NONE, OPTIONS:MOCK]
        ├── tickers/
        │   └── {proxy+}               [ANY:NONE, OPTIONS:MOCK]
        ├── market/
        │   └── {proxy+}               [ANY:NONE, OPTIONS:MOCK]
        ├── timeseries/
        │   └── {proxy+}               [ANY:NONE, OPTIONS:MOCK]
        └── runtime                     [ANY:NONE, OPTIONS:MOCK]

{proxy+}                                [ANY:COGNITO, OPTIONS:MOCK] (existing catch-all)
```

### FR-012: Intermediates That Are Also Endpoints

| Path | Role as Intermediate | Role as Endpoint | Auth |
|------|---------------------|-----------------|------|
| `/api/v2/notifications` | Parent of `/unsubscribe` | `GET` lists notifications | COGNITO_USER_POOLS |
| `/api/v2/auth/magic-link` | Parent of `/{proxy+}` (verify) | `POST` sends magic link | NONE |

Without methods on these, requests to the exact path return 403 `Missing Authentication Token` instead of routing to `{proxy+}`.

## Implementation Strategy

The API Gateway module accepts a `public_routes` variable:

```hcl
variable "public_routes" {
  type = list(object({
    path_parts    = list(string)   # ["api", "v2", "auth", "anonymous"]
    has_proxy     = bool           # true → create {proxy+} child
    is_endpoint   = bool           # true → parent also needs method (FR-012)
    endpoint_auth = string         # "NONE" or "COGNITO_USER_POOLS" (for FR-012 parents)
  }))
}
```

A `locals` block computes:
1. All unique intermediate paths (deduped across routes)
2. Which intermediates need methods (FR-012)
3. Leaf resources with `ANY` + `OPTIONS` methods
4. Lambda proxy integrations for each

All resources created via `for_each` — atomic, DRY, reviewable in `terraform plan`.

## Complexity Tracking

No constitution violations requiring justification.

## Post-Design Constitution Re-Check

| Gate | Status | Notes |
|------|--------|-------|
| Auth on management endpoints | PASS | Cognito at API Gateway + application-level defense-in-depth |
| Unit + E2E tests | PASS | New test files for auth behavior |
| Atomic deployment | PASS | Single terraform apply (FR-007) |
| CORS on errors | PASS | 401/403 Gateway Responses with CORS (FR-008) |
| FR-012 intermediates | PASS | Methods on /notifications and /auth/magic-link |
