# Research: ECR Docker Build for SSE Lambda

**Date**: 2025-12-06
**Feature**: 038-ecr-docker-build

## Research Summary

This feature adds a Docker build job to the existing deploy.yml workflow. All infrastructure (ECR repo, IAM permissions, Dockerfile) already exists - only the CI pipeline step is missing.

## Decision 1: GitHub Actions for Docker Build

**Decision**: Use aws-actions/amazon-ecr-login@v2 and docker/build-push-action@v6

**Rationale**: These are the official and most maintained actions for ECR authentication and Docker builds. They integrate well with GitHub Actions caching and provide clear error messages.

**Alternatives considered**:
- Manual docker login/build/push commands - Rejected because official actions handle edge cases better (token refresh, retries)
- AWS CodeBuild - Rejected because adds unnecessary complexity when GHA runners have Docker

## Decision 2: Build Timing

**Decision**: Add Docker build step AFTER S3 upload but BEFORE Terraform apply for each environment

**Rationale**:
- Terraform apply needs the image to exist in ECR
- S3 uploads are fast and can run in parallel
- Building per-environment allows environment-specific tags if needed later

**Alternatives considered**:
- Build once in the `build` job and reuse - Rejected because ECR repos are per-environment, would require cross-account ECR access
- Build in a separate workflow - Rejected because adds coordination complexity and potential race conditions

## Decision 3: Image Tagging Strategy

**Decision**: Tag with both `:latest` and `:{commit-sha}` for rollback capability

**Rationale**:
- `:latest` is what Terraform currently references
- `:{commit-sha}` provides immutable rollback targets
- ECR lifecycle policy keeps last 5 images, preventing unbounded growth

**Alternatives considered**:
- Only `:latest` tag - Rejected because no rollback capability
- Semantic versioning - Rejected as overkill for Lambda deployments where we want latest

## Decision 4: Caching Strategy

**Decision**: Use GitHub Actions cache with docker/build-push-action cache-from/cache-to

**Rationale**:
- GHA cache is free and fast
- build-push-action supports inline caching natively
- Avoids ECR cache storage costs

**Alternatives considered**:
- ECR cache - Adds cost, complexity
- No caching - Rejected because clean builds take 3-5 minutes vs ~1 minute cached

## Decision 5: Error Handling

**Decision**: Fail fast - if Docker build fails, skip Terraform apply

**Rationale**:
- Terraform will fail anyway if image doesn't exist
- Failing early provides clearer error messages
- Prevents partial deployments

**Implementation**: Standard GitHub Actions job dependency (`needs: build-sse-image`)

## Existing Infrastructure Inventory

### Already Complete (No Changes Needed)

| Component | Location | Status |
|-----------|----------|--------|
| Dockerfile | `src/lambdas/sse_streaming/Dockerfile` | Complete |
| ECR Repository | `infrastructure/terraform/main.tf:567` | Complete |
| ECR Lifecycle Policy | `infrastructure/terraform/main.tf:587` | Complete |
| Lambda image_uri reference | `infrastructure/terraform/main.tf:618` | Complete |
| IAM ECR permissions | `infrastructure/terraform/ci-user-policy.tf:272-330` | Complete |

### To Be Added

| Component | Location | Change |
|-----------|----------|--------|
| Docker build job (preprod) | `.github/workflows/deploy.yml` | Add new job |
| Docker build job (prod) | `.github/workflows/deploy.yml` | Add new job |

## References

- [aws-actions/amazon-ecr-login](https://github.com/aws-actions/amazon-ecr-login)
- [docker/build-push-action](https://github.com/docker/build-push-action)
- [AWS Lambda Container Image Support](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [AWS Lambda Web Adapter](https://github.com/awslabs/aws-lambda-web-adapter)
