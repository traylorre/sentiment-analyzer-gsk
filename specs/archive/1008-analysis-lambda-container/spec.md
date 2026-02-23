# Feature 1008: Analysis Lambda Container Image Deployment

## Overview

Deploy the Analysis Lambda as a container image to include PyTorch and transformers libraries for ML sentiment inference. This implements ADR-005 Phase 2.

## Problem Statement

The Analysis Lambda fails with `No module named 'transformers'` because:
- Current ZIP packaging excludes heavy ML dependencies (torch ~2GB, transformers ~500MB)
- Deploy workflow line 252-254 explicitly states "NO torch/transformers"
- ADR-005 Phase 2 (container migration) was planned but never implemented
- Model weights ARE in S3 (`s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/model.tar.gz`)
- But the transformers library to LOAD the model is missing

## Solution

Deploy Analysis Lambda as ECR container image following the proven SSE Lambda container pattern:
- Two-stage Docker build (builder + runtime)
- PyTorch CPU-only + transformers bundled in container
- Model weights downloaded from S3 at runtime (already implemented in sentiment.py)
- Reuse existing Lambda module with `image_uri` support

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-001 | Create Dockerfile for Analysis Lambda with PyTorch CPU-only and transformers | P0 |
| FR-002 | Create ECR repository for Analysis Lambda images | P0 |
| FR-003 | Add workflow job to build and push Analysis Lambda image | P0 |
| FR-004 | Update Terraform to deploy Lambda from container image instead of ZIP | P0 |
| FR-005 | Add smoke test to validate container imports before deployment | P0 |
| FR-006 | Lambda must load model from S3 and perform sentiment inference | P0 |
| FR-007 | Container must use non-root user (security requirement from 090-security-first-burndown) | P1 |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-001 | Cold start time < 10 seconds | P1 |
| NFR-002 | Container image size < 3GB | P1 |
| NFR-003 | Build time < 10 minutes in CI | P2 |
| NFR-004 | Memory usage < 2048MB during inference | P0 |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Analysis Lambda Container (~2.5GB)                          │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Base: public.ecr.aws/lambda/python:3.13                 │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ Dependencies (installed in /var/task):                  │ │
│ │   - torch (CPU-only) ~700MB                             │ │
│ │   - transformers ~500MB                                 │ │
│ │   - boto3, pydantic, aws-xray-sdk ~50MB                 │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ Code: handler.py, sentiment.py, shared/                 │ │
│ ├─────────────────────────────────────────────────────────┤ │
│ │ Model: Downloaded from S3 at runtime → /tmp/model       │ │
│ │   - distilbert/v1.0.0/model.tar.gz (247MB)              │ │
│ └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Files to Create/Modify

### New Files
- `src/lambdas/analysis/Dockerfile` - Container definition
- `src/lambdas/analysis/requirements.txt` - Production dependencies

### Modified Files
- `infrastructure/terraform/main.tf` - Add ECR repository, update Lambda module
- `.github/workflows/deploy.yml` - Add build-analysis-image job

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | Container builds successfully in CI | Workflow job completes |
| SC-002 | Smoke test validates imports | Docker import test passes |
| SC-003 | Lambda deploys with container image | Terraform apply succeeds |
| SC-004 | Model loads from S3 | CloudWatch logs show "Model loaded successfully" |
| SC-005 | Sentiment inference works | DynamoDB items updated with sentiment attribute |
| SC-006 | Dashboard shows non-zero values | Visual verification |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Large image size causes slow cold starts | Medium | Use Lambda-optimized base image, optimize layers |
| PyTorch version mismatch with model | High | Pin exact versions matching model training env |
| ECR permissions missing | Medium | Copy IAM patterns from SSE Lambda |
| Build timeout in CI | Low | Use Docker layer caching |

## Dependencies

- Existing SSE Lambda container infrastructure (ECR, workflow, Lambda module)
- Model already in S3: `s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/model.tar.gz`
- Lambda memory already at 2048MB (PR #447)

## Out of Scope

- ONNX conversion (future optimization)
- Model bundled in container (stays in S3 for size efficiency)
- Production deployment (preprod only for now)
