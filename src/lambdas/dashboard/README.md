# Dashboard Lambda

## Purpose

Serves the dashboard UI and API endpoints via Lambda Function URL.

## Trigger

HTTP requests via Function URL (CORS enabled)

## Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| GET | `/` | Serve index.html | None |
| GET | `/health` | Health check + DynamoDB connectivity | None |
| GET | `/api/metrics` | Aggregated sentiment metrics | API Key |
| GET | `/api/stream` | SSE real-time updates | API Key |

## For On-Call Engineers

### SOP Reference: SC-05 (Dashboard Failures), SC-12 (High Latency)

**Alarms**:
- `${environment}-lambda-dashboard-errors`
- `${environment}-dashboard-latency-high`

### Quick Checks

```bash
# 1. Check recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/dev-sentiment-dashboard \
  --filter-pattern "ERROR" \
  --start-time $(date -d '30 minutes ago' +%s)000

# 2. Test health endpoint
curl -s "https://YOUR_FUNCTION_URL/health" | jq

# 3. Verify API key secret
aws secretsmanager get-secret-value \
  --secret-id dev/sentiment-analyzer/dashboard-api-key \
  --query 'SecretString' --output text
```

### Common Failures

| Error Code | Cause | Fix |
|------------|-------|-----|
| 401 Unauthorized | Invalid API key | Check `X-API-Key` header matches secret |
| `DATABASE_ERROR` | DynamoDB query failed | Check GSI `by_status` exists |
| SSE timeout | Client disconnected | Normal behavior, client will reconnect |

## Authentication

API key passed via `X-API-Key` header, validated with `secrets.compare_digest()`
to prevent timing attacks.

**Security Note**: The `/health` endpoint is unauthenticated intentionally for
monitoring systems. It only returns connectivity status, no sensitive data.

## SSE Behavior

- Poll interval: 5 seconds
- Sends `data: {metrics}` events
- Client should handle reconnection on disconnect
