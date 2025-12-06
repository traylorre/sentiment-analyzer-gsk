# Feature Specification: Fix Terraform State Bucket Permission Mismatch

**Feature Branch**: `018-tfstate-bucket-fix`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "Fix pipeline unblocking - Terraform S3 state bucket permission mismatch causing preprod deployment failures"

## Clarifications

### Session 2025-12-06

- Q: Should the CI user policy (ci-user-policy.tf) be included in this fix if it also contains the incorrect terraform state bucket pattern? → A: Yes, include CI user policy fix if pattern mismatch exists
- Q: Should we add the new pattern for backward compatibility or migrate all old patterns to the new standard? → A: Migrate all old patterns to the new standardized pattern `sentiment-analyzer-terraform-state-*`
- Q: Do we need to maintain dev environment backward compatibility? → A: No, dev compatibility not required. Pipeline only verifies integration tests pass and Terraform can deploy. Clean replacement is acceptable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI/CD Pipeline Successful Deployment (Priority: P1)

As a developer pushing changes to the main branch, I want the preprod deployment pipeline to successfully complete Terraform initialization so that my changes are deployed to the preprod environment without manual intervention.

**Why this priority**: This is a blocking issue that prevents all deployments to preprod. No features can be released until this is resolved. Every merge to main currently fails at the Terraform Init step.

**Independent Test**: Can be fully tested by triggering a pipeline run and verifying Terraform Init (Preprod) step completes successfully, delivering immediate unblocking of the CI/CD pipeline.

**Acceptance Scenarios**:

1. **Given** a merge to main branch, **When** the pipeline runs the "Terraform Init (Preprod)" step, **Then** Terraform successfully initializes and connects to the S3 state backend without AccessDenied errors
2. **Given** the preprod-deployer IAM user, **When** it attempts s3:ListBucket on the terraform state bucket, **Then** the operation succeeds due to matching resource patterns in the policy
3. **Given** a successful Terraform init, **When** the pipeline continues, **Then** the full deployment to preprod completes successfully

---

### User Story 2 - Consistent IAM Policies Across Environments (Priority: P2)

As a platform engineer, I want all environment-specific deployer policies to use consistent bucket naming patterns so that similar permission mismatches don't occur in other environments.

**Why this priority**: Prevents future pipeline failures in dev and prod environments. While only preprod is currently failing, the same pattern mismatch likely exists in other policy files.

**Independent Test**: Can be verified by reviewing all deployer policy files and confirming the Terraform state bucket patterns match the actual bucket naming convention.

**Acceptance Scenarios**:

1. **Given** the dev-deployer-policy.json file, **When** reviewed for Terraform state access, **Then** the S3 resource pattern matches the actual bucket naming convention
2. **Given** the prod-deployer-policy.json file, **When** reviewed for Terraform state access, **Then** the S3 resource pattern matches the actual bucket naming convention

---

### User Story 3 - Standardized Naming Convention (Priority: P2)

As a platform engineer, I want all Terraform state bucket references to use a single standardized naming pattern so that future maintenance is simplified and naming inconsistencies are eliminated.

**Why this priority**: Eliminates technical debt from having two different naming conventions. Prevents future confusion and potential permission mismatches.

**Independent Test**: Can be verified by searching the codebase for the old pattern and confirming zero occurrences remain.

**Acceptance Scenarios**:

1. **Given** a search for `tfstate` in the codebase, **When** executed after this fix, **Then** no IAM policies, backend configs, or Terraform files contain the old pattern
2. **Given** the bootstrap Terraform, **When** creating new state buckets, **Then** they use the `terraform-state` naming convention

---

### Edge Cases

- What happens if the bucket name changes in the future? (Assumption: bucket naming convention is stable; policy patterns use wildcards for account ID)
- How does the system handle state bucket access in new environments? (Assumption: new environments follow the same naming convention)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The preprod-deployer-policy.json MUST grant s3:ListBucket permission on buckets matching `sentiment-analyzer-terraform-state-*`
- **FR-002**: The preprod-deployer-policy.json MUST grant s3:GetObject, s3:PutObject, s3:DeleteObject permissions on objects in buckets matching `sentiment-analyzer-terraform-state-*/preprod/*`
- **FR-003**: The dev-deployer-policy.json MUST grant equivalent Terraform state access permissions with pattern `sentiment-analyzer-terraform-state-*`
- **FR-004**: The prod-deployer-policy.json MUST grant equivalent Terraform state access permissions with pattern `sentiment-analyzer-terraform-state-*`
- **FR-005**: All deployer policies MUST maintain the environment-scoped object paths (e.g., `/preprod/*`, `/dev/*`, `/prod/*`) to prevent cross-environment access
- **FR-006**: The ci-user-policy.tf MUST be updated with the correct bucket pattern `sentiment-analyzer-terraform-state-*` if it contains the incorrect pattern
- **FR-007**: The dev backend configuration (backend-dev.hcl) MUST be migrated to use `sentiment-analyzer-terraform-state-*` pattern
- **FR-008**: The bootstrap Terraform (bootstrap/main.tf) MUST be updated to create buckets with `sentiment-analyzer-terraform-state-*` pattern
- **FR-009**: All documentation referencing the old `tfstate` pattern MUST be updated to use the standardized `terraform-state` pattern

### Key Entities

- **Deployer Policy**: Environment-specific IAM policy JSON files that define what AWS actions deployer users can perform
- **Terraform State Bucket**: S3 bucket (`sentiment-analyzer-terraform-state-{account-id}`) storing Terraform state files, organized by environment subdirectories
- **Pipeline User**: IAM user (e.g., `sentiment-analyzer-preprod-deployer`) that executes Terraform operations during CI/CD deployments

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Preprod deployment pipeline completes successfully within normal execution time (no Terraform Init failures)
- **SC-002**: All three environment deployer policies (dev, preprod, prod) use the standardized `terraform-state` bucket pattern
- **SC-003**: No AccessDenied errors related to s3:ListBucket on Terraform state buckets in any environment
- **SC-004**: Future deployments to preprod succeed without IAM permission-related failures
- **SC-005**: Zero occurrences of the old `tfstate` pattern remain in IAM policies and Terraform configs (excluding comments documenting the migration)
- **SC-006**: All documentation references use the standardized `terraform-state` pattern

## Assumptions

- The actual Terraform state bucket follows the naming pattern `sentiment-analyzer-terraform-state-{account-id}`
- The original policy used an incorrect pattern `sentiment-analyzer-tfstate-*` which doesn't match the actual bucket name
- Environment isolation is maintained through object path prefixes (e.g., `/preprod/*`) rather than separate buckets
- The CI user policy (ci-user-policy.tf) will be included in this fix if it contains the incorrect bucket pattern (confirmed via clarification)

## Out of Scope

- KMS wildcard remediation (IAM-006) - tracked separately
- Property test failures (PROP-001) - tracked separately
- Methodology infrastructure for target repo (spec coherence, bidirectional, mutation) - not required for target repos per Amendment 1.7
