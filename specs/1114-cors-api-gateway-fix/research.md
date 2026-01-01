# Research: CORS API Gateway Fix

**Feature**: 1114-cors-api-gateway-fix
**Date**: 2026-01-01

## Research Questions

### Q1: Why do browser requests fail while curl succeeds?

**Decision**: CORS is a browser-only security mechanism. Curl doesn't enforce CORS.

**Rationale**:
- Browser sends OPTIONS preflight → Gets CORS headers from API Gateway mock → Proceeds
- Browser sends GET/POST → Lambda response via AWS_PROXY has NO CORS headers → Browser blocks
- Curl bypasses CORS entirely (no Origin header enforcement)

**Evidence**:
```bash
# OPTIONS preflight - HAS CORS headers
curl -X OPTIONS "https://yikrqu13lj.execute-api.us-east-1.amazonaws.com/v1/api/v2/runtime"
# Returns: access-control-allow-origin: *

# GET request - NO CORS headers
curl -D - "https://yikrqu13lj.execute-api.us-east-1.amazonaws.com/v1/api/v2/runtime"
# Returns: 200 OK with body, but NO access-control-allow-origin header
```

### Q2: Why doesn't API Gateway add CORS headers to Lambda responses?

**Decision**: AWS_PROXY integration bypasses API Gateway response mapping.

**Rationale**:
- `type = "AWS_PROXY"` means Lambda returns complete HTTP response
- API Gateway passes Lambda response through unchanged
- No `aws_api_gateway_integration_response` applies to proxy integrations
- This is intentional AWS design for "pass-through" behavior

**Alternatives Considered**:
1. Switch to regular integration (non-proxy) - Rejected: Would require response template mapping
2. Add method_response/integration_response - Rejected: Doesn't work with AWS_PROXY

### Q3: Where IS CORS configured correctly?

**Decision**: Lambda Function URL has proper CORS configuration in Terraform.

**Rationale**:
From `infrastructure/terraform/main.tf` lines 440-458:
```terraform
function_url_cors = {
  allow_credentials = false
  allow_headers     = ["content-type", "authorization", "x-api-key", "x-user-id", "x-auth-type"]
  allow_methods     = ["GET", "POST", "PUT", "PATCH", "DELETE"]
  allow_origins     = var.cors_allowed_origins or localhost fallback
  expose_headers    = ["x-ratelimit-limit", "x-ratelimit-remaining", ...]
  max_age           = 86400
}
```

AWS Lambda Function URL natively handles CORS at infrastructure level - no code needed.

### Q4: Why doesn't Lambda add CORS headers in code?

**Decision**: Intentionally removed to prevent duplicate headers.

**Rationale**:
From `src/lambdas/dashboard/handler.py` line 45:
```python
# CORSMiddleware removed - CORS handled by Lambda Function URL
# DO NOT add CORSMiddleware here - it causes duplicate Access-Control-Allow-Origin headers
# which browsers reject with "Failed to fetch" errors.
```

The `get_cors_headers()` function in middleware returns empty dict (deprecated).

### Q5: What is the simplest fix?

**Decision**: Change `NEXT_PUBLIC_API_URL` in Amplify to use Lambda Function URL.

**Rationale**:
- Lambda Function URL already has CORS configured correctly
- Single Terraform variable change
- No code changes required
- No Lambda redeployment needed
- Only Amplify rebuild required (automatic on env var change)

**Alternatives Considered**:
1. Add API Gateway integration responses - Rejected: Requires migrating from AWS_PROXY
2. Add conditional CORS in Lambda code - Rejected: Code change, deployment, complexity
3. Use CloudFront with custom headers - Rejected: Overkill for this issue

## Current vs Target Architecture

### Current (Broken)
```
Browser → Amplify (NEXT_PUBLIC_API_URL=API Gateway)
       → API Gateway /v1/api/v2/*
       → Lambda (AWS_PROXY, no CORS headers)
       → Response missing CORS headers
       → Browser BLOCKS ❌
```

### Target (Fixed)
```
Browser → Amplify (NEXT_PUBLIC_API_URL=Lambda Function URL)
       → Lambda Function URL (has CORS config)
       → Lambda response + CORS headers added by AWS
       → Response HAS CORS headers
       → Browser ALLOWS ✅
```

## Files Verified

| File | Finding |
|------|---------|
| `infrastructure/terraform/modules/api_gateway/main.tf` | OPTIONS has CORS; Lambda proxy has none |
| `infrastructure/terraform/main.tf:440-458` | Lambda Function URL CORS properly configured |
| `infrastructure/terraform/modules/amplify/main.tf:59` | Uses `var.api_gateway_url` (needs change) |
| `src/lambdas/dashboard/handler.py:45` | CORS middleware intentionally removed |
| `src/lambdas/shared/middleware/security_headers.py:70` | `get_cors_headers()` returns empty dict |

## Conclusion

The infrastructure is correctly designed for Lambda Function URL CORS, but frontend was misconfigured to use API Gateway. Fix is simple: redirect frontend to Lambda Function URL.
