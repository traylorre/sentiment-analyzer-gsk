# Implementation Plan: CORS API Gateway Fix

**Branch**: `1114-cors-api-gateway-fix` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1114-cors-api-gateway-fix/spec.md`

## Summary

Fix dashboard CORS blocking by routing frontend API calls through Lambda Function URL (which has CORS configured) instead of API Gateway (which lacks CORS on Lambda proxy responses).

**Root Cause Discovered**: The infrastructure has two paths to Lambda:
1. **Lambda Function URL** - Has CORS configured via Terraform `function_url_cors` block ✅
2. **API Gateway** - Uses AWS_PROXY which bypasses response mapping; no CORS headers ❌

Frontend is configured to use API Gateway (`NEXT_PUBLIC_API_URL`), but Lambda Function URL has the CORS configuration.

**Solution**: Update Amplify environment variable to use Lambda Function URL directly.

## Technical Context

**Language/Version**: Terraform 1.5+ (infrastructure change only)
**Primary Dependencies**: AWS Amplify, Lambda Function URL
**Storage**: N/A (configuration change)
**Testing**: Browser-based CORS verification, curl header inspection
**Target Platform**: AWS Amplify + Lambda Function URL
**Project Type**: Web application (frontend configuration change)
**Performance Goals**: No change (same Lambda backend)
**Constraints**: Must maintain authentication flow, must not break existing functionality
**Scale/Scope**: Single environment variable change in Terraform

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Infrastructure as Code | ✅ PASS | Change is Terraform-only |
| Security & Access Control | ✅ PASS | Lambda Function URL uses same auth headers |
| TLS/HTTPS | ✅ PASS | Lambda Function URLs are HTTPS-only |
| No Pipeline Bypass | ✅ PASS | Standard PR workflow |

## Project Structure

### Documentation (this feature)

```text
specs/1114-cors-api-gateway-fix/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
└── checklists/
    └── requirements.md  # Specification quality checklist
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── main.tf                          # Amplify module configuration
└── modules/
    ├── amplify/
    │   └── main.tf                  # NEXT_PUBLIC_API_URL env var (CHANGE HERE)
    └── lambda/
        └── main.tf                  # function_url_cors configuration (already correct)
```

**Structure Decision**: Infrastructure-only change. Modify Amplify module to use Dashboard Lambda Function URL instead of API Gateway endpoint.

## Complexity Tracking

> No violations - simple configuration change.

## Implementation Approach

### Option Analysis (from clarification)

| Option | Description | Complexity | Risk |
|--------|-------------|------------|------|
| A. API Gateway integration responses | Add CORS to gateway | High | Requires AWS_PROXY → regular integration migration |
| **B. Lambda Function URL (SELECTED)** | Point frontend to Function URL | Low | Single env var change |
| C. Conditional Lambda CORS | Detect request source | Medium | Code change + deployment |

**Selected**: Option B - Lambda Function URL already has CORS configured correctly. Simply redirect frontend to use it.

### Key Files to Modify

1. **`infrastructure/terraform/modules/amplify/main.tf`** (line 59)
   - Change: `NEXT_PUBLIC_API_URL = var.api_gateway_url`
   - To: `NEXT_PUBLIC_API_URL = var.dashboard_lambda_url`

2. **`infrastructure/terraform/modules/amplify/variables.tf`**
   - Add: `dashboard_lambda_url` variable

3. **`infrastructure/terraform/main.tf`**
   - Pass Dashboard Lambda Function URL to Amplify module

### Verification Steps

1. `terraform plan` - Verify only Amplify env var changes
2. `terraform apply` - Deploy change
3. Trigger Amplify rebuild (env var change requires rebuild)
4. Test in browser - Verify no CORS errors
5. Verify ticker search works
6. Verify all API operations work

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Auth headers not forwarded | Lambda Function URL accepts same headers (X-User-ID, Authorization) |
| API Gateway features lost | Evaluate: throttling, caching - may need future work if needed |
| Amplify rebuild required | Expected - env var changes trigger rebuild automatically |

## Out of Scope

- API Gateway integration response changes (rejected approach)
- Lambda code modifications (no code changes)
- CloudFront configuration changes (not needed for this fix)
