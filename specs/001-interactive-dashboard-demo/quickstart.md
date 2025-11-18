# Quickstart Guide: Interactive Dashboard Demo

**Feature**: `001-interactive-dashboard-demo` | **Date**: 2025-11-16

## Overview

This guide walks you through setting up, deploying, and demoing the interactive sentiment analysis dashboard from scratch.

**Timeline**: 2-4 hours for full setup and deployment

---

## Prerequisites

### Required Tools

- **AWS CLI** (v2.x): `aws --version`
- **Terraform** (v1.5+): `terraform --version`
- **Python** (3.11): `python3.11 --version`
- **Docker** (for Lambda layers): `docker --version`
- **Git**: `git --version`

### AWS Account Setup

1. **AWS Account** with admin access
2. **AWS credentials** configured:
   ```bash
   aws configure
   # Enter: Access Key, Secret Key, Region (us-east-1), Output (json)
   ```

3. **NewsAPI Key**:
   - Register at https://newsapi.org/register
   - Copy API key (free tier: 100 requests/day)

---

## Step 1: Store Secrets in AWS Secrets Manager

**Important**: Store secrets before deployment (required by Lambda functions)

### NewsAPI Key

```bash
# Store NewsAPI key (dev environment)
aws secretsmanager create-secret \
    --name dev/sentiment-analyzer/newsapi \
    --description "NewsAPI key for sentiment analyzer demo" \
    --secret-string "{\"api_key\":\"YOUR_NEWSAPI_KEY_HERE\"}" \
    --region us-east-1

# Verify stored
aws secretsmanager get-secret-value \
    --secret-id dev/sentiment-analyzer/newsapi \
    --region us-east-1 \
    --query SecretString \
    --output text
```

**Expected output**:
```json
{"api_key":"your-key-here"}
```

### Dashboard API Key

```bash
# Generate a secure API key
DASHBOARD_KEY=$(openssl rand -hex 32)
echo "Dashboard API Key: $DASHBOARD_KEY"

# Store dashboard API key (dev environment)
aws secretsmanager create-secret \
    --name dev/sentiment-analyzer/dashboard-api-key \
    --description "API key for dashboard authentication" \
    --secret-string "{\"api_key\":\"$DASHBOARD_KEY\"}" \
    --region us-east-1

# Verify stored
aws secretsmanager get-secret-value \
    --secret-id dev/sentiment-analyzer/dashboard-api-key \
    --region us-east-1 \
    --query SecretString \
    --output text
```

> **Note**: Save the dashboard API key - you'll need it to access the dashboard.

---

## Step 2: Clone Repository & Setup Local Environment

```bash
# Clone repo
git clone <your-repo-url>
cd sentiment-analyzer-gsk

# Checkout feature branch
git checkout 001-interactive-dashboard-demo

# Create Python virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For testing
```

### requirements.txt

```
boto3==1.34.0
transformers==4.35.0
torch==2.1.0
fastapi==0.104.0
mangum==0.17.0
requests==2.31.0
python-json-logger==2.0.7
```

### requirements-dev.txt

```
pytest==7.4.3
moto==4.2.0
pytest-asyncio==0.21.1
black==23.11.0
ruff==0.1.6
```

---

## Step 3: Build Model Lambda Layer

**Purpose**: Package HuggingFace DistilBERT model for Lambda to avoid cold start penalty

```bash
# Navigate to scripts directory
cd infrastructure/scripts

# Run model layer build script
./build-model-layer.sh

# Expected output:
# - downloads DistilBERT (~250MB)
# - creates model-layer.zip
# - uploads to S3: s3://sentiment-models-ACCOUNT_ID/layers/distilbert-v1.0.0.zip
```

### build-model-layer.sh

```bash
#!/bin/bash
set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="sentiment-models-${ACCOUNT_ID}"
LAYER_NAME="distilbert-v1.0.0"

echo "Building model layer: $LAYER_NAME"

# Create S3 bucket for model artifacts (if doesn't exist)
aws s3 mb s3://${BUCKET_NAME} --region us-east-1 2>/dev/null || true

# Create temporary directory
mkdir -p layer/python/model
cd layer

# Download DistilBERT model
python3.11 << EOF
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_name = "distilbert-base-uncased-finetuned-sst-2-english"
print(f"Downloading {model_name}...")

model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

model.save_pretrained("python/model")
tokenizer.save_pretrained("python/model")

print("Model saved to layer/python/model")
EOF

# Create layer zip
zip -r ../${LAYER_NAME}.zip python
cd ..

# Upload to S3
aws s3 cp ${LAYER_NAME}.zip s3://${BUCKET_NAME}/layers/${LAYER_NAME}.zip

echo "Model layer uploaded to s3://${BUCKET_NAME}/layers/${LAYER_NAME}.zip"

# Cleanup
rm -rf layer
```

**Make executable**:
```bash
chmod +x infrastructure/scripts/build-model-layer.sh
```

---

## Step 4: Deploy Infrastructure with Terraform

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Review plan
terraform plan -var="newsapi_secret_arn=arn:aws:secretsmanager:us-east-1:ACCOUNT_ID:secret:dev/sentiment-analyzer/newsapi-XXXXX"

# Deploy (takes ~5-10 minutes)
terraform apply -auto-approve

# Save outputs
terraform output -json > outputs.json
```

### Key Terraform Outputs

```bash
# Dashboard URL (open in browser)
terraform output dashboard_url

# DynamoDB table name
terraform output dynamodb_table_name

# Ingestion Lambda ARN
terraform output ingestion_lambda_arn
```

**Expected resources created**:
- 1 DynamoDB table (`sentiment-items`)
- 2 GSIs (`by_timestamp`, `by_model_version`)
- 3 Lambda functions (ingestion, analysis, dashboard)
- 1 SNS topic (`sentiment-analysis-requests`)
- 1 EventBridge rule (10-minute scheduler)
- 1 Lambda Function URL (dashboard)
- IAM roles and policies

---

## Step 5: Verify Deployment

### Test 1: Check DynamoDB Table

```bash
aws dynamodb describe-table \
    --table-name sentiment-items \
    --query "Table.[TableName,TableStatus,ItemCount]" \
    --output table
```

**Expected**: `TableStatus: ACTIVE`, `ItemCount: 0` (initially empty)

### Test 2: Invoke Ingestion Lambda Manually

```bash
# Trigger first ingestion (should fetch ~500 articles from NewsAPI)
aws lambda invoke \
    --function-name sentiment-ingestion \
    --payload '{}' \
    response.json

# Check response
cat response.json | jq .
```

**Expected output** (response.json):
```json
{
  "statusCode": 200,
  "body": {
    "summary": {
      "tags_processed": 5,
      "articles_fetched": 487,
      "new_items": 23,
      "duplicates_skipped": 464,
      "errors": 0
    },
    "execution_time_ms": 3421
  }
}
```

### Test 3: Verify Items in DynamoDB

```bash
# Query recent items
aws dynamodb query \
    --table-name sentiment-items \
    --index-name by_timestamp \
    --key-condition-expression "source_type = :st" \
    --expression-attribute-values '{":st":{"S":"newsapi"}}' \
    --scan-index-forward false \
    --limit 5
```

**Expected**: 5-25 items returned (depends on ingestion)

### Test 4: Open Dashboard

```bash
# Get dashboard URL
DASHBOARD_URL=$(terraform output -raw dashboard_url)

# Open in browser (macOS)
open $DASHBOARD_URL

# Or copy URL and paste in browser
echo $DASHBOARD_URL
```

**Expected**:
- Dashboard loads with charts
- Metrics show total items (23+)
- Recent items table populated
- SSE connection status: "● Live" (green)

---

## Step 6: Configure Watch Tags

**Current Implementation**: Tags are hardcoded in Lambda environment variables

### Update Watch Tags

```bash
# Update ingestion Lambda environment
aws lambda update-function-configuration \
    --function-name sentiment-ingestion \
    --environment "Variables={WATCH_TAGS='AI,climate,economy,health,sports',DYNAMODB_TABLE=sentiment-items,MODEL_VERSION=v1.0.0}"

# Verify update
aws lambda get-function-configuration \
    --function-name sentiment-ingestion \
    --query "Environment.Variables.WATCH_TAGS"
```

**Demo Day**: Update tags to interviewer's 5 choices before demo!

---

## Step 7: Seed Data for Integration Tests (Optional)

**Note**: Only for testing, NOT for demo (demo must use live data)

```bash
# Run seed script
cd infrastructure/scripts
python3 seed_data.py --count 100 --source newsapi
```

### seed_data.py

```python
#!/usr/bin/env python3
import boto3
import random
from datetime import datetime, timedelta
import hashlib

dynamodb = boto3.client('dynamodb')
TABLE_NAME = 'sentiment-items'

SAMPLE_TEXTS = [
    "Market rallies on positive economic data",
    "Climate summit reaches historic agreement",
    "New AI model achieves breakthrough performance",
    "Healthcare costs continue to rise",
    "Sports team wins championship"
]

TAGS = ['AI', 'climate', 'economy', 'health', 'sports']
SENTIMENTS = ['positive', 'neutral', 'negative']

def seed_item():
    text = random.choice(SAMPLE_TEXTS)
    sentiment = random.choice(SENTIMENTS)
    score = random.uniform(0.6, 0.99)

    source_id = f"newsapi#{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    timestamp = (datetime.utcnow() - timedelta(hours=random.randint(0, 24))).isoformat() + 'Z'

    dynamodb.put_item(
        TableName=TABLE_NAME,
        Item={
            'source_id': {'S': source_id},
            'ingested_at': {'S': timestamp},
            'source_type': {'S': 'newsapi'},
            'text_snippet': {'S': text},
            'sentiment': {'S': sentiment},
            'score': {'N': str(score)},
            'model_version': {'S': 'v1.0.0'},
            'matched_tags': {'SS': random.sample(TAGS, k=random.randint(1, 3))}
        }
    )

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--source', default='newsapi')
    args = parser.parse_args()

    for i in range(args.count):
        seed_item()
        if (i+1) % 10 == 0:
            print(f"Seeded {i+1}/{args.count} items")

    print(f"Seeded {args.count} items to {TABLE_NAME}")
```

---

## Step 8: Run Integration Tests

```bash
# Navigate to project root
cd /path/to/sentiment-analyzer-gsk

# Run all tests
pytest tests/integration/ -v

# Run specific test
pytest tests/integration/test_ingestion_flow.py::test_end_to_end -v
```

**Expected**: All tests pass ✅

---

## Demo Day Checklist

### 30 Minutes Before Demo

1. **Update watch tags** to interviewer's 5 choices:
   ```bash
   aws lambda update-function-configuration \
       --function-name sentiment-ingestion \
       --environment "Variables={WATCH_TAGS='TAG1,TAG2,TAG3,TAG4,TAG5',DYNAMODB_TABLE=sentiment-items,MODEL_VERSION=v1.0.0}"
   ```

2. **Trigger manual ingestion** to populate fresh data:
   ```bash
   aws lambda invoke \
       --function-name sentiment-ingestion \
       --payload '{}' \
       /tmp/response.json
   ```

3. **Verify dashboard** has 20+ items:
   ```bash
   curl $(terraform output -raw dashboard_url)/api/metrics | jq .summary.total_items
   ```

4. **Open dashboard** in browser:
   ```bash
   open $(terraform output -raw dashboard_url)
   ```

5. **Check SSE connection**: Status should show "● Live" (green)

### During Demo

**Script**:

1. **Introduction** (1 min):
   > "I've built a real-time sentiment analysis system that ingests news articles, analyzes sentiment using a HuggingFace transformer model, and displays results in this live dashboard. Let me show you how it works with your tags."

2. **Collect tags** (30 sec):
   > "Can you give me 5 topics you'd like to track? For example: AI, climate, economy, health, sports."

3. **Update tags** (2 min - while chatting):
   - Open terminal, run `aws lambda update-function-configuration ...`
   - Trigger manual ingestion
   - Explain architecture while waiting

4. **Show dashboard** (5 min):
   - Point out time-series chart (ingestion rate)
   - Pie chart (sentiment distribution)
   - Bar chart (tag matches)
   - Recent items table updating in real-time
   - SSE connection status

5. **Drill into DynamoDB** (2 min):
   - Open AWS Console → DynamoDB → `sentiment-items`
   - Show items table, explain schema
   - Highlight `source_id` (deduplication), `sentiment`, `score`, `model_version`

6. **Explain architecture** (3 min):
   - EventBridge triggers ingestion Lambda every 10 minutes
   - NewsAPI fetch → DynamoDB insert → SNS → Analysis Lambda
   - HuggingFace DistilBERT model (100-150ms inference)
   - FastAPI dashboard with Server-Sent Events for real-time updates

7. **Q&A** (5 min):
   - Common questions:
     - "Why 10-minute polling?" → NewsAPI free tier rate limit
     - "How does SSE work?" → Long-lived HTTP connection, server pushes updates
     - "Model accuracy?" → 91% on SST-2 benchmark, sufficient for demo
     - "Cost?" → $3.50-8.50/month for demo scale

---

## Local Development

### Run Dashboard Locally

```bash
# Set environment variables
export DYNAMODB_TABLE=sentiment-items
export AWS_REGION=us-east-1

# Run FastAPI with uvicorn
cd src/lambdas/dashboard
uvicorn handler:app --reload --port 8000

# Open browser
open http://localhost:8000
```

### Run Tests Locally

```bash
# Unit tests (with mocks)
pytest tests/unit/ -v

# Integration tests (requires AWS credentials)
pytest tests/integration/ -v

# Coverage report
pytest --cov=src --cov-report=html
open htmlcov/index.html
```

---

## Troubleshooting

### Issue: Dashboard shows "● Disconnected"

**Cause**: SSE connection failed or Lambda timed out

**Fix**:
```bash
# Check Lambda logs
aws logs tail /aws/lambda/sentiment-dashboard --follow

# Verify Function URL is accessible
curl $(terraform output -raw dashboard_url)/api/metrics
```

### Issue: No new items appearing

**Cause**: Ingestion Lambda not running or NewsAPI rate limited

**Fix**:
```bash
# Check ingestion logs
aws logs tail /aws/lambda/sentiment-ingestion --follow

# Manually trigger ingestion
aws lambda invoke --function-name sentiment-ingestion --payload '{}' /tmp/response.json
cat /tmp/response.json
```

### Issue: Sentiment analysis errors

**Cause**: Model layer not loaded or out of memory

**Fix**:
```bash
# Check analysis Lambda logs
aws logs tail /aws/lambda/sentiment-analysis --follow

# Verify model layer attached
aws lambda get-function-configuration --function-name sentiment-analysis --query Layers

# Increase memory if needed
aws lambda update-function-configuration \
    --function-name sentiment-analysis \
    --memory-size 1024
```

### Issue: NewsAPI rate limit (429 errors)

**Cause**: Exceeded 100 requests/day free tier

**Fix**:
- Wait 24 hours for quota reset
- OR upgrade NewsAPI plan (paid tier)
- OR increase polling interval to 1 hour (reduce requests)

---

## Cleanup

### Destroy All Resources

```bash
# Navigate to Terraform directory
cd infrastructure/terraform

# Destroy infrastructure
terraform destroy -auto-approve

# Delete S3 model bucket (if created)
aws s3 rb s3://sentiment-models-ACCOUNT_ID --force

# Delete Secrets Manager secrets
aws secretsmanager delete-secret \
    --secret-id dev/sentiment-analyzer/newsapi \
    --force-delete-without-recovery

aws secretsmanager delete-secret \
    --secret-id dev/sentiment-analyzer/dashboard-api-key \
    --force-delete-without-recovery
```

**WARNING**: This deletes all data (DynamoDB items, Lambda functions, secrets, etc.)

---

## Next Steps

After successful Demo 1:

**Demo 2: Chaos Testing** (branch: `002-chaos-testing-demo`)
- Randomly disable Lambdas
- Simulate DynamoDB throttling
- Verify CloudWatch alarms trigger
- Demonstrate graceful degradation

**Demo 3: Auto-Scaling & Load Testing** (branch: `003-autoscaling-demo`)
- Generate traffic spike (1000 items/min)
- Observe Lambda auto-scaling
- Monitor CloudWatch metrics
- Demonstrate throughput alarms → auto-recovery

**Production Enhancements**:
- Cognito authentication
- Multi-source support (Twitter, Reddit)
- Advanced metric dimensions
- Terraform Cloud integration
- Model replay/comparison (OpenAI vs DistilBERT)

---

## Cost Estimate

**Monthly cost** (demo scale, 100-500 items/hour):

| Service | Cost |
|---|---|
| DynamoDB (on-demand) | $0.35 |
| Lambda (ingestion + analysis + dashboard) | $1-3 |
| Secrets Manager | $0.40 |
| CloudWatch Logs/Metrics | $0.50 |
| S3 (model artifacts) | $0.10 |
| **Total** | **$2.35-4.35** |

**Note**: Within AWS Free Tier for first 12 months!

---

## Support & Resources

- **Documentation**: `/specs/001-interactive-dashboard-demo/`
- **Architecture Diagrams**: `/diagrams/`
- **Troubleshooting**: See above or check CloudWatch Logs
- **Slack/Teams**: #sentiment-analyzer channel

---

## Appendix: Environment Variables Reference

### Ingestion Lambda

| Variable | Value |
|---|---|
| `WATCH_TAGS` | `"AI,climate,economy,health,sports"` |
| `DYNAMODB_TABLE` | `"sentiment-items"` |
| `NEWSAPI_SECRET_ARN` | `"arn:aws:secretsmanager:..."` |
| `MODEL_VERSION` | `"v1.0.0"` |
| `SNS_ANALYSIS_TOPIC_ARN` | `"arn:aws:sns:..."` |

### Analysis Lambda

| Variable | Value |
|---|---|
| `DYNAMODB_TABLE` | `"sentiment-items"` |
| `MODEL_PATH` | `"/opt/model"` |
| `MODEL_VERSION` | `"v1.0.0"` |

### Dashboard Lambda

| Variable | Value |
|---|---|
| `DYNAMODB_TABLE` | `"sentiment-items"` |
