# Implementation Plan: ECR Docker Build for SSE Lambda

**Branch**: `038-ecr-docker-build` | **Date**: 2025-12-06 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/038-ecr-docker-build/spec.md`

## Summary

Add Docker build step to GitHub Actions deploy.yml workflow to build and push the SSE streaming Lambda container image to ECR before Terraform runs. The Dockerfile already exists at `src/lambdas/sse_streaming/Dockerfile` and ECR repository is already defined in Terraform. This is a workflow-only change - no application code modifications needed.

## Technical Context

**Language/Version**: GitHub Actions YAML, Docker (Python 3.13-slim base)
**Primary Dependencies**: aws-actions/amazon-ecr-login, docker/build-push-action
**Storage**: AWS ECR (`{env}-sse-streaming-lambda` repository)
**Testing**: Pipeline execution validation (image exists after build step)
**Target Platform**: GitHub Actions runners (ubuntu-latest with Docker)
**Project Type**: CI/CD pipeline modification (single file change)
**Performance Goals**: Clean build <5 minutes, cached build <2 minutes
**Constraints**: Must run before Terraform apply, must use existing ECR repo naming
**Scale/Scope**: 1 workflow file modification, 2 environments (preprod, prod)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Deployment via IaC | PASS | ECR repository already in Terraform, this adds CI build step |
| CI/CD integration | PASS | Adding standard Docker build pattern to existing workflow |
| Pre-push requirements | PASS | No code changes, only workflow YAML |
| Branch protection | PASS | Using standard feature branch workflow |
| No bypass allowed | PASS | Standard PR flow maintained |

**All gates passed. Proceeding to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/038-ecr-docker-build/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
.github/workflows/
└── deploy.yml           # MODIFIED: Add Docker build job

src/lambdas/sse_streaming/
├── Dockerfile           # EXISTING: No changes needed
├── requirements.txt     # EXISTING: Dependencies for Docker build
└── handler.py           # EXISTING: Lambda handler
```

**Structure Decision**: Workflow-only modification. No new directories. Existing Dockerfile is complete and functional.

## Existing Infrastructure Analysis

### Dockerfile (src/lambdas/sse_streaming/Dockerfile)
- Base: `python:3.13-slim` multi-stage build
- Uses AWS Lambda Web Adapter (`aws-lambda-adapter:0.9.1`)
- Sets `AWS_LWA_INVOKE_MODE=RESPONSE_STREAM` for SSE
- Exposes port 8080 for Lambda Web Adapter
- Runtime: uvicorn with FastAPI handler

### ECR Repository (infrastructure/terraform/main.tf:567-585)
- Name: `{env}-sse-streaming-lambda` (e.g., `preprod-sse-streaming-lambda`)
- Image scanning enabled
- Immutable tags disabled (allows `:latest` overwrite)
- Lifecycle policy keeps last 5 images

### Lambda Configuration (infrastructure/terraform/main.tf:608-667)
- `image_uri = "${aws_ecr_repository.sse_streaming.repository_url}:latest"`
- Package type: `Image`
- Invoke mode: `RESPONSE_STREAM`

### IAM Permissions (infrastructure/terraform/ci-user-policy.tf:272-330)
- ECR repository management (Create, Delete, Describe, etc.)
- ECR image operations (PutImage, BatchGetImage, etc.)
- ECR authorization token (for docker login)
- Scoped to `*-sse-streaming-*` pattern

## Complexity Tracking

No violations detected. This is a standard CI/CD pattern addition.
