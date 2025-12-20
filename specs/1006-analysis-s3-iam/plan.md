# Implementation Plan: Fix Analysis Lambda S3 IAM Permissions

**Branch**: `1006-analysis-s3-iam` | **Date**: 2025-12-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1006-analysis-s3-iam/spec.md`

## Summary

Add `s3:HeadObject` permission to the Analysis Lambda's IAM policy to enable boto3's `download_file()` method to successfully download ML models from S3. Currently the policy only has `s3:GetObject`, but `download_file()` internally calls `HeadObject` first to get object metadata, resulting in a 403 Forbidden error.

## Technical Context

**Language/Version**: Terraform 1.5+ (HCL), existing infrastructure-as-code
**Primary Dependencies**: AWS IAM, S3, Lambda (no code changes - infrastructure only)
**Storage**: S3 bucket `sentiment-analyzer-models-{account_id}`
**Testing**: terraform validate, terraform plan, manual Lambda invocation
**Target Platform**: AWS us-east-1
**Project Type**: Infrastructure fix (single file change)
**Performance Goals**: N/A (IAM permission, no performance impact)
**Constraints**: Must not remove existing `s3:GetObject` permission
**Scale/Scope**: Single IAM policy statement, 1 line addition

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security & IAM least-privilege | PASS | Adding minimal required permission (HeadObject) scoped to specific bucket ARN |
| Infrastructure as Code | PASS | Change via Terraform, not console |
| Model artifacts access | PASS | Constitution requires Lambda access to S3 model artifacts (§84-86) |

No violations. Proceed with implementation.

## Project Structure

### Documentation (this feature)

```text
specs/1006-analysis-s3-iam/
├── spec.md              # Feature specification
├── plan.md              # This file
├── checklists/
│   └── requirements.md  # Validation checklist
└── tasks.md             # Implementation tasks (next step)
```

### Source Code (repository root)

```text
infrastructure/terraform/modules/iam/main.tf   # Line 274-276 - analysis_s3_model policy
```

**Structure Decision**: Infrastructure-only change. Single file modification in existing IAM module.

## Complexity Tracking

No violations to justify - this is the simplest possible fix (adding one S3 action to an existing policy).

## Phase 0: Research

**No research required** - this is a well-documented AWS pattern:
- boto3 `download_file()` uses S3 Transfer Manager which calls `HeadObject` before `GetObject`
- AWS documentation confirms this behavior
- Root cause already confirmed via CloudWatch logs (`403 on HeadObject operation`)

## Phase 1: Design

### Data Model

N/A - no data model changes. This is an IAM permission fix.

### API Contracts

N/A - no API changes. This is an IAM permission fix.

### Implementation Approach

**File**: `infrastructure/terraform/modules/iam/main.tf`
**Location**: Lines 274-276 (analysis_s3_model policy)

**Current State**:
```hcl
Action = [
  "s3:GetObject"
]
```

**Target State**:
```hcl
Action = [
  "s3:GetObject",
  "s3:HeadObject"
]
```

### Verification Steps

1. `terraform fmt` - format check
2. `terraform validate` - syntax validation
3. `terraform plan` - verify only IAM policy changes
4. Deploy to preprod
5. Invoke Analysis Lambda - verify no 403 errors
6. Check DynamoDB - verify items get sentiment attribute
7. Check dashboard - verify non-zero counts

## Next Steps

Run `/speckit.tasks` to generate the implementation task list.
