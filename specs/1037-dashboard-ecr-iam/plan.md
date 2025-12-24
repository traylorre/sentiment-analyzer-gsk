# Implementation Plan: Dashboard ECR IAM Policy Fix

**Branch**: `1037-dashboard-ecr-iam` | **Date**: 2025-12-23 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1037-dashboard-ecr-iam/spec.md`

## Summary

Add `*-dashboard-lambda*` ECR repository pattern to the CI deploy IAM policy to allow pushing Dashboard Lambda container images. This is a minimal Terraform change to fix a 403 Forbidden error blocking the deploy pipeline.

## Technical Context

**Language/Version**: Terraform 1.5+ (HCL)
**Primary Dependencies**: AWS Provider ~> 5.0
**Storage**: N/A (IAM policy change)
**Testing**: Pipeline validation (GitHub Actions deploy workflow)
**Target Platform**: AWS IAM
**Project Type**: Infrastructure
**Performance Goals**: N/A
**Constraints**: Must follow existing resource naming patterns
**Scale/Scope**: Single policy update (2 statements)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] **No over-engineering**: Single pattern addition, no architectural changes
- [x] **Principal of least privilege**: Pattern is specific to dashboard-lambda repositories
- [x] **Follow existing patterns**: Uses same ARN pattern structure as existing ECR statements
- [x] **No quick fixes without spec**: This spec documents the fix properly

## Project Structure

### Documentation (this feature)

```text
specs/1037-dashboard-ecr-iam/
├── plan.md              # This file
├── spec.md              # Feature specification
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
infrastructure/terraform/
└── ci-user-policy.tf    # IAM policy file to modify
```

**Structure Decision**: Single file modification - add one ARN pattern to two existing statements.

## Implementation Approach

### File to Modify

**infrastructure/terraform/ci-user-policy.tf**

1. **ECR Statement** (lines 298-302): Add `"arn:aws:ecr:*:*:repository/*-dashboard-lambda*"` to resources
2. **ECRImages Statement** (lines 321-325): Add `"arn:aws:ecr:*:*:repository/*-dashboard-lambda*"` to resources

### Change Summary

```hcl
# Before (ECR statement resources)
resources = [
  "arn:aws:ecr:*:*:repository/*-sentiment-*",
  "arn:aws:ecr:*:*:repository/*-sse-streaming-*",
  "arn:aws:ecr:*:*:repository/*-analysis-*"
]

# After (ECR statement resources)
resources = [
  "arn:aws:ecr:*:*:repository/*-sentiment-*",
  "arn:aws:ecr:*:*:repository/*-sse-streaming-*",
  "arn:aws:ecr:*:*:repository/*-analysis-*",
  "arn:aws:ecr:*:*:repository/*-dashboard-lambda*"
]
```

Same pattern for ECRImages statement.

## Complexity Tracking

No violations. This is a minimal, targeted fix.

## Risk Assessment

- **Low Risk**: Adding one resource pattern to existing policy
- **No Breaking Changes**: Existing patterns unchanged
- **Rollback**: Git revert the single file change
- **Validation**: Deploy pipeline success confirms fix
