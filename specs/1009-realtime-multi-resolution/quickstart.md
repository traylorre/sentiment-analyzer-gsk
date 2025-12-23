# Quickstart: Real-Time Multi-Resolution Sentiment Time-Series

**Feature**: 1009-realtime-multi-resolution
**Date**: 2025-12-21

## Prerequisites

- Python 3.13
- Terraform 1.5+
- AWS CLI configured
- Docker (for LocalStack)
- Node.js 18+ (for frontend)

## Local Development

### 1. Set up environment

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk

# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt
```

### 2. Run unit tests

```bash
# Run all timeseries-related tests
pytest tests/unit/test_timeseries*.py -v

# Run with coverage
pytest tests/unit/test_timeseries*.py --cov=src/lib/timeseries --cov-report=term-missing
```

### 3. Start LocalStack

```bash
# Start LocalStack for integration testing
make localstack-up

# Initialize Terraform with LocalStack
make tf-init-local

# Apply Terraform (creates tables)
make tf-apply-local
```

### 4. Run integration tests

```bash
# Run integration tests against LocalStack
pytest tests/integration/timeseries/test_timeseries_pipeline.py -v

# Clean up
make localstack-down
```

## API Usage

### Get Time-Series Data

```bash
# Get 1-minute resolution for AAPL
curl "https://{function-url}/api/v2/timeseries/AAPL?resolution=1m"

# Get 5-minute resolution with time range
curl "https://{function-url}/api/v2/timeseries/AAPL?resolution=5m&start=2025-12-21T10:00:00Z&end=2025-12-21T11:00:00Z"

# Get hourly resolution
curl "https://{function-url}/api/v2/timeseries/AAPL?resolution=1h"
```

### Subscribe to SSE Stream

```bash
# Subscribe to 1-minute and 5-minute updates for AAPL
curl -N "https://{function-url}/api/v2/stream?resolutions=1m,5m&tickers=AAPL"

# Subscribe to all resolutions for all tickers
curl -N "https://{function-url}/api/v2/stream?resolutions=1m,5m,10m,1h,3h,6h,12h,24h"
```

### Example SSE Events

```
event: heartbeat
id: evt_a1b2c3d4
data: {"timestamp":"2025-12-21T10:35:00Z","connections":42}

event: bucket_update
id: evt_x1y2z3a4
data: {"ticker":"AAPL","resolution":"1m","bucket":{"timestamp":"2025-12-21T10:35:00Z","open":0.72,"high":0.89,"low":0.45,"close":0.78,"count":12,"avg":0.72,"label_counts":{"positive":8,"neutral":3,"negative":1},"is_partial":false}}

event: partial_bucket
id: evt_p1q2r3s4
data: {"ticker":"AAPL","resolution":"1m","bucket":{"timestamp":"2025-12-21T10:36:00Z","open":0.65,"high":0.65,"low":0.65,"close":0.65,"count":1,"avg":0.65,"label_counts":{"positive":1,"neutral":0,"negative":0},"is_partial":true},"progress_pct":47}
```

## Infrastructure Deployment

### Deploy to Preprod

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan changes
terraform plan -var-file=env/preprod.tfvars

# Apply changes
terraform apply -var-file=env/preprod.tfvars
```

### Verify Deployment

```bash
# Check new table exists
aws dynamodb describe-table --table-name preprod-sentiment-timeseries

# Check Lambda environment variables
aws lambda get-function-configuration --function-name preprod-sse-streaming | jq '.Environment.Variables'
```

## Frontend Development

### Run Dashboard Locally

```bash
cd src/dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

### Test Resolution Switching

1. Open dashboard at http://localhost:3000
2. Select a ticker (e.g., AAPL)
3. Click resolution buttons (1m, 5m, 1h, etc.)
4. Verify instant switching (<100ms perceived delay)
5. Check IndexedDB cache in browser DevTools

## Troubleshooting

### Common Issues

**Issue**: Resolution switching slow (>100ms)

Check:
1. Lambda global cache hit rate in CloudWatch
2. IndexedDB cache in browser DevTools
3. Network latency to API

**Issue**: Partial bucket not updating

Check:
1. SSE connection status in browser DevTools
2. Lambda logs for polling errors
3. DynamoDB table has items with `is_partial=true`

**Issue**: Missing buckets at higher resolutions

Check:
1. Write fanout logic in ingestion Lambda
2. BatchWriteItem errors in CloudWatch
3. TTL not expired for lower resolutions

### Debug Commands

```bash
# Check SSE Lambda logs
aws logs tail /aws/lambda/preprod-sse-streaming --follow

# Check ingestion Lambda logs
aws logs tail /aws/lambda/preprod-ingestion --follow

# Query timeseries table directly
aws dynamodb query \
  --table-name preprod-sentiment-timeseries \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "AAPL#1m"}}' \
  --limit 10

# Check table item count
aws dynamodb scan \
  --table-name preprod-sentiment-timeseries \
  --select COUNT
```

## Performance Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Resolution switch latency | <100ms | Browser DevTools Network tab |
| Live update latency | <3s | Compare article timestamp to SSE event |
| Cache hit rate | >80% | Lambda CloudWatch metrics |
| API response time | <200ms | CloudWatch API Gateway metrics |

## Next Steps

After completing quickstart:

1. Run E2E tests: `pytest tests/e2e/test_multi_resolution_dashboard.py`
2. Monitor costs in AWS Cost Explorer
3. Review CloudWatch dashboards for performance
