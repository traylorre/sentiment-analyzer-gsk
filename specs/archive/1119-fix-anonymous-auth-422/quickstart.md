# Quickstart: Fix Anonymous Auth 422 Error

**Feature**: 1119-fix-anonymous-auth-422
**Date**: 2026-01-02

## Testing the Fix

### Prerequisites

1. Dashboard Lambda deployed to dev/preprod
2. Lambda Function URL available

### Manual Testing

```bash
# Get the Lambda Function URL
LAMBDA_URL=$(aws lambda list-function-url-configs \
  --function-name dashboard-lambda \
  --query 'FunctionUrlConfigs[0].FunctionUrl' \
  --output text)

# Test 1: No body (should now return 201, was returning 422)
curl -X POST "$LAMBDA_URL/api/v2/auth/anonymous" \
  -H "Content-Type: application/json" \
  -w "\nHTTP Status: %{http_code}\n"

# Test 2: Empty body (should return 201)
curl -X POST "$LAMBDA_URL/api/v2/auth/anonymous" \
  -H "Content-Type: application/json" \
  -d '{}' \
  -w "\nHTTP Status: %{http_code}\n"

# Test 3: Body with custom timezone (should return 201)
curl -X POST "$LAMBDA_URL/api/v2/auth/anonymous" \
  -H "Content-Type: application/json" \
  -d '{"timezone": "Europe/London"}' \
  -w "\nHTTP Status: %{http_code}\n"
```

### Expected Responses

All three tests should return HTTP 201 with a response like:
```json
{
  "user_id": "uuid-here",
  "auth_type": "anonymous",
  "created_at": "2026-01-02T00:00:00Z",
  "session_expires_at": "2026-02-01T00:00:00Z",
  "storage_hint": "localStorage"
}
```

### Unit Tests

```bash
cd /home/traylorre/projects/sentiment-analyzer-gsk
pytest tests/unit/test_dashboard_handler.py -k "anonymous" -v
```

### Browser Testing

1. Open browser DevTools (F12)
2. Go to Network tab
3. Navigate to dashboard URL in incognito window
4. Verify POST /api/v2/auth/anonymous returns 201 (not 422)

## Verification Checklist

- [ ] No body → 201 Created
- [ ] Empty body `{}` → 201 Created
- [ ] Body with timezone → 201 Created with provided timezone
- [ ] Response contains all required fields
- [ ] Frontend loads without auth errors
