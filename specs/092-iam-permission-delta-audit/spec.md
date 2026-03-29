# Feature 092: IAM Permission Delta Audit

**Status**: Draft
**Created**: 2025-12-11
**Related Issues**: Pipeline failures in sentiment-analyzer-gsk main branch

---

## Problem Statement

The target repo (sentiment-analyzer-gsk) Deploy Pipeline is failing with three categories of IAM permission errors:

1. **S3 State Backend AccessDenied** - Can't write Terraform state
2. **IAM AttachUserPolicy AccessDenied** (8 instances) - Can't attach deployment policies to CI users
3. **CloudFront UpdateResponseHeadersPolicy AccessDenied** - Tag condition mismatch

These failures represent a **dual failure mode**:

- **Operational**: Pipeline blocked, no deployments possible
- **Methodology**: Validators (`/iam-validate`, `/iam-resource-alignment-validate`) did not detect these issues pre-merge

---

## Root Cause Analysis

### RC-001: S3 State Bucket Naming Mismatch

**Pipeline Error**:

```
Error: saving state: failed to upload state: operation error S3: PutObject, https response error StatusCode: 403, AccessDenied
Bucket: sentiment-analyzer-terraform-state-218795110243
```

**Policy Pattern** (`ci-user-policy.tf:831-834`):

```hcl
resources = [
  "arn:aws:s3:::*-sentiment-tfstate",
  "arn:aws:s3:::*-sentiment-tfstate/*"
]
```

**Actual Bucket** (`backend-preprod.hcl`):

```hcl
bucket = "sentiment-analyzer-terraform-state-218795110243"
```

**Mismatch**: Pattern `*-sentiment-tfstate` does NOT match `sentiment-analyzer-terraform-state-218795110243`

**Why Validator Missed It**: The `IAMResourceAlignmentValidator` maps S3 to `aws_s3_bucket` resources, but `backend.hcl` files are NOT Terraform resources - they're configuration. The validator only checks `resource "aws_s3_bucket"` blocks, not backend configurations.

---

### RC-002: IAM User Naming Convention Mismatch

**Pipeline Error** (8 instances):

```
Error: attaching policy (arn:aws:iam::*:policy/CIDeployCore) to IAM User (preprod-sentiment-deployer): operation error IAM: AttachUserPolicy, https response error StatusCode: 403, AccessDenied
```

**Policy Pattern** (`ci-user-policy.tf:639-641`):

```hcl
resources = [
  "arn:aws:iam::*:user/*-sentiment-deployer"
]
```

**CI User Executing the Action**: `sentiment-analyzer-preprod-deployer` (legacy naming)

**Target User Being Modified**: `preprod-sentiment-deployer` (new naming convention)

**Analysis**: The policy allows the deployer to attach policies to users matching `*-sentiment-deployer`. The target user `preprod-sentiment-deployer` DOES match this pattern. However, the CI user itself (`sentiment-analyzer-preprod-deployer`) may lack permissions because IAM also checks if the calling principal has permission - and the policy must allow the action based on the caller's identity.

**Critical Insight**: The IAM resource ARN pattern validates the _target_ of the action, but the CI user identity (`sentiment-analyzer-preprod-deployer`) must also be authorized. The `090-security-first-burndown` migration updated policy patterns but did NOT rename the actual CI user in AWS.

**Why Validator Missed It**: The `IAMResourceAlignmentValidator` only checks Terraform resources vs IAM policy ARN patterns. It does NOT validate that the executing CI user exists and has correct permissions - that's an AWS IAM state validation, not a code validation.

---

### RC-003: CloudFront Tag Condition Mismatch

**Pipeline Error**:

```
Error: updating CloudFront Response Headers Policy: operation error CloudFront: UpdateResponseHeadersPolicy, https response error StatusCode: 403, AccessDenied
```

**Policy Pattern** (`ci-user-policy.tf:871-877`):

```hcl
condition {
  test     = "StringLike"
  variable = "aws:ResourceTag/Name"
  values   = ["*-sentiment-*"]
}
```

**Analysis**: The CloudFront Response Headers Policy resource in AWS lacks a `Name` tag matching `*-sentiment-*`, causing the IAM condition to fail.

**Why Validator Missed It**: No validator currently checks that AWS resources have the tags required by IAM policy conditions. This is a gap in `IAMResourceAlignmentValidator`.

---

## Validator Gap Analysis

### GAP-001: Backend Configuration Not Validated

**Current Behavior**: `IAMResourceAlignmentValidator` only scans `resource "..." {}` blocks.

**Gap**: `backend.hcl` files configure state storage but aren't validated against IAM policies.

**Impact**: S3 state bucket naming mismatches go undetected.

**Required Enhancement**: Parse `backend*.hcl` files and validate `bucket` attribute against IAM S3 policy patterns.

---

### GAP-002: IAM User Entity vs Resource ARN Validation

**Current Behavior**: Validators check policy-to-resource alignment but assume the CI user executing actions has correct permissions.

**Gap**: No validation that the _executing_ CI user's ARN matches patterns in IAM policies that restrict who can perform actions.

**Impact**: Legacy CI user names (`sentiment-analyzer-*-deployer`) can fail to match new policy patterns (`*-sentiment-deployer`).

**Required Enhancement**: Add validator that extracts CI user ARNs from GitHub Actions workflows and validates against IAM policy patterns.

---

### GAP-003: IAM Tag Conditions vs Terraform Tags

**Current Behavior**: `IAMResourceAlignmentValidator` checks resource names against ARN patterns.

**Gap**: No validation that resources have tags matching `aws:ResourceTag/*` conditions in IAM policies.

**Impact**: CloudFront (and other tag-conditioned) permissions fail at runtime.

**Required Enhancement**: Parse IAM `Condition` blocks, extract tag requirements, and validate Terraform resources have matching tags.

---

### GAP-004: Pre-existing AWS State vs Terraform Configuration

**Current Behavior**: Validators only check code (Terraform files).

**Gap**: Pre-existing AWS resources (S3 bucket, IAM users created outside Terraform or before migration) may have legacy names that don't match new patterns.

**Impact**: Terraform `apply` fails because AWS state doesn't match policy expectations.

**Note**: This is partially outside validation scope (requires AWS API calls), but documentation should warn about state migration requirements.

---

## Success Criteria

### SC-001: S3 Backend Validation (GAP-001)

Extend `IAMResourceAlignmentValidator` to parse `backend*.hcl` files and validate S3 bucket names against IAM patterns.

**Test**: Create fixture with mismatched backend bucket name, verify validator reports ALIGN-003 finding.

### SC-002: CI User ARN Validation (GAP-002)

Create new validator rule to extract CI user references from Terraform and validate against IAM policy user patterns.

**Test**: Create fixture with legacy CI user name, verify validator reports ALIGN-004 finding.

### SC-003: Tag Condition Validation (GAP-003)

Extend `IAMResourceAlignmentValidator` to parse IAM `Condition` blocks and validate resources have required tags.

**Test**: Create fixture with missing Name tag on CloudFront, verify validator reports ALIGN-005 finding.

### SC-004: Documentation (GAP-004)

Document AWS state migration requirements in `docs/iam-migration.md`.

**Artifact**: Migration guide explaining how to update pre-existing AWS resources after naming convention changes.

---

## Operational Fixes Required

### FIX-001: Update S3 State Bucket Policy Pattern

**File**: `infrastructure/terraform/ci-user-policy.tf`
**Change**: Update S3 resource patterns to match actual bucket naming:

```hcl
resources = [
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*",
  "arn:aws:s3:::sentiment-analyzer-terraform-state-*/*"
]
```

**Rationale**: The state bucket was created with legacy naming and renaming S3 buckets requires recreation. Safer to update policy.

---

### FIX-002: Rename AWS CI Users (Bootstrap Required)

**Current State**: CI user `sentiment-analyzer-preprod-deployer` (legacy naming)
**Target State**: CI user `preprod-sentiment-deployer` (new naming convention)

**Bootstrap Steps**:

1. Create new IAM user `preprod-sentiment-deployer` via AWS Console/CLI
2. Copy all policies from legacy user to new user
3. Update GitHub Actions secrets with new user credentials
4. Delete legacy user `sentiment-analyzer-preprod-deployer`

**Note**: This is a manual bootstrap operation. The Terraform cannot rename itself since the deployer executing the action is the user being renamed.

**Verification**: After bootstrap, IAM policy pattern `*-sentiment-deployer` will match the new user.

---

### FIX-003: Add Name Tags to CloudFront Resources

**File**: `modules/cloudfront/main.tf` (target repo)
**Change**: Ensure all CloudFront resources have `Name` tag matching `*-sentiment-*`:

```hcl
tags = {
  Name        = "${var.environment}-sentiment-dashboard"
  Environment = var.environment
}
```

---

## Scope

### In Scope

- Batch all IAM permission fixes into single PR
- Extend `IAMResourceAlignmentValidator` for gaps 1-3
- Create migration documentation
- Update methodology tests

### Out of Scope

- Renaming pre-existing AWS resources (manual bootstrap task)
- Adding AWS API-based validation (would require credentials in CI)
- Changes to other validators (SQS, SNS, Lambda) unless directly related

---

## Dependencies

- 085-iam-validator-refactor (completed) - Foundation for allowlist loading
- 090-security-first-burndown (target repo) - Introduced naming convention changes

---

## Clarification Decisions

### Q1: CI User Fix Strategy

**Decision**: Rename AWS users
**Rationale**: Manually rename CI users in AWS to match new naming convention. Requires bootstrap step but cleaner long-term. No dual patterns in IAM policies.

### Q2: Tag Validation Scope

**Decision**: CloudFront + FIS + Logs (comprehensive)
**Rationale**: Fix all tag-conditioned resources in single PR: CloudFront, FIS execution role, and Log Groups.

### Q3: Validator Design

**Decision**: Extend existing IAMResourceAlignmentValidator
**Rationale**: Add backend.hcl parsing to existing validator. Keeps related validation logic together.

### Q4: Implementation Priority

**Decision**: Both together
**Rationale**: Implement operational fixes + validator gaps in single comprehensive PR. Ensures methodology gap doesn't recur.

---

## File Impact Analysis

### Template Repo (terraform-gsk-template)

| File                                        | Change Type | Purpose                                           |
| ------------------------------------------- | ----------- | ------------------------------------------------- |
| `src/validators/iam_resource_alignment.py`  | Modify      | Add backend.hcl parsing, tag condition validation |
| `tests/unit/test_iam_resource_alignment.py` | Modify      | Add tests for new rules                           |
| `tests/fixtures/validators/`                | Add         | New fixtures for backend/tag mismatches           |
| `docs/iam-migration.md`                     | Add         | Migration guide documentation                     |

### Target Repo (sentiment-analyzer-gsk)

| File                                         | Change Type | Purpose                        |
| -------------------------------------------- | ----------- | ------------------------------ |
| `infrastructure/terraform/ci-user-policy.tf` | Modify      | Fix S3 and IAM user patterns   |
| `modules/cloudfront/main.tf`                 | Modify      | Add Name tag                   |
| `modules/chaos/main.tf`                      | Modify      | Add Name tags to FIS resources |

---

## References

- Pipeline Failure Run: Deploy Pipeline on main branch
- Recent Target Commits: `c603bdd` (feat 090: Security-first drift burndown)
- Validator Source: `src/validators/iam_resource_alignment.py:393-475`
- IAM Policy: `infrastructure/terraform/ci-user-policy.tf`
