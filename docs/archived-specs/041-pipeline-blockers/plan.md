# Implementation Plan: Pipeline Blockers Resolution

**Branch**: `041-pipeline-blockers` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/041-pipeline-blockers/spec.md`

## Summary

Resolve two remaining pipeline blockers preventing preprod deployment:
1. **ECR Import**: Import orphan `preprod-sse-streaming-lambda` repository into terraform state
2. **KMS Key Policy**: Add CI deployer admin permissions to KMS key policy to allow key creation

Both issues are infrastructure-only fixes with no application code changes.

## Technical Context

**Language/Version**: Terraform 1.5+ with HCL
**Primary Dependencies**: AWS Provider ~> 5.0, terraform CLI
**Storage**: S3 terraform state backend (`sentiment-analyzer-terraform-state-218795110243`)
**Testing**: terraform validate, terraform plan (drift detection)
**Target Platform**: AWS (us-east-1)
**Project Type**: Infrastructure-as-Code (no source structure changes)
**Performance Goals**: N/A (infrastructure provisioning)
**Constraints**: CI deployer (`sentiment-analyzer-preprod-deployer`) must be able to create/manage KMS keys
**Scale/Scope**: 2 resources affected (1 ECR repo, 1 KMS key)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Security: Secrets in code | PASS | No secrets introduced |
| Security: Least-privilege IAM | PASS | KMS admin scoped to CI deployers only |
| Testing: Unit test accompaniment | N/A | Infrastructure-only changes |
| Git: No bypass of pipeline | PASS | All changes go through PR process |
| Deployment: IaC only | PASS | All changes are Terraform |

**Pre-Phase 0**: PASS - No violations

## Project Structure

### Documentation (this feature)

```text
specs/041-pipeline-blockers/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
infrastructure/terraform/
├── main.tf                          # ECR resource: aws_ecr_repository.sse_streaming
├── modules/kms/
│   ├── main.tf                      # KMS key resource: aws_kms_key.main (FIX NEEDED)
│   └── variables.tf                 # Add ci_deployer_arns variable
└── ci-user-policy.tf                # CI deployer user definitions (reference)
```

**Structure Decision**: Existing infrastructure-as-code structure. No new directories needed.

## Implementation Tasks

### Task 1: Import Orphan ECR Repository (FR-001)

**Resource**: `aws_ecr_repository.sse_streaming` in `main.tf:567`
**AWS Resource**: `preprod-sse-streaming-lambda` (exists in AWS)
**State**: Missing from terraform state

**Action**: One-time terraform import command

```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl -backend-config="region=us-east-1"
terraform import aws_ecr_repository.sse_streaming preprod-sse-streaming-lambda
terraform plan  # Verify no changes needed
```

**Verification**: `terraform plan` shows no changes to ECR repository

### Task 2: Fix KMS Key Policy (FR-002, FR-003)

**Resource**: `aws_kms_key.main` in `modules/kms/main.tf:24-76`
**Problem**: Key policy only grants `kms:*` to root account. AWS requires creating principal to also have key management.

**Current Policy** (problematic):
```hcl
Statement = [
  {
    Sid = "RootAccess"
    Principal = { AWS = "arn:aws:iam::${account_id}:root" }
    Action = "kms:*"
    Resource = "*"
  },
  # ... service access statements
]
```

**Required Change**: Add statement for CI deployer key administration

```hcl
# CI Deployer Key Administration
{
  Sid       = "CIDeployerKeyAdmin"
  Effect    = "Allow"
  Principal = {
    AWS = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-preprod-deployer",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-prod-deployer"
    ]
  }
  Action = [
    "kms:Create*",
    "kms:Describe*",
    "kms:Enable*",
    "kms:List*",
    "kms:Put*",
    "kms:Update*",
    "kms:Revoke*",
    "kms:Disable*",
    "kms:Get*",
    "kms:Delete*",
    "kms:TagResource",
    "kms:UntagResource",
    "kms:ScheduleKeyDeletion",
    "kms:CancelKeyDeletion"
  ]
  Resource = "*"
}
```

**Alternative**: Use variable for CI deployer ARNs for reusability

**Verification**: `terraform apply` creates KMS key without `MalformedPolicyDocumentException`

### Task 3: Pipeline Validation (FR-004)

**Action**: Push changes, monitor pipeline

**Expected Result**:
1. Terraform init succeeds (state bucket accessible - verified in spec 019)
2. Terraform plan shows KMS key policy change only
3. Terraform apply creates KMS key successfully
4. No `RepositoryAlreadyExistsException` errors
5. No `MalformedPolicyDocumentException` errors

## Edge Case Handling

| Edge Case | Resolution |
|-----------|------------|
| ECR repo has images | Import preserves existing images |
| KMS key exists in failed state | Delete existing key first if in pending deletion |
| Prod deployer also needs KMS | FR-005 requires same pattern for prod |

## Execution Order

1. **Bootstrap (manual)**: ECR import using `sentiment-analyzer-dev` user
2. **Code Change**: KMS key policy update in `modules/kms/main.tf`
3. **Pipeline**: Push → PR → Merge → Automated terraform apply

## Success Criteria Mapping

| SC | Verification |
|----|--------------|
| SC-001 | Pipeline job completes < 10 min |
| SC-002 | No ECR/KMS exceptions in logs |
| SC-003 | Preprod smoke tests pass |
| SC-004 | CI deployer can update key policy |

## Complexity Tracking

No complexity violations. This is a minimal infrastructure fix.
