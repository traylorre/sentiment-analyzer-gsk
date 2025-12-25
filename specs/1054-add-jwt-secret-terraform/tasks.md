# Tasks: Add JWT_SECRET to Lambda Terraform Configuration

**Feature ID**: 1054
**Input**: spec.md

## Phase 1: Terraform Variable Setup

- [x] T001 Add jwt_secret variable to infrastructure/terraform/variables.tf with sensitive = true
- [x] T002 Add jwt_secret to preprod.tfvars with E2E test default value (comment only, value via secrets)
- [x] T003 Add jwt_secret to prod.tfvars with production value placeholder (comment only, value via secrets)

## Phase 2: Lambda Environment Updates

- [x] T004 Add JWT_SECRET to Dashboard Lambda environment variables in main.tf (~line 403-423)
- [x] T005 Add JWT_SECRET to SSE Lambda environment variables in main.tf (~line 731-745)

## Phase 3: CI/CD Configuration

- [x] T006 Add JWT_SECRET to deploy.yml terraform apply commands for preprod
- [x] T007 Add JWT_SECRET to deploy.yml terraform apply commands for prod
- [x] T007b Add PREPROD_TEST_JWT_SECRET to test-preprod job environment

## Phase 4: Verification

- [x] T008 Run terraform fmt and validate
- [x] T009 Run make validate to ensure no regressions
- [ ] T010 Create PR and enable auto-merge

## Dependencies

- T001 must complete before T004-T007
- T004-T005 can run in parallel after T001
- T006-T007 can run in parallel after T001

## Estimated Complexity

- **Low**: ~6 files modified, straightforward Terraform changes
- **Risk**: CI secret must be set in GitHub Actions for deploy to work

## GitHub Secrets Required

Before PR can pass, the following secrets must be added to the repository:

1. `PREPROD_JWT_SECRET` - Must match `test-jwt-secret-for-e2e-only-not-production` (the default in E2E tests)
2. `PROD_JWT_SECRET` - Strong, unique secret for production JWT validation
