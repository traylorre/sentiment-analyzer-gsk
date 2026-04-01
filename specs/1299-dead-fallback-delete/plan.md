# Feature 1299: Implementation Plan

## Technical Context

Already implemented. This plan documents the changes for completeness.

## Changes Made

### `infrastructure/terraform/modules/amplify/variables.tf`
- Removed `dashboard_lambda_url` variable (was fallback target for `NEXT_PUBLIC_API_URL`)
- Removed `sse_lambda_url` variable (was fallback target for `NEXT_PUBLIC_SSE_URL`)
- Made `api_gateway_url` required with validation: `condition = var.api_gateway_url != ""`
- Made `sse_cloudfront_url` required with validation: `condition = var.sse_cloudfront_url != ""`
- Both validation error messages explain WHY the fallback was removed (Feature 1256 IAM protection)

### `infrastructure/terraform/modules/amplify/main.tf`
- Replaced `var.api_gateway_url != "" ? var.api_gateway_url : var.dashboard_lambda_url` with `var.api_gateway_url`
- Replaced `var.sse_cloudfront_url != "" ? var.sse_cloudfront_url : var.sse_lambda_url` with `var.sse_cloudfront_url`
- Updated comments to reflect the current architecture

### `infrastructure/terraform/main.tf` (root module)
- Removed `dashboard_lambda_url = module.dashboard_lambda.function_url` from Amplify module call
- Removed `sse_lambda_url = module.sse_streaming_lambda.function_url` from Amplify module call
- Updated comments

## Verification

Cross-module reference audit: `grep -rn 'dashboard_lambda_url\|sse_lambda_url' infrastructure/terraform/modules/amplify/` returns zero results.

## Dependencies

None. Changes are isolated to Terraform configuration. No Python code changes.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Bootstrap validation skipped for `known after apply` | Low | None (API Gateway always provisioned) | Validation catches `.tfvars` misconfig only |
| Other dead fallbacks exist | Medium | Low (separate issue) | Sweep task filed |

## Adversarial Review #2

No drift detected. Feature is already implemented. Spec, plan, and code are consistent. Gate: PASS.
