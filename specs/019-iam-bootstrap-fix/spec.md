# Feature Specification: IAM Bootstrap - Deployer S3 State Bucket Access

**Feature Branch**: `019-iam-bootstrap-fix`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "IAM bootstrap chicken-and-egg problem: deployer cannot update its own S3 permissions because it lacks access to terraform state bucket"

## Problem Analysis

### Root Cause Investigation

**Symptom**: Pipeline fails at "Terraform Init (Preprod)" with:
```
User: arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer
is not authorized to perform: s3:ListBucket on resource:
arn:aws:s3:::sentiment-analyzer-terraform-state-218795110243
```

**Discovery**:

| Component | Pattern | Matches Bucket? |
|-----------|---------|-----------------|
| Actual S3 Bucket | `sentiment-analyzer-terraform-state-218795110243` | N/A |
| ci-user-policy.tf | `sentiment-analyzer-terraform-state-*` | YES |
| preprod-deployer-policy.json | `sentiment-analyzer-terraform-state-*` | YES |
| bootstrap/main.tf | `sentiment-analyzer-terraform-state-${account_id}` | YES |

**Conclusion**: The patterns in the codebase are CORRECT. The issue is that the AWS IAM policy attached to `sentiment-analyzer-preprod-deployer` has NOT been updated to match the code.

### Chicken-and-Egg Problem

1. **To fix the IAM policy** - Must run `terraform apply` targeting IAM resources
2. **To run terraform** - Need access to S3 state bucket for terraform state
3. **To access state bucket** - Need the IAM policy to be fixed

**Solution**: Use a different IAM principal (dev user) that already has state bucket access to apply the IAM policy updates.

### Available Bootstrap Path

```
Current identity: arn:aws:iam::218795110243:user/sentiment-analyzer-dev
Can access bucket: YES (verified via `aws s3 ls`)
```

The dev user can bootstrap the preprod-deployer's IAM policy.

## User Scenarios & Testing

### User Story 1 - Pipeline Unblocking (Priority: P1)

As a developer, I need the preprod deployment pipeline to successfully initialize terraform so that code changes can be deployed to preprod.

**Why this priority**: Blocks all preprod deployments; highest business impact.

**Independent Test**: Pipeline job "Terraform Init (Preprod)" completes successfully without AccessDenied errors.

**Acceptance Scenarios**:

1. **Given** the preprod-deployer IAM policy is updated, **When** pipeline runs terraform init, **Then** terraform successfully initializes with state from S3
2. **Given** correct IAM permissions, **When** terraform plan runs, **Then** no permission errors occur for state bucket operations

---

### User Story 2 - Self-Healing Pipeline (Priority: P2)

As a DevOps engineer, I need IAM policy changes in the codebase to be automatically applied so that future permission updates don't require manual bootstrap.

**Why this priority**: Prevents recurrence of chicken-and-egg problems.

**Independent Test**: After bootstrap, subsequent IAM policy changes in ci-user-policy.tf are applied automatically by the pipeline.

**Acceptance Scenarios**:

1. **Given** the initial bootstrap is complete, **When** IAM policy terraform is modified, **Then** pipeline can apply the changes without manual intervention

---

### User Story 3 - Constitution Amendment (Priority: P3)

As a team, we need documented procedures for IAM bootstrap scenarios so that future occurrences are handled consistently.

**Why this priority**: Governance and knowledge retention.

**Independent Test**: Constitution contains IAM bootstrap procedure section.

**Acceptance Scenarios**:

1. **Given** a new IAM chicken-and-egg scenario, **When** engineer consults constitution, **Then** they find step-by-step bootstrap procedure

---

### Edge Cases

- What happens if dev user also loses state bucket access? (Requires AWS console or CLI with root/admin)
- What if terraform state is corrupted? (Requires state recovery procedure)
- What if multiple IAM policies need bootstrap? (Must target all relevant resources)

## Requirements

### Functional Requirements

- **FR-001**: ci-user-policy.tf MUST use pattern `sentiment-analyzer-terraform-state-*` for S3 state bucket access
- **FR-002**: Bootstrap procedure MUST be executable by sentiment-analyzer-dev user (or equivalent with state bucket access)
- **FR-003**: Bootstrap MUST target only IAM resources without requiring full terraform apply
- **FR-004**: Constitution MUST document IAM bootstrap procedure for future reference
- **FR-005**: After bootstrap, pipeline MUST be able to self-update IAM policies

### Key Entities

- **IAM User: sentiment-analyzer-preprod-deployer**: CI/CD user for preprod deployments
- **IAM User: sentiment-analyzer-prod-deployer**: CI/CD user for prod deployments
- **IAM User: sentiment-analyzer-dev**: Development user with broader permissions
- **S3 Bucket: sentiment-analyzer-terraform-state-***: Terraform state storage
- **IAM Policy: ci_deploy_storage**: Policy granting S3 state bucket access

## Success Criteria

### Measurable Outcomes

- **SC-001**: Pipeline job "Terraform Init (Preprod)" passes within 60 seconds
- **SC-002**: No AccessDenied errors in terraform init/plan/apply for state bucket
- **SC-003**: Constitution contains bootstrap procedure (Amendment 1.6+)
- **SC-004**: Future IAM policy changes apply automatically without manual intervention

## Bootstrap Procedure (Reference)

```bash
# Run from developer machine with sentiment-analyzer-dev credentials
cd /home/traylorre/projects/sentiment-analyzer-gsk/infrastructure/terraform

# Verify identity (should be sentiment-analyzer-dev, NOT preprod-deployer)
aws sts get-caller-identity

# Initialize terraform with preprod backend
terraform init -backend-config=backend-preprod.hcl -backend-config="region=us-east-1" -reconfigure

# Apply ONLY the IAM policy resources
terraform apply \
  -target=aws_iam_policy.ci_deploy_storage \
  -target=aws_iam_user_policy_attachment.ci_deploy_storage_preprod \
  -target=aws_iam_user_policy_attachment.ci_deploy_storage_prod \
  -var="environment=preprod" \
  -var="aws_region=us-east-1"
```

## Assumptions

- The sentiment-analyzer-dev user has permission to modify IAM policies for other users
- The dev user's credentials are available locally via AWS default profile
- Terraform state in S3 is not corrupted or locked
