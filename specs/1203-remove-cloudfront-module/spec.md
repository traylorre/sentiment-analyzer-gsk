# Feature Specification: Remove CloudFront Terraform Module

**Feature Branch**: `1203-remove-cloudfront-module`
**Created**: 2026-01-18
**Status**: Draft
**Input**: User description: "Remove CloudFront Terraform module completely. Delete modules/cloudfront/ directory. Remove all references in main.tf, variables.tf, outputs.tf, and ci-user-policy.tf. CloudFront is vestigial - Amplify serves frontend directly."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Infrastructure Engineer Removes Unused Infrastructure (Priority: P1)

An infrastructure engineer needs to remove the vestigial CloudFront infrastructure that is no longer serving any purpose. The CloudFront module was originally created to serve the frontend via S3, but the architecture has evolved to use Amplify for frontend hosting. Keeping this unused infrastructure creates confusion, maintenance burden, and unnecessary cost.

**Why this priority**: Removing unused infrastructure is foundational - it eliminates cost, confusion, and maintenance burden. All other cleanup tasks (tfvars, workflows, tests, docs) depend on this core removal.

**Independent Test**: Can be tested by running `terraform plan` after removal and verifying only CloudFront resources are marked for destruction, with no errors from missing references.

**Acceptance Scenarios**:

1. **Given** the CloudFront module exists in the infrastructure, **When** the engineer deletes the module directory and all references, **Then** running `terraform plan` shows only CloudFront-related resources scheduled for destruction.

2. **Given** the CloudFront module has been removed, **When** the engineer runs `terraform validate`, **Then** the configuration passes validation with no errors about missing modules or outputs.

3. **Given** the CloudFront module references have been removed from CI user policy, **When** the CI pipeline runs, **Then** it no longer requests CloudFront-related permissions.

---

### User Story 2 - Developer Reviews Clean Codebase (Priority: P2)

A developer reviewing the codebase (including potential interviewers) should see a clean, coherent architecture without vestigial artifacts that contradict the actual deployed architecture.

**Why this priority**: Code cleanliness and professional presentation matter for credibility, but functionality (P1) must come first.

**Independent Test**: Can be tested by searching for "cloudfront" in the terraform directory and finding zero matches.

**Acceptance Scenarios**:

1. **Given** the CloudFront module has been removed, **When** a developer searches for "cloudfront" in the infrastructure/terraform directory, **Then** they find zero matches.

2. **Given** the cleanup is complete, **When** a developer reads main.tf, **Then** they see no commented-out code, no "legacy" labels, and no references to CloudFront.

---

### Edge Cases

- What happens if other modules depend on CloudFront outputs?
  - All dependencies must be identified and removed before module deletion.
- How does the system handle existing CloudFront resources in AWS?
  - Terraform will mark resources for destruction on next apply. Actual destruction happens separately.
- What happens if the module directory has uncommitted changes?
  - Changes should be committed or discarded before deletion to avoid losing work.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The `infrastructure/terraform/modules/cloudfront/` directory MUST be completely deleted.
- **FR-002**: All `module "cloudfront"` references MUST be removed from `main.tf`.
- **FR-003**: All CloudFront-related variables MUST be removed from `variables.tf`.
- **FR-004**: All CloudFront-related outputs MUST be removed from root `main.tf` or `outputs.tf`.
- **FR-005**: All CloudFront IAM permissions MUST be removed from `ci-user-policy.tf`.
- **FR-006**: No references to `module.cloudfront.*` outputs MUST remain in any Terraform file.
- **FR-007**: The infrastructure MUST pass `terraform validate` after all changes.
- **FR-008**: No "cloudfront" string matches MUST remain in the infrastructure/terraform directory (excluding state files).

### Key Entities

- **CloudFront Module**: The Terraform module being removed, located at `modules/cloudfront/`.
- **Module References**: Places where `module.cloudfront` is called or its outputs are used.
- **CI User Policy**: IAM policy granting permissions to the CI/CD pipeline, which may include CloudFront permissions.
- **CloudFront Variables**: Input variables related to CloudFront configuration (custom domain, certificate ARN, etc.).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero files remain in the `modules/cloudfront/` directory (directory deleted entirely).
- **SC-002**: Zero grep matches for "cloudfront" in `infrastructure/terraform/` (excluding .terraform/).
- **SC-003**: `terraform validate` passes with exit code 0 after all changes.
- **SC-004**: `terraform plan` shows only CloudFront resource destruction, no errors or warnings about missing references.

## Assumptions

- CloudFront resources currently exist in AWS and will be marked for destruction (actual destruction is a separate operation).
- No other modules or configurations depend on CloudFront outputs.
- The S3 bucket created by the CloudFront module (dashboard assets) is also being removed.
- This change will require a `terraform apply` to actually destroy AWS resources.

## Out of Scope

- Actually running `terraform apply` to destroy AWS resources (this feature is about code cleanup).
- Removing CloudFront references from non-Terraform files (workflows, tests, docs - those are separate features).
- Removing CloudFront URLs from tfvars files (that is Feature 3 in the workplan).
- Cost analysis of the removal (CloudFront is already established as vestigial).

## Dependencies

- Must be coordinated with Feature 3 (tfvars cleanup), Feature 4 (workflow cleanup), Feature 5 (app code cleanup), Feature 6 (test cleanup), and Feature 7 (diagram updates).
- The actual `terraform apply` should be done carefully after verifying the plan shows expected changes.
