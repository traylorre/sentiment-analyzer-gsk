# Feature 107: Fix CloudFront 403 AccessDenied for API Requests

## Problem Statement

CloudFront returns 403 AccessDenied (S3 XML error) when accessing API endpoints like `/api/v2/auth/anonymous`. The Interview Dashboard "Execute" buttons fail with "Error: Failed to fetch".

## Root Cause Analysis

### Current State
1. CloudFront receives request: `GET /api/v2/auth/anonymous`
2. Cache behavior `/api/*` routes to `api-gateway` origin ✓
3. CloudFront forwards `/api/v2/auth/anonymous` to API Gateway (no `origin_path`)
4. API Gateway expects stage prefix: `/v1/api/v2/auth/anonymous`
5. API Gateway returns 403 ForbiddenException (missing stage)
6. CloudFront custom_error_response maps 403 → fetch `/index.html` from S3
7. S3 returns 403 AccessDenied (manifest as XML error to client)

### Evidence
```bash
# Direct API Gateway WITH stage prefix - works:
$ curl -s "https://yikrqu13lj.execute-api.us-east-1.amazonaws.com/v1/api/v2/auth/anonymous"
{"detail":"Method Not Allowed"}  # FastAPI response (expected for GET)

# Direct API Gateway WITHOUT stage prefix - fails:
$ curl -I "https://yikrqu13lj.execute-api.us-east-1.amazonaws.com/api/v2/auth/anonymous"
HTTP/2 403
x-amzn-errortype: ForbiddenException

# CloudFront - fails with S3 error:
$ curl -I "https://d2z9uvoj5xlbd2.cloudfront.net/api/v2/auth/anonymous"
server: AmazonS3
content-type: application/xml
```

### Current CloudFront Configuration
```json
{
  "Origins": [
    {"Id": "s3-dashboard", "OriginPath": ""},
    {"Id": "api-gateway", "DomainName": "yikrqu13lj.execute-api.us-east-1.amazonaws.com", "OriginPath": ""}
  ]
}
```

**Missing**: `OriginPath: "/v1"` on api-gateway origin.

## Solution

Add `origin_path = "/v1"` to the API Gateway origin in CloudFront module.

**Why not remove the stage?** REST API (current) requires explicit stage names. Only HTTP API supports `$default` (stageless). Migration would be a larger change.

### Request Flow After Fix
```
User requests:       https://cloudfront.net/api/v2/auth/anonymous
CloudFront receives: /api/v2/auth/anonymous
CloudFront forwards: /v1/api/v2/auth/anonymous (origin_path prepended)
API Gateway stage:   v1 ✓ (validates, strips stage)
Lambda receives:     /api/v2/auth/anonymous
Response:            200 OK → User
```

**Note**: The `/v1` stage is invisible to users - it's an internal routing detail between CloudFront and API Gateway.

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|--------------|
| SC-001 | `curl https://d2z9uvoj5xlbd2.cloudfront.net/api/v2/auth/anonymous` returns JSON, not XML | Manual test |
| SC-002 | Interview Dashboard "Execute" buttons work | Manual test |
| SC-003 | No changes to API Gateway stage name | Code review |
| SC-004 | SSE endpoints still work via SSE Lambda | E2E tests |

## Implementation

### File Changes

1. **`modules/cloudfront/main.tf`**: Add `origin_path` to API Gateway origin
   ```hcl
   dynamic "origin" {
     for_each = var.api_gateway_domain != "" ? [1] : []
     content {
       domain_name = var.api_gateway_domain
       origin_id   = "api-gateway"
       origin_path = var.api_gateway_stage_path  # NEW: prepend stage
       custom_origin_config {
         http_port              = 80
         https_port             = 443
         origin_protocol_policy = "https-only"
         origin_ssl_protocols   = ["TLSv1.2"]
       }
     }
   }
   ```

2. **`modules/cloudfront/variables.tf`**: Add variable
   ```hcl
   variable "api_gateway_stage_path" {
     description = "API Gateway stage path to prepend to origin requests (e.g., /v1)"
     type        = string
     default     = ""
   }
   ```

3. **`main.tf`**: Pass stage path from api_gateway module
   ```hcl
   module "cloudfront" {
     # ... existing config ...
     api_gateway_stage_path = "/${module.api_gateway.stage_name}"
   }
   ```

4. **`modules/api_gateway/outputs.tf`**: Export stage name (if not already)
   ```hcl
   output "stage_name" {
     value = aws_apigatewayv2_stage.main.name
   }
   ```

## Test Plan

1. Deploy to preprod
2. Invalidate CloudFront cache: `aws cloudfront create-invalidation --distribution-id E14HOKHFRMG5XG --paths "/api/*"`
3. Test API endpoint: `curl https://d2z9uvoj5xlbd2.cloudfront.net/api/v2/auth/anonymous`
4. Verify Interview Dashboard Execute buttons
5. Run E2E tests

## Risks

| Risk | Mitigation |
|------|------------|
| Cache invalidation delay | Pre-create invalidation, wait for completion |
| Breaking other API paths | All `/api/*` routes use same stage, no impact |

## Dependencies

- None (CloudFront and API Gateway already deployed)
