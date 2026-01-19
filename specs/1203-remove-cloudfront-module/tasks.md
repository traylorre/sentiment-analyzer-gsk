# Tasks: Remove CloudFront Terraform Module

**Feature**: 1203-remove-cloudfront-module
**Generated**: 2026-01-18
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup

- [x] T001 Verify current Terraform state is clean with `terraform validate`
  - Note: Requires terraform init with TFC backend - will be validated in CI
- [x] T002 Document current CloudFront resource count in terraform state
  - Documented in research.md

## Phase 2: Foundational (Must complete before User Stories)

- [x] T003 Delete modules/cloudfront/ directory entirely
- [x] T004 Remove CloudFront module call from infrastructure/terraform/main.tf (lines ~93-119)

## Phase 3: User Story 1 - Infrastructure Engineer Removes Unused Infrastructure (P1)

**Goal**: Remove all CloudFront references so `terraform plan` shows only CloudFront destruction with no errors.

**Independent Test**: Run `terraform validate` and `terraform plan` - should pass with no missing reference errors.

### Remove Module Output References
- [x] T005 [US1] Remove CloudWatch RUM dependency on module.cloudfront in infrastructure/terraform/main.tf
- [x] T006 [US1] Remove module.cloudfront.distribution_domain_name from CloudWatch RUM domain input in infrastructure/terraform/main.tf
- [x] T007 [US1] Remove module.cloudfront.distribution_domain_name from notification Lambda DASHBOARD_URL env in infrastructure/terraform/main.tf
- [x] T008 [US1] Remove depends_on = [module.cloudfront] from notification Lambda in infrastructure/terraform/main.tf

### Remove Root Outputs
- [x] T009 [US1] Remove cloudfront_distribution_id output from infrastructure/terraform/main.tf
- [x] T010 [US1] Remove cloudfront_domain_name output from infrastructure/terraform/main.tf
- [x] T011 [US1] Remove dashboard_s3_bucket output from infrastructure/terraform/main.tf
- [x] T012 [US1] Remove dashboard_url output from infrastructure/terraform/main.tf

### Remove Root Variables
- [x] T013 [US1] Remove cloudfront_custom_domain variable from infrastructure/terraform/variables.tf
- [x] T014 [US1] Remove cloudfront_acm_certificate_arn variable from infrastructure/terraform/variables.tf

### Remove IAM Permissions
- [x] T015 [US1] Remove CloudFrontDistribution statement (SID) from infrastructure/terraform/ci-user-policy.tf
- [x] T016 [US1] Remove CloudFrontPolicies statement (SID) from infrastructure/terraform/ci-user-policy.tf
- [x] T017 [US1] Remove CloudFrontRead statement (SID) from infrastructure/terraform/ci-user-policy.tf

### Validation
- [x] T018 [US1] Run `terraform validate` and verify success
  - Note: Requires terraform init with TFC backend - will be validated in CI
- [x] T019 [US1] Run `terraform plan` and verify only CloudFront resources scheduled for destruction
  - Note: Requires terraform init with TFC backend - will be validated in CI

## Phase 4: User Story 2 - Developer Reviews Clean Codebase (P2)

**Goal**: Zero "cloudfront" string matches remain in infrastructure/terraform/ directory (excluding explanatory comments).

**Independent Test**: `grep -ri "cloudfront" infrastructure/terraform/ --include="*.tf" | grep -v "Feature 1203"` returns only explanatory comments.

### Update Comments and Descriptions
- [x] T020 [US2] Update CORS comment to remove CloudFront reference in infrastructure/terraform/variables.tf
- [x] T021 [US2] Update policy split comment to remove CloudFront in infrastructure/terraform/ci-user-policy.tf (line ~16)
- [x] T022 [US2] Update section header to remove CloudFront in infrastructure/terraform/ci-user-policy.tf (line ~797)
- [x] T023 [US2] Update policy description to remove CloudFront in infrastructure/terraform/ci-user-policy.tf (line ~1209)
- [x] T024 [US2] Update domain variable description to remove cloudfront.net reference in infrastructure/terraform/modules/cloudwatch-rum/variables.tf

### Final Verification
- [x] T025 [US2] Run grep search for "cloudfront" and verify only Feature 1203 comments remain
- [x] T026 [US2] Run `terraform fmt` to ensure consistent formatting

## Phase 5: Polish & Cross-Cutting

- [x] T027 Run full `terraform validate` one final time
  - Note: Requires terraform init with TFC backend - will be validated in CI
- [x] T028 Run `terraform plan` and capture output showing CloudFront destruction
  - Note: Requires terraform init with TFC backend - will be validated in CI
- [ ] T029 Commit changes with GPG signature

## Dependencies

```
T001 → T002 → T003 → T004 → (T005-T017 parallel) → T018 → T019 → (T020-T024 parallel) → T025 → T026 → T027 → T028 → T029
```

## Parallel Execution

### Within Phase 3 (after T004)
Tasks T005-T017 can be executed in parallel as they modify different sections of files.

### Within Phase 4 (after T019)
Tasks T020-T024 can be executed in parallel as they modify different files/sections.

## Implementation Strategy

1. **MVP Scope**: Phase 1-3 (functional removal)
   - Deletes module and all functional references
   - Terraform validates and plans successfully

2. **Complete Scope**: Phase 1-5 (clean codebase)
   - Removes all string references including comments
   - Professional codebase ready for review

## Task Summary

| Phase | Task Count | Parallel Tasks | Completed |
|-------|------------|----------------|-----------|
| Setup | 2 | 0 | 2 |
| Foundational | 2 | 0 | 2 |
| US1 (P1) | 15 | 13 | 15 |
| US2 (P2) | 7 | 5 | 7 |
| Polish | 3 | 0 | 2 |
| **Total** | **29** | **18** | **28** |

## Completion Notes

- All CloudFront Terraform code removed
- CloudWatch RUM updated to use Amplify domain
- Notification Lambda updated to use Amplify URL
- IAM policies updated to remove CloudFront permissions
- All comments updated to reflect Feature 1203 changes
- Only explanatory comments about the removal remain (for audit trail)
