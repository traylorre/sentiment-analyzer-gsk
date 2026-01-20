# Ingestion Lambda

## Purpose

Fetches financial news from Tiingo and market data from Finnhub, deduplicates, stores in DynamoDB, publishes to SNS for analysis.

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

# 2. Verify Tiingo/Finnhub API keys
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo \
  --query 'SecretString' --output text | jq -r '.api_key' | head -c 8
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/finnhub \
  --query 'SecretString' --output text | jq -r '.api_key' | head -c 8
# Should show first 8 chars of each API key

# 3. Check EventBridge rule
aws events describe-rule --name dev-sentiment-ingestion-schedule
```

### Common Failures

| Error Code | Cause | Fix |
|------------|-------|-----|
| `RATE_LIMIT_EXCEEDED` | Tiingo (500/day) or Finnhub (60/min) 429 | Wait for rate limit reset |
| `SECRET_ERROR` | API key missing/invalid | Rotate key in Secrets Manager |
| `DATABASE_ERROR` | DynamoDB throttle | Check write capacity alarm |

## Configuration

- `WATCH_TAGS`: Comma-separated tags (max 5)
- `TIINGO_SECRET_ARN`: Secret path for Tiingo API key
- `FINNHUB_SECRET_ARN`: Secret path for Finnhub API key
- `SNS_TOPIC_ARN`: Topic for analysis requests

## Adapters

`adapters/tiingo.py` - Tiingo API implementation with:
- Exponential backoff on rate limits (500 requests/day limit)
- Circuit breaker after 3 consecutive failures
- Financial news aggregation

`adapters/finnhub.py` - Finnhub API implementation with:
- Exponential backoff on rate limits (60 requests/minute limit)
- Circuit breaker after 3 consecutive failures
- Market data and news feed
