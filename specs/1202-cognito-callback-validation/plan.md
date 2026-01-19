# Implementation Plan: Cognito Callback URL Validation

**Branch**: `1202-cognito-callback-validation` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1202-cognito-callback-validation/spec.md`

## Summary

Add Terraform outputs to expose Cognito OAuth callback and logout URLs for visibility and validation. The implementation requires adding two outputs to the Cognito module and exposing them at root level. This enables engineers to verify OAuth configuration without AWS console access.

**Critical Insight**: The Cognito module uses `lifecycle { ignore_changes = [callback_urls, logout_urls] }` because values are patched post-creation by `terraform_data.cognito_callback_patch`. Outputs will show Terraform-configured values, which may differ from patched AWS state when Amplify is enabled.

## Technical Context

**Language/Version**: Terraform 1.0+ with AWS Provider ~> 5.0
**Primary Dependencies**: AWS Cognito User Pool Client, terraform_data provisioner
**Storage**: N/A (infrastructure-as-code outputs)
**Testing**: `terraform output`, `terraform plan`, AWS CLI validation
**Target Platform**: AWS Cognito
**Project Type**: Infrastructure-as-Code (Terraform modules)
**Performance Goals**: N/A (output generation is instant)
**Constraints**: Must not break existing deployments; must handle conditional Amplify deployment
**Scale/Scope**: 2 new module outputs + 2 new root outputs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**Reviewed Constitution**: `.specify/memory/constitution.md` (Version 1.6)

**Relevant Sections**:
- **Section 5 - Deployment Requirements**: Infrastructure as Code using Terraform is mandated. This feature aligns with IaC principles.
- **Section 5 - Terraform Cloud specifics**: Outputs are exported for programmatic access and CI/CD validation.
- **Section 7 - Testing & Validation**: Outputs enable verification without AWS console access.

**No Constitution Violations**: This feature introduces no new resources, patterns, or dependencies that conflict with the constitution.

## Project Structure

### Documentation (this feature)

```text
specs/1202-cognito-callback-validation/
├── plan.md              # This file
├── research.md          # Research findings
├── quickstart.md        # Quick implementation guide
├── spec.md              # Feature specification
└── checklists/          # Validation checklists
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── main.tf                           # Add 2 root outputs (~lines 1175-1185)
└── modules/cognito/
    └── outputs.tf                    # Add 2 module outputs
```

**Structure Decision**: Minimal change - only Terraform output definitions. No new modules, resources, or structural changes.

## Implementation Approach

### Phase 1: Add Module Outputs (Cognito)

**File**: `infrastructure/terraform/modules/cognito/outputs.tf`

Add two new outputs after existing outputs:
```hcl
output "callback_urls" {
  description = "Configured callback URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.callback_urls
}

output "logout_urls" {
  description = "Configured logout URLs for OAuth redirects"
  value       = aws_cognito_user_pool_client.dashboard.logout_urls
}
```

### Phase 2: Expose Root Outputs

**File**: `infrastructure/terraform/main.tf` (add after existing outputs section)

Add two new root outputs:
```hcl
output "cognito_callback_urls" {
  description = "Cognito OAuth callback URLs (Terraform-configured values)"
  value       = module.cognito.callback_urls
}

output "cognito_logout_urls" {
  description = "Cognito OAuth logout URLs (Terraform-configured values)"
  value       = module.cognito.logout_urls
}
```

## Edge Cases Addressed

| Edge Case | Solution |
|-----------|----------|
| Cognito module not deployed | Not applicable - Cognito is always deployed (no `count` conditional) |
| Multiple callback URLs | Output is a list type, displays all configured URLs |
| First deployment (no Amplify patch yet) | Output shows initial values from variables |
| Amplify disabled | Output shows variable-defined URLs (no patching occurs) |

## Files to Modify

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/cognito/outputs.tf` | Add `callback_urls` and `logout_urls` outputs |
| `infrastructure/terraform/main.tf` | Add `cognito_callback_urls` and `cognito_logout_urls` root outputs |

## Testing Approach

1. **Pre-Implementation**: Run `terraform plan` to confirm no unexpected changes
2. **Post-Implementation**: Run `terraform apply` and verify outputs with `terraform output cognito_callback_urls`
3. **Validation**: Compare Terraform output against AWS CLI
4. **CI Integration**: Verify outputs contain expected URL patterns

## Complexity Tracking

No constitution violations or complexity overrides required. This is a straightforward output addition following existing patterns.
