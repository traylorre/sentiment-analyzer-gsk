# Lambda Functions

## Overview

Each Lambda has a single responsibility in the sentiment analysis pipeline:

| Lambda | Trigger | Purpose | Memory | Timeout | Concurrency |
|--------|---------|---------|--------|---------|-------------|
| ingestion | EventBridge (5min) | Fetch Tiingo/Finnhub articles | 512MB | 60s | 1 |
| analysis | SNS | Run DistilBERT inference | 1024MB | 30s | 5 |
| dashboard | Function URL | Serve UI + API | 512MB | 60s | 10 |

## For On-Call Engineers

### Quick Diagnostics

```bash
# Check Lambda errors (replace FUNCTION_NAME)
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-FUNCTION_NAME \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# Check invocation count
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Invocations \
  --dimensions Name=FunctionName,Value=dev-sentiment-FUNCTION_NAME \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

### Common Issues

1. **Cold starts** - Analysis Lambda may take 5-10s on first invocation (model loading)
2. **Throttling** - Check reserved concurrency limits above
3. **Timeouts** - Analysis must complete within 30s; dashboard within 60s

## For Developers

### Adding a New Lambda

1. Create directory under `lambdas/`
2. Implement `handler.py` with `lambda_handler(event, context)`
3. Add unit tests in `tests/unit/test_{name}_handler.py`
4. Add Terraform in `infrastructure/terraform/` (Phase 6)

### Environment Variables

All Lambdas receive:
- `DYNAMODB_TABLE` - Table name
- `MODEL_VERSION` - Sentiment model version

Lambda-specific:
- Ingestion: `WATCH_TAGS`, `SNS_TOPIC_ARN`, `TIINGO_SECRET_ARN`, `FINNHUB_SECRET_ARN`
- Dashboard: `DASHBOARD_API_KEY_SECRET_ARN`
