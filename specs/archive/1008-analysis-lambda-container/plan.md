# Implementation Plan: Analysis Lambda Container Image Deployment

## Phase 1: Container Definition (Dockerfile + requirements.txt)

### Step 1.1: Create requirements.txt
Create production dependencies file with PyTorch CPU-only and transformers.

**File**: `src/lambdas/analysis/requirements.txt`

**Dependencies**:
```
# PyTorch CPU-only (minimal size, no CUDA)
--extra-index-url https://download.pytorch.org/whl/cpu
torch==2.5.1+cpu

# HuggingFace Transformers for DistilBERT
transformers==4.46.3

# AWS SDK
boto3==1.35.76

# Data validation
pydantic==2.10.3

# Structured logging
python-json-logger==2.0.7

# AWS X-Ray tracing (FR-035 Day 1 mandatory)
aws-xray-sdk==2.14.0
```

### Step 1.2: Create Dockerfile
Based on SSE Lambda pattern but for SNS-triggered Lambda (not WSGI).

**File**: `src/lambdas/analysis/Dockerfile`

**Key differences from SSE Lambda**:
- No Lambda Web Adapter (not a web app)
- Uses `public.ecr.aws/lambda/python:3.13` base image
- Handler: `handler.lambda_handler`
- No uvicorn, just Lambda runtime

## Phase 2: Terraform Infrastructure

### Step 2.1: Add ECR Repository
Add `aws_ecr_repository.analysis` resource mirroring SSE pattern.

**Location**: `infrastructure/terraform/main.tf` after SSE ECR (line ~617)

**Configuration**:
- Name: `${var.environment}-analysis-lambda`
- Image scanning on push
- AES256 encryption
- Lifecycle policy: keep last 5 images

### Step 2.2: Update Lambda Module
Modify `module.analysis_lambda` to use container image.

**Changes**:
- Add `image_uri` parameter pointing to ECR repo
- Remove `s3_bucket` and `s3_key` parameters
- Keep memory_size, timeout, environment_variables

### Step 2.3: Add IAM for ECR Pull
Ensure Lambda execution role can pull from ECR.

**Note**: Lambda module may already handle this via AWS managed policy.

## Phase 3: CI/CD Workflow

### Step 3.1: Add Build Job
Add `build-analysis-image-preprod` job to deploy.yml.

**Location**: After `build-sse-image-preprod` job

**Pattern**: Copy SSE job structure with modifications:
- Context: `src/lambdas/`
- Dockerfile: `src/lambdas/analysis/Dockerfile`
- Repository: `${PREPROD_ECR_REGISTRY}/${PREPROD_ECR_ANALYSIS_REPO}`
- Tags: `latest`, `${GITHUB_SHA}`

### Step 3.2: Add Smoke Test
Validate container imports before deployment.

**Test**:
```bash
docker run --rm analysis-lambda:latest python -c "
from handler import lambda_handler
from src.lambdas.analysis.sentiment import load_model
print('Import validation passed')
"
```

### Step 3.3: Update Deploy Job
Add dependency on `build-analysis-image-preprod`.

## Phase 4: Testing and Validation

### Step 4.1: Local Build Test
Build container locally and verify imports.

### Step 4.2: Preprod Deployment
Push to preprod, verify:
- ECR image exists
- Lambda uses container image
- CloudWatch logs show model loading
- Self-healing triggers analysis
- DynamoDB items get sentiment attribute
- Dashboard shows non-zero values

## Implementation Order

1. `src/lambdas/analysis/requirements.txt` - dependencies
2. `src/lambdas/analysis/Dockerfile` - container definition
3. `infrastructure/terraform/main.tf` - ECR repo + Lambda update
4. `.github/workflows/deploy.yml` - build job
5. Test and validate

## Estimated Effort

| Phase | Estimated Time |
|-------|----------------|
| Phase 1: Container Definition | 30 min |
| Phase 2: Terraform | 30 min |
| Phase 3: Workflow | 45 min |
| Phase 4: Testing | 30 min |
| **Total** | ~2.5 hours |
