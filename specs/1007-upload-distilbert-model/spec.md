# Feature 1007: Upload DistilBERT Model to S3

## Problem Statement

The Analysis Lambda cannot perform sentiment analysis because the ML model was never uploaded to S3. The Lambda attempts to download from `s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/model.tar.gz` but the bucket is empty, causing a 403 error (S3 returns 403 for non-existent objects when caller lacks ListBucket).

**Root Cause**: The `build-and-upload-model-s3.sh` script was created but never executed.

**Secondary Issue**: Lambda memory is set to 1024 MB but DistilBERT requires ~1050 MB, creating OOM risk.

## Background

### Current State
- S3 bucket exists: `sentiment-analyzer-models-218795110243`
- S3 bucket is **EMPTY** - no objects
- Analysis Lambda configured correctly
- IAM permissions correct (PR #446 added s3:HeadObject)
- Lambda memory: 1024 MB (marginal)
- Lambda ephemeral storage: 3072 MB (ample)
- Lambda timeout: 30s (ample)

### Model Details (from audit)
| Property | Value |
|----------|-------|
| Model | distilbert-base-uncased-finetuned-sst-2-english |
| Source | HuggingFace Hub |
| pytorch_model.bin | 268 MB |
| Compressed (tar.gz) | ~250 MB |
| Memory at inference | ~700 MB |

### Upload Script (ready to run)
- Path: `infrastructure/scripts/build-and-upload-model-s3.sh`
- Downloads from HuggingFace
- Packages as tar.gz
- Uploads to S3
- Includes hash verification

## Functional Requirements

### FR-001: Model Available in S3
The DistilBERT model MUST be available at:
- Bucket: `sentiment-analyzer-models-218795110243`
- Key: `distilbert/v1.0.0/model.tar.gz`
- Size: ~250 MB

### FR-002: Lambda Memory Increased
The Analysis Lambda memory MUST be increased from 1024 MB to 2048 MB to:
- Prevent OOM during inference
- Provide proportionally faster CPU
- Reduce cold start time

### FR-003: Model Loads Successfully
After fix, Analysis Lambda MUST:
- Download model from S3 on cold start
- Extract to /tmp/model
- Load via transformers pipeline
- Complete within 30s timeout

### FR-004: Sentiment Analysis Works
After fix, Analysis Lambda MUST:
- Receive SNS messages from ingestion
- Classify text as positive/negative/neutral
- Update DynamoDB items with sentiment attribute

## Non-Functional Requirements

### NFR-001: Cold Start Performance
Cold start (S3 download + model load) SHOULD complete in <15s.

### NFR-002: Warm Start Performance
Warm invocations SHOULD complete in <1s.

### NFR-003: Memory Headroom
Lambda memory SHOULD have 50%+ headroom for inference spikes.

## Success Criteria

### SC-001: S3 Object Exists
```bash
aws s3 ls s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/model.tar.gz
# Returns object with size ~250 MB
```

### SC-002: Lambda Memory Updated
```bash
aws lambda get-function-configuration --function-name preprod-sentiment-analysis --query 'MemorySize'
# Returns: 2048
```

### SC-003: Model Downloads Successfully
CloudWatch logs show:
- "Downloading model from S3"
- "Model downloaded from S3" with download_time_ms
- "Model loaded successfully" with load_time_ms

### SC-004: Sentiment Analysis Works
```bash
aws dynamodb scan --table-name preprod-sentiment-items \
  --filter-expression "attribute_exists(sentiment)" \
  --select COUNT
# Returns Count > 0
```

### SC-005: Dashboard Shows Data
Dashboard at https://d2z9uvoj5xlbd2.cloudfront.net shows:
- Total Items > 0
- Positive/Neutral/Negative counts > 0

## Out of Scope

- Container image migration (ADR-005 Phase 2)
- INT8 quantized model optimization
- Provisioned Concurrency (blocked by ephemeral storage >512 MB)
- Lambda SnapStart (Python not supported)
- CloudWatch warming events

## Dependencies

- PR #446 merged (s3:HeadObject permission) - DONE
- PRs #441-445 merged (self-healing) - DONE
- AWS credentials with S3 write access

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| HuggingFace download fails | LOW | HIGH | Script has error handling, can retry |
| S3 upload fails | LOW | HIGH | Script verifies upload, can retry |
| Model hash mismatch | LOW | MEDIUM | Script warns but continues |
| Lambda still OOMs at 2048 MB | VERY LOW | HIGH | Monitor CloudWatch, can increase further |

## Implementation Approach

### Phase 1: Upload Model (Manual, One-Time)
1. Run `./infrastructure/scripts/build-and-upload-model-s3.sh`
2. Verify S3 object exists
3. This is a manual operation, not part of CI/CD

### Phase 2: Increase Lambda Memory (Terraform)
1. Update `infrastructure/terraform/modules/lambda/main.tf`
2. Change Analysis Lambda memory from 1024 to 2048
3. Create PR, merge, deploy

### Phase 3: Verify End-to-End
1. Invoke ingestion Lambda (triggers self-healing)
2. Wait for Analysis Lambda to process items
3. Check DynamoDB for sentiment attribute
4. Check dashboard for non-zero counts
