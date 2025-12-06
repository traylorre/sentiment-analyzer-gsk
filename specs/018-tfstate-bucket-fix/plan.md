# Implementation Plan: Fix Terraform State Bucket Permission Mismatch

**Branch**: `018-tfstate-bucket-fix` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-tfstate-bucket-fix/spec.md`

## Summary

Fix IAM policy patterns to match actual S3 bucket names for Terraform state storage. The preprod and prod environments use bucket `sentiment-analyzer-terraform-state-{account}` but IAM policies reference `sentiment-analyzer-tfstate-*`, causing AccessDenied errors during Terraform init. Clean replacement of all patterns - no backward compatibility needed.

## Technical Context

**Language/Version**: N/A (IAM Policy JSON, HCL configuration)
**Primary Dependencies**: AWS IAM, S3, Terraform
**Storage**: S3 (Terraform state bucket)
**Testing**: Pipeline execution validation
**Target Platform**: AWS
**Project Type**: Infrastructure configuration
**Performance Goals**: N/A
**Constraints**: Must maintain environment isolation via object path prefixes
**Scale/Scope**: 4 policy files, 1 backend config, 1 bootstrap file, 7+ documentation files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| IAM Least Privilege | PASS | Policies scoped to environment-specific paths |
| TLS in Transit | N/A | Not applicable to IAM policy |
| Secrets Not in Source | PASS | No secrets involved |
| Pre-Push Requirements | Will follow | GPG-signed commits, feature branch |

## Root Cause Analysis

**Discovery**: Pipeline failure at "Terraform Init (Preprod)" step with error:
```
User: sentiment-analyzer-preprod-deployer is not authorized to perform:
s3:ListBucket on resource: arn:aws:s3:::sentiment-analyzer-terraform-state-218795110243
```

**Root Cause**: Bucket naming inconsistency between environments:

| Environment | Actual Bucket Name | IAM Policy Pattern | Match? |
|-------------|-------------------|-------------------|--------|
| Dev | `sentiment-analyzer-tfstate-*` | `sentiment-analyzer-tfstate-*` | YES |
| Preprod | `sentiment-analyzer-terraform-state-*` | `sentiment-analyzer-tfstate-*` | NO |
| Prod | `sentiment-analyzer-terraform-state-*` | `sentiment-analyzer-tfstate-*` | NO |
| CI User | (all environments) | `*-sentiment-tfstate-*` | NO (for preprod/prod) |

## Files Requiring Updates

### Policy Files (Pattern Migration)

| File | Current Pattern | New Pattern |
|------|-----------------|-------------|
| `infrastructure/iam-policies/preprod-deployer-policy.json` | `sentiment-analyzer-tfstate-*` | `sentiment-analyzer-terraform-state-*` |
| `infrastructure/iam-policies/prod-deployer-policy.json` | `sentiment-analyzer-tfstate-*` | `sentiment-analyzer-terraform-state-*` |
| `docs/iam-policies/dev-deployer-policy.json` | `sentiment-analyzer-tfstate-*` | `sentiment-analyzer-terraform-state-*` |
| `infrastructure/terraform/ci-user-policy.tf` | `*-sentiment-tfstate-*` | `*-sentiment-terraform-state-*` |

### Backend Configuration (Pattern Migration)

| File | Current Value | New Value |
|------|---------------|-----------|
| `infrastructure/terraform/backend-dev.hcl` | `sentiment-analyzer-tfstate-218795110243` | `sentiment-analyzer-terraform-state-218795110243` |

### Bootstrap Terraform (Future Buckets)

| File | Current Pattern | New Pattern |
|------|-----------------|-------------|
| `infrastructure/terraform/bootstrap/main.tf` | `sentiment-analyzer-tfstate-${account}` | `sentiment-analyzer-terraform-state-${account}` |

### Documentation Files (Pattern References)

| File | Action |
|------|--------|
| `infrastructure/docs/CREDENTIAL_SEPARATION_SETUP.md` | Update all `tfstate` → `terraform-state` |
| `infrastructure/docs/TERRAFORM_RESOURCE_VERIFICATION.md` | Update pattern reference |
| `docs/TERRAFORM_DEPLOYMENT_FLOW.md` | Update diagram/pattern reference |
| `docs/PROMOTION_WORKFLOW_DESIGN.md` | Update policy examples |
| `docs/GET_DASHBOARD_RUNNING.md` | Update bucket reference |
| `docs/PRODUCTION_PREFLIGHT_CHECKLIST.md` | Update state file paths |
| `CLAUDE.md` | Update bucket pattern reference |

## Project Structure

### Documentation (this feature)

```text
specs/018-tfstate-bucket-fix/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output (complete)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (next step)
```

### Source Code (files to modify)

```text
infrastructure/
├── iam-policies/
│   ├── preprod-deployer-policy.json  # Pattern fix
│   └── prod-deployer-policy.json     # Pattern fix
├── terraform/
│   ├── ci-user-policy.tf             # Pattern fix
│   ├── backend-dev.hcl               # Bucket name fix
│   └── bootstrap/
│       └── main.tf                   # Future bucket pattern
└── docs/
    ├── CREDENTIAL_SEPARATION_SETUP.md # Doc update
    └── TERRAFORM_RESOURCE_VERIFICATION.md # Doc update

docs/
├── iam-policies/
│   └── dev-deployer-policy.json      # Pattern fix
├── TERRAFORM_DEPLOYMENT_FLOW.md      # Doc update
├── PROMOTION_WORKFLOW_DESIGN.md      # Doc update
├── GET_DASHBOARD_RUNNING.md          # Doc update
└── PRODUCTION_PREFLIGHT_CHECKLIST.md # Doc update

CLAUDE.md                             # Doc update
```

**Structure Decision**: Existing infrastructure configuration - modifying IAM policy JSON files, Terraform HCL, and documentation.

## Complexity Tracking

No violations. This is a straightforward pattern fix with no architectural changes.

## Implementation Approach

### Strategy: Clean Replacement (No Backward Compatibility)

Dev compatibility not required - pipeline only verifies integration tests pass and Terraform can deploy. Performing clean replacement of all patterns.

### Specific Changes

**preprod-deployer-policy.json (TerraformStateAccess statement)**:
```json
"Resource": [
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*/preprod/*"
]
```

**prod-deployer-policy.json (TerraformStateAccess statement)**:
```json
"Resource": [
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*/prod/*"
]
```

**dev-deployer-policy.json (TerraformStateAccess statement)**:
```json
"Resource": [
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*/dev/*"
]
```

**ci-user-policy.tf (TerraformState statement)**:
```hcl
resources = [
  "arn:aws:s3:::*-sentiment-terraform-state-*",
  "arn:aws:s3:::*-sentiment-terraform-state-*/*",
]
```

**backend-dev.hcl**:
```hcl
bucket = "sentiment-analyzer-terraform-state-218795110243"
```

**bootstrap/main.tf**:
```hcl
bucket = "sentiment-analyzer-terraform-state-${data.aws_caller_identity.current.account_id}"
```

**Documentation updates**: Replace all occurrences of `tfstate` with `terraform-state` in all listed documentation files.

## Validation Plan

1. **Pre-deployment**: Search for remaining `tfstate` occurrences
2. **Post-deployment**: Verify pipeline completes "Terraform Init (Preprod)" step
3. **Full validation**: Confirm preprod deployment completes end-to-end

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Over-permissive patterns | Patterns are specific to sentiment-analyzer prefix |
| Documentation drift | Updating all documentation references |

## Next Steps

1. `/speckit.tasks` - Generate task breakdown
2. Implement changes per task list
3. Push to feature branch
4. Validate pipeline success
