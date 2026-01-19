# Implementation Plan: Remove CloudFront Terraform Module

**Branch**: `1203-remove-cloudfront-module` | **Date**: 2026-01-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1203-remove-cloudfront-module/spec.md`

## Summary

Remove the vestigial CloudFront Terraform module and all references. CloudFront was originally designed for serving the dashboard via S3, but the architecture evolved to use Amplify for frontend hosting. Amplify connects directly to Lambda Function URLs, making CloudFront redundant. This cleanup eliminates confusion, maintenance burden, and ensures code credibility.

## Technical Context

**Language/Version**: Terraform 1.5+ with AWS Provider ~> 5.0
**Primary Dependencies**: AWS CloudFront, S3, IAM, CloudWatch RUM
**Storage**: N/A (infrastructure deletion)
**Testing**: `terraform validate`, `terraform plan`
**Target Platform**: AWS
**Project Type**: Infrastructure-as-Code
**Performance Goals**: N/A
**Constraints**: Must pass `terraform validate` after removal
**Scale/Scope**: 7 files to modify, 1 module directory to delete

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Requirement | Status | Notes |
|-------------|--------|-------|
| Infrastructure as Code | PASS | Using Terraform per constitution Section 5 |
| GPG Signing | PASS | All commits will be signed per Section 8 |
| Pipeline Compliance | PASS | Will run through full CI/CD pipeline |
| No Pipeline Bypass | PASS | Will not bypass any checks |

No constitution violations. This is a cleanup operation that simplifies the codebase.

## Project Structure

### Documentation (this feature)

```text
specs/1203-remove-cloudfront-module/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # All CloudFront references identified
├── quickstart.md        # Deletion steps
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Task breakdown (from /speckit.tasks)
```

### Source Code Changes

```text
infrastructure/terraform/
├── main.tf              # DELETE: module call, outputs, dependencies
├── variables.tf         # DELETE: cloudfront_* variables
├── ci-user-policy.tf    # DELETE: CloudFront IAM permissions
└── modules/
    ├── cloudfront/      # DELETE ENTIRE DIRECTORY
    │   ├── main.tf
    │   ├── variables.tf
    │   └── outputs.tf
    └── cloudwatch-rum/
        └── variables.tf # MODIFY: Remove CloudFront reference in description
```

**Structure Decision**: Infrastructure cleanup - no new structure needed. Removing files and references only.

## Deletion Scope

### Files to Delete Entirely
- `modules/cloudfront/main.tf` (~465 lines)
- `modules/cloudfront/variables.tf` (~84 lines)
- `modules/cloudfront/outputs.tf` (~34 lines)

### Files to Modify

| File | Lines to Remove | What to Remove |
|------|-----------------|----------------|
| `main.tf` | ~30 lines | Module call (93-119), outputs (1176-1195), dependencies |
| `variables.tf` | ~14 lines | `cloudfront_custom_domain`, `cloudfront_acm_certificate_arn` |
| `ci-user-policy.tf` | ~80 lines | CloudFront IAM permissions (882-957), policy description |
| `modules/cloudwatch-rum/variables.tf` | 1 line | CloudFront mention in description |

### Dependencies to Update

The following references to `module.cloudfront.*` must be removed:
1. `module.cloudfront.distribution_domain_name` in CloudWatch RUM module call
2. `module.cloudfront.distribution_domain_name` in notification Lambda env
3. `module.cloudfront.s3_bucket_name` in output
4. `module.cloudfront.dashboard_url` in output
5. `depends_on = [module.cloudfront]` in two places

## Complexity Tracking

No constitution violations. This is a simplification operation.

| Aspect | Before | After |
|--------|--------|-------|
| Module count | N+1 | N |
| IAM policy lines | ~1200 | ~1100 |
| Root outputs | N+4 | N |
| Root variables | N+2 | N |
