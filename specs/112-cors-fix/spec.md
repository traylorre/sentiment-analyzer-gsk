# Feature 112: Fix CORS for Interview Dashboard API Calls

## Problem Statement

The Interview Dashboard hosted on GitHub Pages (`traylorre.github.io`) cannot make API calls to the CloudFront distribution (`d2z9uvoj5xlbd2.cloudfront.net`) because:

1. Browser sends CORS preflight (OPTIONS) request
2. CloudFront forwards to API Gateway
3. API Gateway returns 405 (Method Not Allowed) without CORS headers
4. Browser blocks the actual request with "Error: failed to fetch"

## Root Cause

- Lambda Function URL has CORS configured, but requests come through CloudFront → API Gateway
- API Gateway REST API doesn't have native CORS handling for OPTIONS
- CloudFront doesn't add CORS headers to responses

## Solution

Add a CloudFront Response Headers Policy with CORS configuration for `/api/*` routes:

1. Create `aws_cloudfront_response_headers_policy.cors_api` resource
2. Configure CORS headers:
   - `Access-Control-Allow-Origin`: From `cors_allowed_origins` variable
   - `Access-Control-Allow-Methods`: GET, POST, PUT, DELETE, OPTIONS, PATCH
   - `Access-Control-Allow-Headers`: Authorization, Content-Type, X-User-ID, Accept, Origin
3. Attach policy to API Gateway cache behavior
4. Forward `X-User-ID` header to origin

## Changes

### infrastructure/terraform/modules/cloudfront/variables.tf
- Add `cors_allowed_origins` variable (list of strings)

### infrastructure/terraform/modules/cloudfront/main.tf
- Add `aws_cloudfront_response_headers_policy.cors_api` resource
- Attach `response_headers_policy_id` to API cache behavior
- Forward `X-User-ID` header to origin

### infrastructure/terraform/main.tf
- Pass `cors_allowed_origins` to cloudfront module

### interview/index.html
- Reorder Resilience section navigation: Chaos → Caching → Circuit → Traffic

## Success Criteria

| ID | Criterion | Verification |
|----|-----------| -------------|
| SC-001 | OPTIONS preflight returns CORS headers | curl -X OPTIONS with Origin header |
| SC-002 | POST /api/v2/auth/anonymous works from GitHub Pages | Browser test |
| SC-003 | Navigation order matches spec | Visual inspection |
| SC-004 | Terraform validates | `terraform validate` |

## Out of Scope

- Deploying dashboard to S3 (View Live Dashboard 403 issue)
- API Gateway native CORS configuration (more complex, not needed with CloudFront policy)
