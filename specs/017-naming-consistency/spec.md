# Feature Specification: IAM and Resource Naming Consistency

**Feature Branch**: `017-naming-consistency`
**Created**: 2025-12-03
**Status**: Draft
**Input**: User description: "IAM and Resource Naming Consistency - Eliminate legacy naming, establish single pattern, add automated validation"

## Problem Statement

The project has repeated CI/CD failures due to mismatches between resource names and IAM policy ARN patterns. Two naming patterns exist:
- Legacy: `sentiment-analyzer-*`
- Current: `{env}-sentiment-*`

**Decision**: Eliminate ALL legacy naming. One pattern only: `{env}-sentiment-{service}`

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Developer Adds New Resource (Priority: P1)

A developer adds a new AWS resource. Validation ensures the name follows `{env}-sentiment-{service}` and IAM policies permit access.

**Why this priority**: Catches issues at development time before CI.

**Independent Test**: Add a resource with wrong name, verify validation fails with clear error.

**Acceptance Scenarios**:

1. **Given** a developer adds a Lambda named `sentiment-analyzer-foo`, **When** they run validation, **Then** it fails with "use {env}-sentiment-{service} pattern"
2. **Given** a developer adds a Lambda named `preprod-sentiment-newservice`, **When** they run validation, **Then** it passes
3. **Given** IAM policy lacks pattern for new resource, **When** validation runs, **Then** it reports which IAM statement needs the pattern

---

### User Story 2 - CI Validates Before Deploy (Priority: P1)

CI checks all resources match IAM patterns before Terraform apply.

**Why this priority**: Safety net - prevents deploy failures.

**Independent Test**: PR with misnamed resource fails CI with actionable message.

**Acceptance Scenarios**:

1. **Given** PR with correctly named resources, **When** CI runs, **Then** validation passes
2. **Given** PR with legacy-named resource, **When** CI runs, **Then** validation fails before apply

---

### User Story 3 - Migrate Legacy Resources (Priority: P2)

Existing `sentiment-analyzer-*` resources are renamed to `{env}-sentiment-*`.

**Why this priority**: Enables removal of legacy IAM patterns.

**Independent Test**: After migration, remove legacy patterns from IAM, deploy succeeds.

**Acceptance Scenarios**:

1. **Given** legacy resource exists, **When** migration runs, **Then** resource is renamed to new pattern
2. **Given** all resources migrated, **When** legacy IAM patterns removed, **Then** deploy succeeds

---

### Edge Cases

- Resources with state (DynamoDB, S3) need careful migration to avoid data loss
- Third-party integrations may require exception documentation

## Requirements *(mandatory)*

### Functional Requirements

**Single Naming Pattern**:
- **FR-001**: ALL resources MUST use pattern: `{env}-sentiment-{service}`
- **FR-002**: Valid environments: `preprod`, `prod`
- **FR-003**: Centralized variable MUST generate the prefix: `${var.environment}-sentiment`
- **FR-004**: NO new resources may use `sentiment-analyzer-*` pattern

**Automated Validation**:
- **FR-005**: `make check-iam-patterns` MUST verify all resources match IAM policies
- **FR-006**: Validation MUST fail if any resource uses legacy `sentiment-analyzer-*` pattern
- **FR-007**: Validation MUST run in CI before Terraform plan
- **FR-008**: Validation errors MUST include resource name, file location, and correct pattern

**IAM Policy Cleanup**:
- **FR-009**: After migration, IAM policies MUST only contain `*-sentiment-*` patterns
- **FR-010**: Remove all `sentiment-analyzer-*` patterns from IAM policies

**Documentation**:
- **FR-011**: CLAUDE.md MUST document the single naming pattern with examples
- **FR-012**: Documentation MUST explicitly forbid legacy pattern for new resources

### Key Entities

- **Resource Prefix**: `{env}-sentiment` (e.g., `preprod-sentiment`, `prod-sentiment`)
- **Full Resource Name**: `{env}-sentiment-{service}` (e.g., `preprod-sentiment-ingestion`)
- **IAM ARN Pattern**: `*-sentiment-*` (matches all environments)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero resources use `sentiment-analyzer-*` pattern after migration
- **SC-002**: Zero IAM patterns reference `sentiment-analyzer-*` after cleanup
- **SC-003**: Validation command completes in under 30 seconds
- **SC-004**: CI catches 100% of naming violations before deploy
- **SC-005**: Zero IAM permission failures post-implementation
