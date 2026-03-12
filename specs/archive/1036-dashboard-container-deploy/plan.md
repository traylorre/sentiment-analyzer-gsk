# Implementation Plan: Dashboard Lambda Container Deployment

**Branch**: `1036-dashboard-container-deploy` | **Date**: 2025-12-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1036-dashboard-container-deploy/spec.md`

## Summary

Migrate Dashboard Lambda from ZIP packaging to container image deployment to resolve HTTP 502 errors caused by pydantic_core binary incompatibility with Lambda's AL2023 + Python 3.13 runtime. Follow the existing pattern established by Analysis Lambda container deployment (ADR-005).

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: FastAPI 0.127.0, Mangum 0.19.0, pydantic 2.12.5, boto3 1.42.14
**Storage**: DynamoDB (existing tables), S3 (ticker cache)
**Testing**: pytest with moto mocks (unit), preprod E2E tests
**Target Platform**: AWS Lambda with AL2023 runtime
**Project Type**: Web application (Lambda + API Gateway)
**Performance Goals**: Cold start < 15s, health check response < 2s
**Constraints**: Container image < 1GB, same handler path as current ZIP
**Scale/Scope**: Single Lambda function migration

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Amendment 1.6 (No Quick Fixes) | PASS | Following full speckit workflow |
| Amendment 1.8 (IAM Managed Policy) | N/A | No IAM changes |
| Amendment 1.12 (Mandatory Speckit) | PASS | Spec created, plan in progress |
| Amendment 1.14 (Validator Usage) | PASS | Will run validators after implementation |

## Project Structure

### Documentation (this feature)

```text
specs/1036-dashboard-container-deploy/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research (N/A - using existing ADR-005)
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (speckit.tasks)
```

### Source Code (repository root)

```text
src/lambdas/dashboard/
├── Dockerfile           # NEW: Container build definition
├── handler.py           # EXISTING: FastAPI + Mangum adapter
├── router_v2.py         # EXISTING: API routes
├── configurations.py    # EXISTING: User config management
└── requirements.txt     # NEW: Container-specific deps (subset of main)

infrastructure/terraform/
├── main.tf              # MODIFY: Add ECR repository, update Lambda config
└── variables.tf         # No changes expected

.github/workflows/
└── deploy.yml           # MODIFY: Add container build job for Dashboard
```

**Structure Decision**: Following existing Analysis Lambda pattern - Dockerfile at Lambda source root, container-specific requirements.txt.

## Implementation Approach

### Phase 1: ECR Repository Setup

1. Add `aws_ecr_repository.dashboard` resource to main.tf (copy from analysis pattern)
2. Add lifecycle policy to retain last 5 images
3. Enable image scanning on push

### Phase 2: Dockerfile Creation

1. Create `src/lambdas/dashboard/Dockerfile` following Analysis Lambda pattern
2. Base image: `public.ecr.aws/lambda/python:3.13`
3. Install dependencies from requirements.txt
4. Copy handler.py and supporting modules
5. Set PYTHONPATH and CMD for Lambda handler

### Phase 3: Deploy Workflow Update

1. Add "Build Dashboard Lambda Image" job (copy from SSE/Analysis pattern)
2. Build and push to ECR with both `:latest` and `:{github-sha}` tags
3. Add force update step using AWS CLI (same as SSE pattern)
4. Remove ZIP packaging steps for Dashboard (keep for other Lambdas)

### Phase 4: Terraform Lambda Update

1. Change Dashboard Lambda from ZIP to container image
2. Update `package_type = "Image"`
3. Update `image_uri` to point to ECR repository
4. Remove `s3_bucket` and `s3_key` references

### Phase 5: Validation

1. Deploy to preprod
2. Verify health endpoint returns HTTP 200
3. Verify CloudWatch logs have no ImportModuleError
4. Run E2E tests to confirm all pass

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Container build failure | Pre-validate Dockerfile locally with `docker build` |
| Cold start regression | Monitor cold start times, adjust memory if needed |
| Handler path mismatch | Verify CMD matches existing handler.lambda_handler |
| Missing dependencies | Validate requirements.txt includes all transitive deps |

## Dependencies

- ECR repository must exist before Lambda can reference it
- Container image must be pushed before Terraform apply
- Existing Analysis/SSE Lambda patterns provide proven reference

## Complexity Tracking

No constitution violations. This follows an established pattern (ADR-005).
