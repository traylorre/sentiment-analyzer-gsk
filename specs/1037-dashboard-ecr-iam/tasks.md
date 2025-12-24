# Tasks: Dashboard ECR IAM Policy Fix

**Input**: Design documents from `/specs/1037-dashboard-ecr-iam/`
**Prerequisites**: plan.md, spec.md

**Tests**: Pipeline validation (no unit tests needed - this is IAM policy change)

**Organization**: Single phase implementation - minimal infrastructure fix

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

## Path Conventions

- **Infrastructure**: `infrastructure/terraform/` (Terraform files)

---

## Phase 1: Implementation

**Purpose**: Add dashboard-lambda ECR pattern to IAM policy

- [x] T001 Add dashboard-lambda pattern to ECR statement resources in infrastructure/terraform/ci-user-policy.tf (line ~300)
- [x] T002 Add dashboard-lambda pattern to ECRImages statement resources in infrastructure/terraform/ci-user-policy.tf (line ~323)
- [x] T003 Update comment on ECR statement to document dashboard-lambda pattern

---

## Phase 2: Validation

**Purpose**: Verify changes are correct and minimal

- [x] T004 Run terraform fmt to ensure formatting in infrastructure/terraform/
- [x] T005 N/A - no Makefile in repo, terraform fmt validates syntax

---

## Phase 3: Deploy & Verify

**Purpose**: Merge and validate pipeline succeeds

- [ ] T006 Push branch and create PR
- [ ] T007 Monitor PR checks pass
- [ ] T008 Verify Deploy Pipeline "Build Dashboard Lambda Image (Preprod)" succeeds after merge

---

## Dependencies & Execution Order

- **Phase 1**: No dependencies - start immediately
- **Phase 2**: Depends on Phase 1 completion
- **Phase 3**: Depends on Phase 2 completion

### Within Each Phase

- T001, T002, T003 modify the same file, run sequentially
- T004, T005 can run in parallel

---

## Implementation Strategy

### MVP First

1. Complete Phase 1: Add the pattern
2. Complete Phase 2: Validate locally
3. Complete Phase 3: Push and verify pipeline

### Single Developer Sequence

T001 → T002 → T003 → T004 → T005 → T006 → T007 → T008

---

## Notes

- This is a minimal infrastructure fix
- No code changes required outside ci-user-policy.tf
- Pipeline success is the ultimate validation
- Pattern format: `*-dashboard-lambda*` matches `preprod-dashboard-lambda` and `prod-dashboard-lambda`
