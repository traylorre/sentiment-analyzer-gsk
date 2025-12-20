# Quickstart: ECR Docker Build for SSE Lambda

**Date**: 2025-12-06
**Feature**: 038-ecr-docker-build

## Overview

Add Docker build steps to deploy.yml to build and push SSE Lambda container image to ECR before Terraform runs. This unblocks the pipeline which is currently failing with "Source image does not exist".

## Target Files

| File | Action | Description |
|------|--------|-------------|
| `.github/workflows/deploy.yml` | MODIFY | Add Docker build jobs for preprod and prod |

## Implementation Steps

### Step 1: Add Build SSE Image Job (Preprod)

Insert a new job `build-sse-image-preprod` after `deploy-preprod-s3` but before `deploy-preprod`:

```yaml
build-sse-image-preprod:
  name: Build SSE Lambda Image (Preprod)
  runs-on: ubuntu-latest
  needs: [build, deploy-preprod-s3]
  outputs:
    image_uri: ${{ steps.build-push.outputs.image_uri }}
  steps:
    - uses: actions/checkout@v4

    - name: Configure AWS Credentials (Preprod)
      uses: aws-actions/configure-aws-credentials@v5
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ vars.AWS_REGION }}

    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2

    - name: Build and Push SSE Lambda Image
      id: build-push
      uses: docker/build-push-action@v6
      with:
        context: src/lambdas/sse_streaming
        push: true
        tags: |
          ${{ steps.login-ecr.outputs.registry }}/preprod-sse-streaming-lambda:latest
          ${{ steps.login-ecr.outputs.registry }}/preprod-sse-streaming-lambda:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

### Step 2: Update deploy-preprod Dependencies

Modify `deploy-preprod` job to depend on the new build job:

```yaml
deploy-preprod:
  name: Deploy to Preprod
  needs: [build, deploy-preprod-s3, build-sse-image-preprod]  # Added build-sse-image-preprod
  # ... rest of job
```

### Step 3: Add Build SSE Image Job (Prod)

Add similar job `build-sse-image-prod` after `deploy-prod-s3`:

```yaml
build-sse-image-prod:
  name: Build SSE Lambda Image (Prod)
  runs-on: ubuntu-latest
  needs: [build, deploy-prod-s3, validation-gate]
  steps:
    - uses: actions/checkout@v4

    - name: Configure AWS Credentials (Production)
      uses: aws-actions/configure-aws-credentials@v5
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ vars.AWS_REGION }}

    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2

    - name: Build and Push SSE Lambda Image
      uses: docker/build-push-action@v6
      with:
        context: src/lambdas/sse_streaming
        push: true
        tags: |
          ${{ steps.login-ecr.outputs.registry }}/prod-sse-streaming-lambda:latest
          ${{ steps.login-ecr.outputs.registry }}/prod-sse-streaming-lambda:${{ github.sha }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
```

### Step 4: Update deploy-prod Dependencies

Modify `deploy-prod` job:

```yaml
deploy-prod:
  name: Deploy to Production
  needs: [deploy-preprod, validation-gate, deploy-prod-s3, build-sse-image-prod]  # Added build-sse-image-prod
  # ... rest of job
```

## Verification Checklist

After implementation, verify:

- [ ] `build-sse-image-preprod` job runs successfully
- [ ] ECR image appears with `:latest` and `:sha` tags
- [ ] `deploy-preprod` job now depends on `build-sse-image-preprod`
- [ ] Terraform apply succeeds (no more "Source image does not exist" error)
- [ ] `build-sse-image-prod` job runs successfully after validation gate
- [ ] `deploy-prod` job now depends on `build-sse-image-prod`

## Expected Workflow Diagram

```
build
  │
  ├──────────────────┬────────────────────┐
  │                  │                    │
  ▼                  ▼                    │
deploy-preprod-s3    │                    │
  │                  │                    │
  └────────┬─────────┘                    │
           │                              │
           ▼                              │
  build-sse-image-preprod                 │
           │                              │
           ▼                              │
      deploy-preprod                      │
           │                              │
           ▼                              │
        e2e-tests                         │
           │                              │
           ▼                              │
     validation-gate ─────────────────────┤
           │                              │
           ├──────────────────────────────┘
           │
           ▼
    deploy-prod-s3
           │
           ▼
  build-sse-image-prod
           │
           ▼
       deploy-prod
           │
           ▼
     canary-tests
```

## Notes

- Dockerfile already exists and is tested locally
- ECR repository is created by Terraform on first run (may need manual initial image)
- IAM permissions for ECR are already in place via ci-user-policy.tf
- Build uses GitHub Actions cache for layer reuse
