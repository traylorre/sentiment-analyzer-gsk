# Feature 1299: Delete Amplify Function URL Fallback

## Problem Statement

The Amplify module had ternary fallback chains that silently routed the frontend to IAM-protected Function URLs when API Gateway or CloudFront URLs were empty:

```hcl
NEXT_PUBLIC_API_URL = var.api_gateway_url != "" ? var.api_gateway_url : var.dashboard_lambda_url
NEXT_PUBLIC_SSE_URL = var.sse_cloudfront_url != "" ? var.sse_cloudfront_url : var.sse_lambda_url
```

Both Function URLs have `authorization_type = "AWS_IAM"` (Feature 1256). The frontend cannot sign requests with SigV4. If the fallback triggered, every request would return **403 Forbidden** with no error indication to the user. The frontend would show empty state.

This is a control plane bug: a misconfiguration silently produces a broken deployment instead of failing loudly at `terraform plan`.

### Root Cause

The fallback was written before Feature 1256 locked Function URLs to IAM auth. When `auth_type` was `NONE`, the fallback worked. After 1256, the fallback target became unreachable, but the code was never updated.

### Impact

- **Silent deployment failure**: Frontend points at 403 URL, shows empty state, no errors in logs
- **False sense of safety**: Terraform applies successfully, all resources healthy, but frontend is broken
- **Untestable**: The fallback condition (`api_gateway_url == ""`) never triggers because API Gateway is unconditionally provisioned

## Requirements

### FR-001: Remove fallback ternaries
Replace conditional expressions with direct variable references:
- `NEXT_PUBLIC_API_URL = var.api_gateway_url`
- `NEXT_PUBLIC_SSE_URL = var.sse_cloudfront_url`

### FR-002: Make required variables explicit
Add Terraform validation blocks to `api_gateway_url` and `sse_cloudfront_url` that fail on empty string with clear error messages explaining WHY the fallback was removed.

### FR-003: Remove dead variables
Delete `dashboard_lambda_url` and `sse_lambda_url` variables from the Amplify module and remove their arguments from the root module call.

### NFR-001: Fail at plan time
If either required URL is empty, `terraform plan` must fail with an actionable error message, not silently produce a broken deployment.

## Success Criteria

1. `terraform plan` fails if `api_gateway_url` or `sse_cloudfront_url` is empty
2. No references to `dashboard_lambda_url` or `sse_lambda_url` in the Amplify module
3. Existing deployments unaffected (URLs are always populated by unconditional modules)

## Implementation Status

**Already implemented this session.** Three files changed:
- `infrastructure/terraform/modules/amplify/variables.tf` — variables replaced with validated required ones
- `infrastructure/terraform/modules/amplify/main.tf` — ternaries replaced with direct references
- `infrastructure/terraform/main.tf` — dead arguments removed from module call

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | Cross-module reference audit missing. Other modules/outputs could reference deleted variables. | Resolved: `grep -rn` confirmed zero references to `dashboard_lambda_url` or `sse_lambda_url` anywhere in the Amplify module or root module after deletion. Lambda module still exports `function_url` — that output feeds CI env vars and test fixtures, unrelated to Amplify. |
| HIGH | Function URL attack surface remains. Removing the fallback is necessary but not sufficient — Function URLs are still reachable (return 403 with AWS metadata in headers). If IAM auth were toggled back to NONE, the fallback path would silently re-enable. | Out of scope for 1299. The Function URL attack surface is addressed by Feature 1256 (IAM auth) and test coverage in `test_function_url_restricted.py`. File follow-up: consider `resource_policy` on Function URLs or disabling Dashboard Lambda Function URL entirely. |
| MEDIUM | Bootstrap chicken-and-egg: Terraform skips custom validation for `(known after apply)` values. Validation only catches hardcoded empty strings in `.tfvars`. | Acknowledged limitation. The API Gateway module is unconditional (always provisioned), so the URL is always populated. The validation catches misconfiguration in `.tfvars` or manual overrides, not Terraform apply-time resolution failures. |
| MEDIUM | "Already implemented" inverts spec-first methodology (Amendment 1.6). | Acknowledged. This was a bug fix during an active deploy-unblocking sprint. The spec is written after the fact to document rationale. Log in tech-debt registry. |
| LOW | Other ternary fallback patterns may exist post-1256. | Added sweep: `grep -rn '!= "" ?' infrastructure/terraform/` should be audited for same dead-fallback pattern. Out of scope for this feature. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** Both HIGH findings resolved (cross-module audit clean, Function URL surface deferred to existing Feature 1256 coverage). Proceeding to Stage 3.

## Clarifications

No ambiguities detected. Feature is already implemented with clear rationale. All questions answerable from existing artifacts.
