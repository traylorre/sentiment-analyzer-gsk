# Feature Specification: Pipeline Blockers Resolution

**Feature Branch**: `041-pipeline-blockers`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "Resolve remaining pipeline blockers: import orphan ECR repo and fix KMS key policy"

## Problem Analysis

### Root Cause Investigation

The preprod deployment pipeline is failing at Terraform Apply due to two issues discovered during IAM bootstrap (spec 019):

**Issue 1: Orphan ECR Repository**
- During a previous failed terraform apply, the ECR repository `preprod-sse-streaming-lambda` was created
- The apply then failed on a different resource (KMS key)
- Terraform state does not contain the ECR repo because the apply was rolled back
- Subsequent applies fail with `RepositoryAlreadyExistsException`

**Issue 2: KMS Key Policy**
- Error: `MalformedPolicyDocumentException: The new key policy will not allow you to update the key policy in the future`
- The KMS key policy only grants `kms:*` to root account
- AWS requires that the creating principal (CI deployer) can also manage the key
- Without explicit admin permissions for the deployer, AWS rejects the key creation

## User Scenarios & Testing

### User Story 1 - ECR Repository Import (Priority: P1)

As a developer, I need the pipeline to successfully create or manage the SSE streaming Lambda ECR repository so that container-based Lambda deployments work.

**Why this priority**: Direct blocker - terraform apply cannot proceed until ECR state is reconciled.

**Independent Test**: Run `terraform plan` and verify no ECR repository errors appear.

**Acceptance Scenarios**:

1. **Given** orphan ECR repo `preprod-sse-streaming-lambda` exists in AWS but not in terraform state, **When** terraform import is run, **Then** terraform state includes the ECR repo and plan shows no changes
2. **Given** ECR repo is in terraform state, **When** pipeline runs terraform apply, **Then** no `RepositoryAlreadyExistsException` error occurs

---

### User Story 2 - KMS Key Policy Fix (Priority: P1)

As a DevOps engineer, I need the KMS key policy to allow the CI deployer to manage the key so that key creation succeeds.

**Why this priority**: Direct blocker - terraform apply cannot create KMS key without this fix.

**Independent Test**: Run `terraform apply` targeting the KMS module and verify key is created successfully.

**Acceptance Scenarios**:

1. **Given** KMS key policy includes CI deployer admin permissions, **When** terraform creates KMS key, **Then** key is created without `MalformedPolicyDocumentException`
2. **Given** KMS key exists, **When** CI deployer attempts to update key policy, **Then** operation succeeds (key is manageable)

---

### User Story 3 - Pipeline Green (Priority: P1)

As a developer, I need the full preprod deployment pipeline to pass so that changes can be deployed to the preprod environment.

**Why this priority**: End goal - validates both fixes work together.

**Independent Test**: Trigger pipeline run on main branch and observe successful deployment to preprod.

**Acceptance Scenarios**:

1. **Given** ECR import and KMS fix are applied, **When** pipeline runs full terraform apply, **Then** all resources are created/updated successfully
2. **Given** successful terraform apply, **When** smoke tests run, **Then** preprod environment is accessible

---

### Edge Cases

- What if ECR repo has images that must be preserved? (Import preserves existing images)
- What if KMS key already exists in a previous failed state? (May need import or manual deletion)
- What if prod-deployer also needs KMS permissions? (Apply same pattern)

## Requirements

### Functional Requirements

- **FR-001**: Terraform state MUST include the `preprod-sse-streaming-lambda` ECR repository
- **FR-002**: KMS key policy MUST grant key administration permissions to CI deployer users
- **FR-003**: KMS key policy MUST retain root account access as fallback
- **FR-004**: Pipeline MUST complete terraform init, plan, and apply without permission errors
- **FR-005**: Solution MUST work for both preprod and prod deployer users

### Key Entities

- **ECR Repository**: `preprod-sse-streaming-lambda` - container image storage for SSE streaming Lambda
- **KMS Key**: Shared encryption key for sentiment analyzer secrets and data
- **CI Deployer Users**: `sentiment-analyzer-preprod-deployer`, `sentiment-analyzer-prod-deployer`

## Success Criteria

### Measurable Outcomes

- **SC-001**: Pipeline job "Terraform Apply (Preprod)" completes successfully within 10 minutes
- **SC-002**: No `RepositoryAlreadyExistsException` or `MalformedPolicyDocumentException` errors in pipeline logs
- **SC-003**: Preprod smoke tests pass after deployment
- **SC-004**: Future KMS key policy updates can be made by CI deployer without root intervention

## Assumptions

- The orphan ECR repository `preprod-sse-streaming-lambda` should be imported, not deleted and recreated
- CI deployer should have KMS key administration rights scoped to sentiment-analyzer keys only
- Root account access to KMS key should be preserved as a failsafe
- Terraform state in S3 is accessible (verified in spec 019)
