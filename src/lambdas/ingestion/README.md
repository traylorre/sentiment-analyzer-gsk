# Ingestion Lambda

## Purpose

Fetches financial news articles from Tiingo (primary) and Finnhub (secondary), deduplicates, stores in DynamoDB, publishes to SNS for analysis.

## Trigger

EventBridge schedule: Every 5 minutes

## Flow

```
EventBridge → Lambda → Tiingo/Finnhub → DynamoDB → SNS
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

# 2. Verify Tiingo API key
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo \
  --query 'SecretString' --output text | jq -r '.api_key' | head -c 8
# Should show first 8 chars of API key

# 3. Check EventBridge rule
aws events describe-rule --name dev-sentiment-ingestion-schedule
```

### Common Failures

| Error Code | Cause | Fix |
|------------|-------|-----|
| `RATE_LIMIT_EXCEEDED` | Tiingo/Finnhub 429 | Wait for rate limit reset |
| `SECRET_ERROR` | API key missing/invalid | Rotate key in Secrets Manager |
| `DATABASE_ERROR` | DynamoDB throttle | Check write capacity alarm |

## Configuration

- `WATCH_TAGS`: Comma-separated tags (max 5)
- `TIINGO_SECRET_ARN`: Tiingo API key secret path
- `FINNHUB_SECRET_ARN`: Finnhub API key secret path
- `SNS_TOPIC_ARN`: Topic for analysis requests

## Adapters

- `adapters/tiingo.py` - Tiingo implementation (primary source)
- `adapters/finnhub.py` - Finnhub implementation (secondary source)

Both adapters include:
- Exponential backoff on rate limits
- Circuit breaker after 3 consecutive failures
