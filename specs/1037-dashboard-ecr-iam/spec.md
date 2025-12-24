# Feature Specification: Dashboard ECR IAM Policy Fix

**Feature Branch**: `1037-dashboard-ecr-iam`
**Created**: 2025-12-23
**Status**: Draft
**Input**: Fix ECR IAM Policy for Dashboard Lambda - Add dashboard-lambda ECR repository pattern to CI deploy policy. The preprod-dashboard-lambda and prod-dashboard-lambda repositories are not covered by current IAM policy patterns (*-sentiment-*, *-sse-streaming-*, *-analysis-*). Add *-dashboard-lambda* pattern to ECR and ECRImages statements in ci-user-policy.tf. SUCCESS: Deploy pipeline successfully pushes Dashboard Lambda container image to ECR.

## Problem Statement

The Deploy Pipeline fails with `403 Forbidden` when pushing the Dashboard Lambda container image to ECR. The error occurs at the "Build and Push Dashboard Lambda Image" step:

```
ERROR: failed to push 218795110243.dkr.ecr.us-east-1.amazonaws.com/preprod-dashboard-lambda:latest:
unexpected status from HEAD request...: 403 Forbidden
```

SSE and Analysis Lambda images push successfully - only Dashboard fails.

## Root Cause Analysis

The IAM policy `ci-user-policy.tf` has ECR resource patterns that don't include the Dashboard Lambda repository naming convention.

**Current ECR patterns** (lines 298-302, 321-325):
- `*-sentiment-*`
- `*-sse-streaming-*`
- `*-analysis-*`

**Dashboard Lambda repository names**:
- `preprod-dashboard-lambda`
- `prod-dashboard-lambda`

The `*-dashboard-lambda*` pattern is missing from the IAM policy.

## User Scenarios & Testing

### User Story 1 - Deploy Dashboard Lambda Container (Priority: P1)

As a CI/CD pipeline, I need to push Dashboard Lambda container images to ECR so that the deploy workflow can complete successfully and update the Lambda function.

**Why this priority**: This is a blocking issue preventing any deployment of the Dashboard Lambda to preprod and production. Without this fix, feature 1036 (container deployment migration) cannot be fully deployed.

**Independent Test**: Run the Deploy Pipeline on main branch. The "Build Dashboard Lambda Image (Preprod)" job should succeed with all steps completing, including the docker push.

**Acceptance Scenarios**:

1. **Given** a commit merged to main, **When** the Deploy Pipeline runs, **Then** the "Build Dashboard Lambda Image (Preprod)" job succeeds and the image is pushed to ECR.
2. **Given** the preprod deploy succeeds, **When** the pipeline continues to production, **Then** the "Build Dashboard Lambda Image (Production)" job also succeeds.

### Edge Cases

- The pattern `*-dashboard-lambda*` should match both `preprod-dashboard-lambda` and `prod-dashboard-lambda` repositories
- No other existing repositories should be inadvertently granted access (pattern is specific to dashboard-lambda)

## Requirements

### Functional Requirements

- **FR-001**: IAM policy MUST grant ECR repository management permissions for `*-dashboard-lambda*` pattern
- **FR-002**: IAM policy MUST grant ECR image push permissions (BatchCheckLayerAvailability, InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, PutImage) for `*-dashboard-lambda*` pattern
- **FR-003**: Changes MUST be limited to adding the new pattern - no modification to existing patterns or permissions
- **FR-004**: The fix MUST follow the existing pattern structure in ci-user-policy.tf (add to both ECR and ECRImages statements)

### Key Entities

- **ECR Repository**: Container registry storing Lambda container images. Named with `{env}-dashboard-lambda` pattern.
- **IAM Policy**: CIDeployCore policy controlling CI/CD user permissions for ECR operations.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Deploy Pipeline "Build Dashboard Lambda Image (Preprod)" job completes successfully
- **SC-002**: Deploy Pipeline "Build Dashboard Lambda Image (Production)" job completes successfully
- **SC-003**: `terraform plan` shows only the addition of new ECR resource patterns, no unrelated changes
- **SC-004**: Existing SSE and Analysis Lambda ECR operations remain unaffected

## Out of Scope

- Creating new ECR repositories (repositories already exist)
- Modifying Dashboard Lambda code or Dockerfile
- Changing the repository naming convention
- Modifying permissions for other AWS services

## Risk Assessment

- **Low Risk**: Only adding a new resource pattern to existing policy statements
- **Rollback**: Remove the new pattern from the policy
- **Testing**: Pipeline success validates the fix
