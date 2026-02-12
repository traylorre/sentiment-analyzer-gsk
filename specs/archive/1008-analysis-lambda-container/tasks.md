# Tasks: Analysis Lambda Container Image Deployment

## Phase 1: Container Definition

- [ ] T001: Create `src/lambdas/analysis/requirements.txt` with PyTorch CPU-only, transformers, boto3, pydantic, aws-xray-sdk
- [ ] T002: Create `src/lambdas/analysis/Dockerfile` based on Lambda Python 3.13 base image
- [ ] T003: Verify Dockerfile builds locally (docker build test)

## Phase 2: Terraform Infrastructure

- [ ] T004: Add `aws_ecr_repository.analysis` resource to main.tf
- [ ] T005: Add ECR lifecycle policy (keep last 5 images)
- [ ] T006: Update `module.analysis_lambda` to use `image_uri` instead of ZIP
- [ ] T007: Run `terraform fmt` and `terraform validate`

## Phase 3: CI/CD Workflow

- [ ] T008: Add `build-analysis-image-preprod` job to deploy.yml
- [ ] T009: Add smoke test step to validate container imports
- [ ] T010: Update `deploy-preprod` job to depend on `build-analysis-image-preprod`
- [ ] T011: Add force-update step for Analysis Lambda image (like SSE)

## Phase 4: Testing and Validation

- [ ] T012: Create feature branch and commit all changes
- [ ] T013: Push and create PR with auto-merge
- [ ] T014: Monitor deploy workflow for success
- [ ] T015: Invoke self-healing to trigger analysis
- [ ] T016: Verify CloudWatch logs show model loading
- [ ] T017: Verify DynamoDB items have sentiment attribute
- [ ] T018: Verify dashboard shows non-zero values

## Definition of Done

- [ ] All tasks completed
- [ ] PR merged to main
- [ ] Deploy workflow passes
- [ ] Analysis Lambda processes items successfully
- [ ] Dashboard displays sentiment data
