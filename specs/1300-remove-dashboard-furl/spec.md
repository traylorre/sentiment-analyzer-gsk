# Feature 1300: Remove Dashboard Lambda Function URL

## Problem Statement

The Dashboard Lambda has a Function URL (`auth_type = AWS_IAM`) that is zombie infrastructure. No production traffic uses it — the Amplify frontend routes through API Gateway, which invokes Lambda via `lambda:InvokeFunction` (not the Function URL). The Function URL returns 403 to all callers because no `aws_lambda_permission` grants `lambda:InvokeFunctionUrl` to anyone.

Keeping it:
- Expands attack surface (reachable endpoint that leaks AWS metadata in 403 responses)
- Confuses architecture (8 diagrams reference it as if active)
- Bloats CI/CD (warmup curls to a URL that 403s, propagation wait steps for a dead endpoint)
- Wastes test time (2 E2E tests validate a 403 on an endpoint we're removing)

## Requirements

### FR-001: Disable Function URL creation for Dashboard Lambda
Set `create_function_url = false` in the Dashboard Lambda module call in `main.tf`. Remove the `function_url_cors` block and `function_url_invoke_mode` for Dashboard Lambda.

### FR-002: Remove Dashboard Function URL Terraform output
Delete `output "dashboard_function_url"` from root `main.tf`.

### FR-003: Update CI/CD workflow
In `.github/workflows/deploy.yml`:
- Remove `DASHBOARD_FUNCTION_URL` env var from test job
- Remove warmup curl to Dashboard Function URL (keep SSE warmup)
- Remove "Wait for Function URL propagation" step that polls Dashboard Function URL
- Remove `dashboard_url` from deployment metadata JSON (or replace with API Gateway URL)
- Keep all SSE_LAMBDA_URL references (SSE Function URL is actively used)

### FR-004: Update test_function_url_restricted.py
- REMOVE: `test_dashboard_function_url_returns_403` (Dashboard Function URL won't exist)
- REMOVE: `test_bearer_token_on_function_url_still_403` (same)
- KEEP: `test_sse_function_url_returns_403` (SSE Function URL still exists)
- KEEP: `test_api_gateway_health_works` (API Gateway path, unrelated)
- KEEP: `test_cloudfront_sse_status_works` (CloudFront path, unrelated)
- Update `TestDirectFunctionURLBlocked` class: remove Dashboard tests, keep SSE test

### FR-005: KEEP SSE_LAMBDA_URL on Dashboard Lambda
`SSE_LAMBDA_URL` env var on Dashboard Lambda is used by the frontend runtime config endpoint (`/api/v2/runtime`) to tell the browser where to connect for SSE streaming. This is the SSE Lambda's Function URL, NOT the Dashboard Lambda's Function URL. Do NOT remove it.

### NFR-001: SSE Lambda Function URL unaffected
SSE Lambda keeps `create_function_url = true` with `auth_type = AWS_IAM` and `invoke_mode = RESPONSE_STREAM`. CloudFront OAC continues to work.

### NFR-002: Terraform plan shows only expected deletions
`terraform plan` should show removal of Dashboard Function URL resource and related permission. No other resources affected.

## Edge Cases

### EC-1: Terraform state has existing Function URL
Terraform will destroy the `aws_lambda_function_url` resource for Dashboard Lambda. This is safe — no traffic hits it. The Lambda function itself is unaffected.

### EC-2: CI/CD referencing removed output
If any step reads `terraform output dashboard_function_url` and it no longer exists, the `2>/dev/null || echo ""` fallback handles it gracefully. But we should remove the reference entirely.

### EC-3: Dashboard Lambda env var SSE_LAMBDA_URL
The Dashboard Lambda has `SSE_LAMBDA_URL` in its environment. This is used by the frontend runtime config endpoint to tell the browser where to connect for SSE. This is the SSE Function URL, NOT the Dashboard Function URL. KEEP it.

## Success Criteria

1. `create_function_url = false` for Dashboard Lambda
2. No `dashboard_function_url` output in Terraform
3. `terraform plan` shows only Function URL resource deletion
4. CI/CD has no references to Dashboard Function URL
5. E2E tests updated: 2 Dashboard tests removed, 3 remaining tests pass
6. SSE Lambda Function URL completely unaffected

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | FR-005 vs EC-3 contradiction: FR-005 suggested conditionally removing `SSE_LAMBDA_URL`, EC-3 says keep it. Implementer could break frontend SSE discovery. | **Fixed.** FR-005 rewritten to explicitly say KEEP. The env var serves the runtime config endpoint. |
| MEDIUM | Shared module toggle scope: `create_function_url` might affect both Lambdas if the module has a single conditional. | **Mitigated.** The module variable is per-invocation (`module "dashboard_lambda"` and `module "sse_streaming_lambda"` are separate calls). Add explicit `terraform plan` gate to NFR-002: verify SSE Function URL is NOT in the changeset. |
| MEDIUM | Output consumer audit incomplete: no grep of monitoring dashboards, cross-repo references, or CloudWatch alarms for `dashboard_function_url`. | **Mitigated.** Add grep sweep task during implementation. The template repo and security repo should be checked. |
| LOW | CI warmup was hitting 403 anyway (Function URL is IAM-protected). Removing it changes nothing — the warmup was ineffective. | **Acknowledged.** No action needed. The warmup never worked. |
| LOW | Function URL qualifier (alias vs $LATEST) not confirmed. | **Verified from prior research:** Function URL points to the `live` alias. Removing it doesn't affect the alias itself. |
| LOW | 8 diagrams reference Dashboard Function URL — diagram updates are Feature 1301 (separate feature). | **Acknowledged.** Feature 1301 handles diagram updates after this feature. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** FR-005 contradiction fixed. Proceeding to Stage 3.

## Clarifications

### Q1: Does the Lambda module's `create_function_url` variable work per-invocation?
**Answer:** Yes. Each `module "dashboard_lambda"` and `module "sse_streaming_lambda"` call is an independent instance of `modules/lambda`. Setting `create_function_url = false` on one does not affect the other.
**Evidence:** `infrastructure/terraform/modules/lambda/main.tf:140-156` — `count = var.create_function_url ? 1 : 0` on the `aws_lambda_function_url` resource.

### Q2: Is `SSE_LAMBDA_URL` used by the Dashboard Lambda's runtime config endpoint?
**Answer:** Yes. The `/api/v2/runtime` endpoint returns configuration including SSE URL for the frontend to connect. This env var is the SSE Lambda Function URL, passed through to the browser.
**Evidence:** Prior session research confirmed this at `main.tf:466`.

All questions self-answered. No questions deferred to user.
