# Ingestion Lambda

## Purpose

Fetches articles from NewsAPI, deduplicates, stores in DynamoDB, publishes to SNS for analysis.

## Trigger

EventBridge schedule: Every 5 minutes

## Flow

```
EventBridge → Lambda → NewsAPI → DynamoDB → SNS
                         ↓
                   (deduplicate)
```

## For On-Call Engineers

### SOP Reference: SC-03 (Ingestion Failures)

**Alarm**: `${environment}-lambda-ingestion-errors`

### Quick Checks

```bash
# 1. Check recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-ingestion \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Verify NewsAPI key
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/newsapi \
  --query 'SecretString' --output text | jq -r '.api_key' | head -c 8
# Should show first 8 chars of API key

# 3. Check EventBridge rule
aws events describe-rule --name dev-sentiment-ingestion-schedule
```

### Common Failures

| Error Code | Cause | Fix |
|------------|-------|-----|
| `RATE_LIMIT_EXCEEDED` | NewsAPI 429 | Wait for rate limit reset (hourly) |
| `SECRET_ERROR` | API key missing/invalid | Rotate key in Secrets Manager |
| `DATABASE_ERROR` | DynamoDB throttle | Check write capacity alarm |

## Configuration

- `WATCH_TAGS`: Comma-separated tags (max 5)
- `NEWSAPI_SECRET_ARN`: Secret path for API key
- `SNS_TOPIC_ARN`: Topic for analysis requests

## Adapters

`adapters/newsapi.py` - NewsAPI implementation with:
- Exponential backoff on rate limits
- Circuit breaker after 3 consecutive failures
- 100 articles per request (max allowed)
