# Tasks: Fix Terraform State Bucket Permission Mismatch

**Input**: Design documents from `/specs/018-tfstate-bucket-fix/`
**Prerequisites**: plan.md (complete), spec.md (complete), research.md (complete)

**Tests**: Not required - infrastructure configuration fix validated by pipeline execution

**Organization**: Tasks grouped by user story for independent implementation and validation

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify current state and prepare for changes

- [ ] T001 Verify current branch is `018-tfstate-bucket-fix` and synced with main
- [ ] T002 Search for all `tfstate` occurrences to confirm scope in repository root

---

## Phase 2: User Story 1 - CI/CD Pipeline Successful Deployment (Priority: P1) 🎯 MVP

**Goal**: Unblock preprod pipeline by fixing the preprod-deployer-policy.json TerraformStateAccess pattern

**Independent Test**: Merge to main and verify "Terraform Init (Preprod)" step completes successfully

### Implementation for User Story 1

- [ ] T003 [US1] Update TerraformStateAccess resource pattern from `sentiment-analyzer-tfstate-*` to `sentiment-analyzer-terraform-state-*` in infrastructure/iam-policies/preprod-deployer-policy.json
- [ ] T004 [US1] Verify preprod object path still uses `/preprod/*` suffix for environment isolation in infrastructure/iam-policies/preprod-deployer-policy.json

**Checkpoint**: Preprod pipeline should now complete Terraform Init successfully

---

## Phase 3: User Story 2 - Consistent IAM Policies Across Environments (Priority: P2)

**Goal**: Update all remaining deployer policies and CI user policy to use consistent patterns

**Independent Test**: Review all policy files and confirm TerraformStateAccess patterns match `sentiment-analyzer-terraform-state-*`

### Implementation for User Story 2

- [ ] T005 [P] [US2] Update TerraformStateAccess resource pattern from `sentiment-analyzer-tfstate-*` to `sentiment-analyzer-terraform-state-*` in infrastructure/iam-policies/prod-deployer-policy.json
- [ ] T006 [P] [US2] Update TerraformStateAccess resource pattern from `sentiment-analyzer-tfstate-*` to `sentiment-analyzer-terraform-state-*` in docs/iam-policies/dev-deployer-policy.json
- [ ] T007 [P] [US2] Update TerraformState resources pattern from `*-sentiment-tfstate-*` to `*-sentiment-terraform-state-*` in infrastructure/terraform/ci-user-policy.tf
- [ ] T008 [US2] Verify each policy maintains environment-scoped object paths (`/dev/*`, `/preprod/*`, `/prod/*`)

**Checkpoint**: All deployer policies and CI user policy now use standardized pattern

---

## Phase 4: User Story 3 - Standardized Naming Convention (Priority: P2)

**Goal**: Update backend config, bootstrap Terraform, and all documentation to eliminate old pattern

**Independent Test**: Search for `tfstate` in codebase - should return zero matches in policies, configs, and code files

### Implementation for User Story 3

#### Backend and Bootstrap Updates

- [ ] T009 [P] [US3] Update bucket value from `sentiment-analyzer-tfstate-218795110243` to `sentiment-analyzer-terraform-state-218795110243` in infrastructure/terraform/backend-dev.hcl
- [ ] T010 [P] [US3] Update bucket pattern from `sentiment-analyzer-tfstate-${account}` to `sentiment-analyzer-terraform-state-${account}` in infrastructure/terraform/bootstrap/main.tf

#### Documentation Updates

- [ ] T011 [P] [US3] Replace all `tfstate` references with `terraform-state` in infrastructure/docs/CREDENTIAL_SEPARATION_SETUP.md
- [ ] T012 [P] [US3] Replace `tfstate` pattern reference with `terraform-state` in infrastructure/docs/TERRAFORM_RESOURCE_VERIFICATION.md
- [ ] T013 [P] [US3] Replace `tfstate` references in diagram and pattern sections in docs/TERRAFORM_DEPLOYMENT_FLOW.md
- [ ] T014 [P] [US3] Replace `tfstate` references in policy examples in docs/PROMOTION_WORKFLOW_DESIGN.md
- [ ] T015 [P] [US3] Replace bucket reference from `tfstate` to `terraform-state` in docs/GET_DASHBOARD_RUNNING.md
- [ ] T016 [P] [US3] Replace state file path references from `tfstate` to `terraform-state` in docs/PRODUCTION_PREFLIGHT_CHECKLIST.md
- [ ] T017 [P] [US3] Replace bucket pattern reference from `tfstate` to `terraform-state` in CLAUDE.md

**Checkpoint**: Zero occurrences of old `tfstate` pattern remain in codebase (excluding this spec documentation)

---

## Phase 5: Validation & Commit

**Purpose**: Final verification and commit

- [ ] T018 Search for remaining `tfstate` occurrences - should only appear in specs/018-tfstate-bucket-fix/ documentation
- [ ] T019 Run `make validate` to ensure no linting or formatting issues
- [ ] T020 Commit changes with GPG signature to feature branch
- [ ] T021 Push to remote and create PR
- [ ] T022 Verify pipeline passes "Terraform Init (Preprod)" step

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - start immediately
- **Phase 2 (US1)**: Depends on Phase 1 - CRITICAL for unblocking pipeline
- **Phase 3 (US2)**: Can run in parallel with Phase 2 (different files)
- **Phase 4 (US3)**: Can run in parallel with Phases 2 & 3 (different files)
- **Phase 5 (Validation)**: Depends on all previous phases

### User Story Independence

- **US1**: Can complete and validate independently (fixes blocking issue)
- **US2**: Can complete and validate independently (consistency across envs)
- **US3**: Can complete and validate independently (naming standardization)

All user stories work on different files - maximum parallelization possible.

---

## Parallel Opportunities

### Maximum Parallelization (All P-marked tasks)

```text
# All policy updates can run in parallel (different files):
T005 [P] [US2] prod-deployer-policy.json
T006 [P] [US2] dev-deployer-policy.json
T007 [P] [US2] ci-user-policy.tf

# All config updates can run in parallel (different files):
T009 [P] [US3] backend-dev.hcl
T010 [P] [US3] bootstrap/main.tf

# All documentation updates can run in parallel (different files):
T011-T017 [P] [US3] All documentation files
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: User Story 1 (preprod-deployer-policy.json only)
3. **STOP and VALIDATE**: Push, create PR, verify pipeline passes
4. If urgent: Merge MVP to unblock pipeline immediately

### Full Implementation

1. Complete all phases (can parallelize T005-T017)
2. Single commit with all changes
3. Push and verify pipeline

### Recommended Approach

Given this is a pipeline-blocking issue:
1. **Quick fix**: T001-T004 only, push immediately to unblock
2. **Follow-up**: T005-T022 for full standardization

---

## Notes

- All [P] tasks can run in parallel (different files)
- No tests needed - validated by pipeline execution
- Commit with GPG signature required
- Feature branch: `018-tfstate-bucket-fix`
- Success = Pipeline completes "Terraform Init (Preprod)" without AccessDenied
