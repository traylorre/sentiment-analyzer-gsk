# Tasks: ECR Docker Build for SSE Lambda

**Input**: Design documents from `/specs/038-ecr-docker-build/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, quickstart.md

**Tests**: Not required - pipeline execution serves as validation

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Review existing workflow and verify prerequisites

- [ ] T001 Read existing workflow in .github/workflows/deploy.yml to identify insertion points
- [ ] T002 [P] Verify Dockerfile exists at src/lambdas/sse_streaming/Dockerfile
- [ ] T003 [P] Verify ECR repository naming in infrastructure/terraform/main.tf (line 567-585)
- [ ] T004 [P] Verify IAM ECR permissions in infrastructure/terraform/ci-user-policy.tf (line 272-330)

**Checkpoint**: All prerequisites verified, ready for implementation

---

## Phase 2: Foundational

**Purpose**: No foundational tasks needed - all infrastructure already exists

**Checkpoint**: Proceed directly to user story implementation

---

## Phase 3: User Story 1 - CI Pipeline Builds Docker Image (Priority: P1) 🎯 MVP

**Goal**: Add Docker build job to preprod deployment that builds and pushes image before Terraform

**Independent Test**: Run pipeline on feature branch, verify image appears in ECR with `:latest` tag

### Implementation for User Story 1

- [ ] T005 [US1] Add `build-sse-image-preprod` job after `deploy-preprod-s3` in .github/workflows/deploy.yml
- [ ] T006 [US1] Configure AWS credentials step using aws-actions/configure-aws-credentials@v5 in build-sse-image-preprod job
- [ ] T007 [US1] Add ECR login step using aws-actions/amazon-ecr-login@v2 in build-sse-image-preprod job
- [ ] T008 [US1] Add Docker build-push step using docker/build-push-action@v6 with context src/lambdas/sse_streaming
- [ ] T009 [US1] Update `deploy-preprod` job to add `build-sse-image-preprod` to needs array in .github/workflows/deploy.yml

**Checkpoint**: Preprod pipeline builds and pushes Docker image before Terraform apply - SC-003 achieved

---

## Phase 4: User Story 2 - Environment-Specific Image Tags (Priority: P2)

**Goal**: Add production build job with environment-specific repository naming

**Independent Test**: Run full pipeline, verify preprod uses `preprod-sse-streaming-lambda` and prod uses `prod-sse-streaming-lambda`

### Implementation for User Story 2

- [ ] T010 [US2] Add `build-sse-image-prod` job after `validation-gate` in .github/workflows/deploy.yml
- [ ] T011 [US2] Configure AWS credentials step for production in build-sse-image-prod job
- [ ] T012 [US2] Add ECR login and Docker build-push steps for prod-sse-streaming-lambda repository
- [ ] T013 [US2] Update `deploy-prod` job to add `build-sse-image-prod` to needs array in .github/workflows/deploy.yml
- [ ] T014 [US2] Add commit SHA tag alongside :latest for both preprod and prod builds (rollback support)

**Checkpoint**: Both environments have isolated Docker builds with immutable SHA tags

---

## Phase 5: User Story 3 - Image Build Caching (Priority: P3)

**Goal**: Enable GitHub Actions cache for Docker layer reuse

**Independent Test**: Compare build times between clean build and cached build - SC-002 targets <2 minutes cached

### Implementation for User Story 3

- [ ] T015 [US3] Add cache-from and cache-to parameters to preprod build-push step in .github/workflows/deploy.yml
- [ ] T016 [US3] Add cache-from and cache-to parameters to prod build-push step in .github/workflows/deploy.yml

**Checkpoint**: Subsequent builds reuse cached layers - SC-001 and SC-002 achieved

---

## Phase 6: Polish & Verification

**Purpose**: Final validation and documentation

- [ ] T017 Push branch and trigger pipeline to verify build-sse-image-preprod runs successfully
- [ ] T018 [P] Verify ECR image exists with both :latest and :sha tags via AWS CLI or Console
- [ ] T019 [P] Verify Terraform apply succeeds without "Source image does not exist" error
- [ ] T020 Monitor build times to confirm <5 min clean build, <2 min cached build (SC-001, SC-002)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verification tasks
- **Foundational (Phase 2)**: Skipped - infrastructure exists
- **User Stories (Phase 3-5)**: Sequential - all modify same file
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: No dependencies - core MVP
- **User Story 2 (P2)**: Depends on US1 pattern (same file)
- **User Story 3 (P3)**: Depends on US1 and US2 (adds to existing steps)

### Within Each User Story

- AWS credentials → ECR login → Docker build-push → Update dependencies
- Each story modifies same file but different sections

### Parallel Opportunities

- T002, T003, T004 (Phase 1): All read different files
- T018, T019 (Phase 6): Independent verification tasks
- **Note**: US1-US3 are sequential because they all modify .github/workflows/deploy.yml

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all verification tasks in parallel:
Task: "Verify Dockerfile exists at src/lambdas/sse_streaming/Dockerfile"
Task: "Verify ECR repository naming in infrastructure/terraform/main.tf"
Task: "Verify IAM ECR permissions in infrastructure/terraform/ci-user-policy.tf"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify prerequisites)
2. Complete Phase 3: User Story 1 (preprod Docker build)
3. **STOP and VALIDATE**: Push branch, verify preprod pipeline passes
4. Can ship MVP with just preprod Docker build

### Incremental Delivery

1. Add User Story 1 → Preprod pipeline unblocked → Immediate value
2. Add User Story 2 → Prod pipeline enabled → Full deployment capability
3. Add User Story 3 → Faster builds → Developer experience improvement

### Single Developer Strategy

Since all tasks modify the same file (.github/workflows/deploy.yml):
1. Complete Setup verification
2. Add all job definitions in sequence (US1 → US2 → US3)
3. Single commit with complete implementation
4. Push and validate pipeline

---

## Notes

- All user story tasks modify .github/workflows/deploy.yml - cannot parallelize
- Setup tasks ARE parallelizable (read different files)
- Verification tasks ARE parallelizable (independent checks)
- YAML snippets available in specs/038-ecr-docker-build/quickstart.md
- No application code changes required
- Commit after Phase 3 (US1) to get immediate value
