# Implementation Plan: Feature 1007

## Overview

Two-phase implementation:
1. **Manual**: Run upload script to populate S3
2. **Terraform**: Increase Lambda memory via PR

## Phase 1: Upload Model to S3

### Step 1.1: Run Upload Script
**File**: `infrastructure/scripts/build-and-upload-model-s3.sh`

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
./infrastructure/scripts/build-and-upload-model-s3.sh
```

**Expected Output**:
- Downloads ~250 MB from HuggingFace
- Creates model.tar.gz
- Uploads to S3
- Verifies upload

### Step 1.2: Verify S3 Upload
```bash
aws s3 ls s3://sentiment-analyzer-models-218795110243/distilbert/v1.0.0/
```

**Expected**: Object exists with size ~250 MB

## Phase 2: Increase Lambda Memory

### Step 2.1: Find Memory Configuration
**File**: `infrastructure/terraform/modules/lambda/main.tf`

Search for Analysis Lambda resource and memory_size attribute.

### Step 2.2: Update Memory Value
Change from 1024 to 2048.

### Step 2.3: Create PR
- Branch: `A-upload-distilbert-model`
- Commit message: Descriptive
- Auto-merge enabled

## Phase 3: Verification

### Step 3.1: Invoke Self-Healing
```bash
aws lambda invoke --function-name preprod-sentiment-ingestion --payload '{}' /tmp/out.json
cat /tmp/out.json | jq '.body.self_healing'
```

**Expected**: `items_republished: 100`

### Step 3.2: Wait for Analysis
Wait 30-60 seconds for Analysis Lambda to process SNS messages.

### Step 3.3: Check CloudWatch Logs
```bash
aws logs tail /aws/lambda/preprod-sentiment-analysis --since 2m | grep -E "(Model loaded|sentiment)"
```

**Expected**: "Model loaded successfully" with load_time_ms

### Step 3.4: Check DynamoDB
```bash
aws dynamodb scan --table-name preprod-sentiment-items \
  --filter-expression "attribute_exists(sentiment)" \
  --select COUNT
```

**Expected**: Count > 0

### Step 3.5: Check Dashboard
Open https://d2z9uvoj5xlbd2.cloudfront.net

**Expected**: Non-zero counts for Total/Positive/Neutral/Negative

## Rollback Plan

### If Model Upload Fails
- Re-run script with `--no-verify` flag
- Manually download from HuggingFace and upload via AWS Console

### If Lambda OOMs at 2048 MB
- Increase to 3072 MB (same Terraform process)
- Consider INT8 quantized model (future optimization)

## Timeline

| Phase | Duration |
|-------|----------|
| Model upload | 5-10 min (includes HuggingFace download) |
| Terraform PR | 10-15 min (includes CI/CD) |
| Verification | 5-10 min |
| **Total** | **~30 min** |
