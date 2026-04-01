# Feature 1300: Implementation Plan

## Changes

### Terraform (infrastructure/terraform/main.tf)
1. Set `create_function_url = false` on Dashboard Lambda module
2. Remove `function_url_cors` block from Dashboard Lambda module
3. Remove `function_url_auth_type` and `function_url_invoke_mode` from Dashboard Lambda module
4. Remove `output "dashboard_function_url"` from root outputs
5. KEEP `SSE_LAMBDA_URL` env var on Dashboard Lambda (serves runtime config)

### CI/CD (.github/workflows/deploy.yml)
1. Remove `DASHBOARD_URL` retrieval from `terraform output dashboard_function_url` (preprod + prod)
2. Remove `dashboard_url` from GitHub step outputs and job outputs
3. Remove warmup curl to Dashboard Function URL (keep SSE warmup)
4. Remove "Wait for Function URL propagation" step (polled Dashboard URL)
5. Remove `DASHBOARD_FUNCTION_URL` env var from test job
6. Replace `dashboard_url` in deployment metadata with `api_url` (API Gateway)
7. KEEP all SSE_LAMBDA_URL references

### Tests (tests/e2e/test_function_url_restricted.py)
1. Remove `test_dashboard_function_url_returns_403`
2. Remove `test_bearer_token_on_function_url_still_403`
3. Keep `test_sse_function_url_returns_403`
4. Keep `test_api_gateway_health_works`
5. Keep `test_cloudfront_sse_status_works`
6. Rename `TestDirectFunctionURLBlocked` → `TestDirectSSEFunctionURLBlocked` (only SSE tests remain)

## Files Modified

| File | Change |
|------|--------|
| `infrastructure/terraform/main.tf` | Remove Dashboard Function URL config + output |
| `.github/workflows/deploy.yml` | Remove Dashboard URL references, keep SSE |
| `tests/e2e/test_function_url_restricted.py` | Remove 2 Dashboard tests, keep 3 |

## Terraform Plan Gate

Before apply, verify `terraform plan` output shows:
- DESTROY: `aws_lambda_function_url` for Dashboard Lambda only
- NO changes to SSE Lambda Function URL
- NO changes to CloudFront distribution
- NO changes to API Gateway

## Dependencies
- No Python package changes
- No handler changes (handler already uses APIGatewayRestResolver from Feature 1297)

## Adversarial Review #2

No drift between spec and plan. FR-005 contradiction resolved in AR#1. Plan matches corrected spec.

### Gate Statement
**0 CRITICAL, 0 HIGH. No drift.** Proceeding to Stage 7.
