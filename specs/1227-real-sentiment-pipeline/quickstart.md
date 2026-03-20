# Quickstart: Real Sentiment Pipeline

## Prerequisites

- AWS credentials with Lambda invoke + DynamoDB read permissions
- Python 3.13 with project dependencies installed
- Access to preprod environment

## Verification Steps

### Step 1: Verify Ingestion Lambda Fix

```bash
# Before fix — expect FunctionError
aws lambda invoke --function-name preprod-sentiment-ingestion \
  --region us-east-1 --payload '{}' /tmp/ingestion.json 2>&1
cat /tmp/ingestion.json
# Expected (before): {"errorMessage": "Unable to import module 'handler': No module named 'aws_lambda_powertools'"}

# After fix — expect success
aws lambda invoke --function-name preprod-sentiment-ingestion \
  --region us-east-1 --payload '{}' /tmp/ingestion.json 2>&1
cat /tmp/ingestion.json
# Expected (after): {"statusCode": 200, "body": {"articles_processed": N, ...}}
```

### Step 2: Verify Data Flowing

```bash
# Check for records with today's date
aws dynamodb query --table-name preprod-sentiment-timeseries \
  --key-condition-expression "PK = :pk AND SK >= :today" \
  --expression-attribute-values '{":pk": {"S": "AAPL#24h"}, ":today": {"S": "2026-03-20"}}' \
  --region us-east-1 --select COUNT
# Expected: Count > 0 within 30 minutes of fix deployment
```

### Step 3: Verify History Endpoint Returns Real Data

```bash
# Create session and query sentiment history
TOKEN=$(curl -s -X POST "$DASHBOARD_URL/api/v2/auth/anonymous" \
  -H "Content-Type: application/json" -d '{}' | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

curl -s -D /tmp/sent_headers.txt \
  "$DASHBOARD_URL/api/v2/tickers/AAPL/sentiment/history?range=1M" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -20

# Check cache header
grep -i 'x-cache-source' /tmp/sent_headers.txt
# Expected: x-cache-source: persistent-cache
```

### Step 4: Verify Synthetic Code Removed

```bash
# Search for the sha256 RNG pattern — should return zero results
grep -r "hashlib.sha256.*ticker\|random.seed.*ticker_hash" src/lambdas/dashboard/ohlc.py
# Expected: no output (pattern removed)
```

### Step 5: Run Trace Inspection Diagnostic

```bash
# Re-run the v3 diagnostic to verify sentiment traces show DB reads
python scripts/trace_inspection_v3.py
# Expected: Sentiment trace > 1ms, shows DynamoDB subsegment
```

## Key Files

| File | Purpose |
|------|---------|
| `.github/workflows/deploy.yml` | Add `aws-lambda-powertools==3.7.0` to ingestion pip install |
| `src/lambdas/dashboard/ohlc.py` | Replace synthetic generator with DynamoDB query |
| `src/lambdas/shared/cache/sentiment_cache.py` | New: in-memory cache + CacheStats for sentiment history |
| `tests/unit/test_sentiment_history.py` | New: unit tests for query + cache logic |
