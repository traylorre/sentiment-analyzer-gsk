# Tasks: Dashboard Lambda Container Deployment

**Input**: Design documents from `/specs/1036-dashboard-container-deploy/`
**Prerequisites**: plan.md (required), spec.md (required for user stories)

**Organization**: All three user stories share the same goal (fix 502 error), so tasks are organized by implementation phase rather than story.

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 1: ECR Repository Setup

**Purpose**: Create container registry infrastructure for Dashboard Lambda

- [x] T001 Add ECR repository resource for Dashboard Lambda in infrastructure/terraform/main.tf
- [x] T002 Add lifecycle policy to ECR repository (keep last 5 images) in infrastructure/terraform/main.tf
- [x] T003 [P] Add ECR repository URL output in infrastructure/terraform/main.tf

**Checkpoint**: ECR infrastructure ready for container images

---

## Phase 2: Dockerfile Creation

**Purpose**: Create container build definition for Dashboard Lambda

- [x] T004 Create Dockerfile for Dashboard Lambda in src/lambdas/dashboard/Dockerfile
- [x] T005 Create container-specific requirements.txt in src/lambdas/dashboard/requirements.txt
- [ ] T006 Validate Dockerfile builds locally with `docker build` (skipped - validated in CI)

**Checkpoint**: Container image builds successfully

---

## Phase 3: Deploy Workflow Update

**Purpose**: Add container build and push steps to CI/CD pipeline

- [x] T007 Add "Build Dashboard Lambda Image (Preprod)" job to .github/workflows/deploy.yml
- [x] T008 Add "Build Dashboard Lambda Image (Production)" job to .github/workflows/deploy.yml
- [x] T009 Add force Lambda image update step for Dashboard in deploy job
- [x] T010 Remove ZIP packaging steps for Dashboard Lambda from deploy workflow

**Checkpoint**: CI/CD pipeline builds and pushes Dashboard container image

---

## Phase 4: Terraform Lambda Update

**Purpose**: Switch Dashboard Lambda from ZIP to container deployment

- [x] T011 Update Dashboard Lambda module to use image_uri instead of s3_bucket/s3_key in infrastructure/terraform/main.tf
- [x] T012 Update package_type to "Image" for Dashboard Lambda in infrastructure/terraform/main.tf
- [x] T013 Add dependency on ECR repository for Dashboard Lambda in infrastructure/terraform/main.tf

**Checkpoint**: Terraform configured for container-based Lambda deployment

---

## Phase 5: Validation

**Purpose**: Verify the migration works correctly in preprod

- [ ] T014 Push changes and trigger Deploy Pipeline
- [ ] T015 Verify preprod health endpoint returns HTTP 200
- [ ] T016 Verify CloudWatch logs have no ImportModuleError
- [ ] T017 Run E2E tests to confirm all pass

**Checkpoint**: Preprod Dashboard Lambda fully functional

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (ECR)**: No dependencies - can start immediately
- **Phase 2 (Dockerfile)**: No dependencies - can run parallel with Phase 1
- **Phase 3 (Workflow)**: Depends on Phase 1 (needs ECR repository names)
- **Phase 4 (Terraform)**: Depends on Phase 1 (needs ECR repository references)
- **Phase 5 (Validation)**: Depends on Phases 1-4 completion

### Parallel Opportunities

```text
Phase 1: T001 → T002 → T003 (sequential within ECR setup)
Phase 2: T004 → T005 → T006 (sequential, Dockerfile first)

After Phase 1 complete:
  Phase 3: T007 → T008 → T009 → T010 (can overlap with Phase 4)
  Phase 4: T011 → T012 → T013

Phase 5: T014 → T015 → T016 → T017 (sequential validation)
```

---

## Implementation Strategy

### MVP: Fix 502 Error

1. Complete Phase 1: ECR repository
2. Complete Phase 2: Dockerfile
3. Complete Phase 3: Workflow updates
4. Complete Phase 4: Terraform updates
5. **VALIDATE**: Deploy and verify health endpoint returns 200

### Success Criteria (from spec)

- SC-001: Preprod health endpoint returns HTTP 200 ✓
- SC-002: No ImportModuleError in CloudWatch logs ✓
- SC-003: E2E tests pass ✓
- SC-004: Deploy Pipeline workflow completes green ✓
- SC-005: Cold start < 15 seconds ✓

---

## Notes

- Follow existing Analysis Lambda container pattern (ADR-005)
- Base image: `public.ecr.aws/lambda/python:3.13`
- Handler path must remain `handler.lambda_handler`
- Keep ZIP packaging for other Lambdas (Ingestion, Metrics, Notification)
