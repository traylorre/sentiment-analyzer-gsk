# Tasks: Pipeline Blockers Resolution

**Input**: Design documents from `/specs/041-pipeline-blockers/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: No tests requested - infrastructure-only changes validated via terraform plan/apply.

**Organization**: Tasks are grouped by user story to enable independent implementation and validation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths and commands in descriptions

## Path Conventions

Infrastructure-as-Code project structure:
```text
infrastructure/terraform/
├── main.tf                     # ECR resource
├── modules/kms/main.tf         # KMS key resource
└── ci-user-policy.tf           # CI deployer reference
```

---

## Phase 1: Setup (Bootstrap Environment)

**Purpose**: Prepare terraform environment with correct backend and credentials

- [x] T001 Verify AWS credentials are for `sentiment-analyzer-dev` user via `aws sts get-caller-identity`
- [x] T002 Navigate to terraform directory: `cd infrastructure/terraform`
- [x] T003 Initialize terraform with preprod backend: `terraform init -backend-config=backend-preprod.hcl -backend-config="region=us-east-1" -reconfigure`

**Checkpoint**: Terraform initialized with preprod state backend

---

## Phase 2: User Story 1 - ECR Repository Import (Priority: P1) 🎯 MVP

**Goal**: Import orphan ECR repository into terraform state to resolve `RepositoryAlreadyExistsException`

**Independent Test**: Run `terraform plan` and verify no ECR repository errors appear

### Implementation for User Story 1

- [x] T004 [US1] Check if ECR repo exists in AWS: `aws ecr describe-repositories --repository-names preprod-sse-streaming-lambda`
- [x] T005 [US1] Import ECR repo into terraform state: `terraform import aws_ecr_repository.sse_streaming preprod-sse-streaming-lambda`
- [x] T006 [US1] Verify import successful: `terraform plan` shows no changes to ECR resource

**Checkpoint**: ECR repository in terraform state, `terraform plan` clean for ECR

---

## Phase 3: User Story 2 - KMS Key Policy Fix (Priority: P1)

**Goal**: Add CI deployer admin permissions to KMS key policy to allow key creation

**Independent Test**: Run `terraform apply` targeting KMS module and verify key creation succeeds

### Implementation for User Story 2

- [x] T007 [US2] Read current KMS key policy in `infrastructure/terraform/modules/kms/main.tf`
- [x] T008 [US2] Add CIDeployerKeyAdmin statement to policy in `infrastructure/terraform/modules/kms/main.tf:31-75`
- [x] T009 [US2] Validate terraform syntax: `terraform validate`
- [x] T010 [US2] Preview KMS changes: `terraform plan -target=module.kms`

**Checkpoint**: KMS key policy includes CI deployer admin permissions, plan shows expected changes

---

## Phase 4: User Story 3 - Pipeline Green (Priority: P1)

**Goal**: Validate full pipeline passes with both fixes applied

**Independent Test**: Push to branch, create PR, merge to main, observe successful preprod deployment

### Implementation for User Story 3

- [ ] T011 [US3] Create feature branch: `git checkout -b 041-pipeline-blockers`
- [ ] T012 [US3] Stage KMS changes: `git add infrastructure/terraform/modules/kms/main.tf`
- [ ] T013 [US3] Commit with GPG signature: `git commit -S -m "fix(kms): Add CI deployer admin permissions to key policy"`
- [ ] T014 [US3] Push to remote: `git push -u origin 041-pipeline-blockers`
- [ ] T015 [US3] Create PR: `gh pr create --fill --base main`
- [ ] T016 [US3] Monitor pipeline: `gh run watch`
- [ ] T017 [US3] Verify no `RepositoryAlreadyExistsException` in pipeline logs
- [ ] T018 [US3] Verify no `MalformedPolicyDocumentException` in pipeline logs
- [ ] T019 [US3] Merge PR after checks pass: `gh pr merge --auto --rebase --delete-branch`

**Checkpoint**: Pipeline green, preprod deployment successful

---

## Phase 5: Polish & Verification

**Purpose**: Verify success criteria and cleanup

- [ ] T020 Verify SC-001: Pipeline job "Terraform Apply (Preprod)" completed < 10 minutes
- [ ] T021 Verify SC-002: No ECR/KMS exceptions in final pipeline run
- [ ] T022 Verify SC-003: Check preprod smoke tests passed
- [ ] T023 Verify SC-004: Test CI deployer can update KMS key policy (optional manual test)
- [ ] T024 Update spec.md status from "Draft" to "Complete"

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **US1 ECR Import (Phase 2)**: Depends on Setup - MUST complete before pipeline validation
- **US2 KMS Fix (Phase 3)**: Depends on Setup - can run parallel to US1
- **US3 Pipeline (Phase 4)**: Depends on US1 and US2 completion
- **Polish (Phase 5)**: Depends on US3 completion

### User Story Dependencies

```text
          ┌──────────────┐
          │   Setup      │
          │  (T001-T003) │
          └──────┬───────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌───────────────┐ ┌───────────────┐
│  US1: ECR     │ │  US2: KMS     │
│  (T004-T006)  │ │  (T007-T010)  │
└───────┬───────┘ └───────┬───────┘
        │                 │
        └────────┬────────┘
                 │
                 ▼
        ┌───────────────┐
        │  US3: Pipeline│
        │  (T011-T019)  │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │    Polish     │
        │  (T020-T024)  │
        └───────────────┘
```

### Parallel Opportunities

- **US1 and US2 can run in parallel** after Setup completes
  - US1 (ECR import) is a one-time bootstrap command
  - US2 (KMS fix) is a code change
  - Both are independent resources

---

## Parallel Example: US1 + US2

```bash
# After Setup completes, these can run simultaneously:

# Terminal 1 (US1 - ECR Import):
terraform import aws_ecr_repository.sse_streaming preprod-sse-streaming-lambda
terraform plan  # Verify ECR clean

# Terminal 2 (US2 - KMS Fix):
# Edit modules/kms/main.tf
terraform validate
terraform plan -target=module.kms
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: US1 ECR Import (T004-T006) - **Unblocks pipeline**
3. Complete Phase 3: US2 KMS Fix (T007-T010) - **Enables key creation**
4. **STOP and VALIDATE**: Both blockers resolved locally

### Full Delivery

1. Complete MVP above
2. Complete Phase 4: US3 Pipeline (T011-T019) - **Push and verify**
3. Complete Phase 5: Polish (T020-T024) - **Verify success criteria**

### Single Developer Strategy

Since this is a small infrastructure fix:
1. Run T001-T003 (Setup) ~2 min
2. Run T004-T006 (ECR Import) ~3 min
3. Run T007-T010 (KMS Fix) ~5 min
4. Run T011-T019 (Pipeline) ~15 min (waiting for CI)
5. Run T020-T024 (Verification) ~5 min

**Total estimated time**: ~30 minutes

---

## Notes

- US1 (ECR Import) requires `sentiment-analyzer-dev` credentials (not preprod-deployer)
- US2 (KMS Fix) is a code change that goes through normal PR flow
- US3 validates that the pipeline works end-to-end
- No unit tests needed - validation is via terraform plan/apply
- Commit after KMS fix only (ECR import modifies state, not code)
