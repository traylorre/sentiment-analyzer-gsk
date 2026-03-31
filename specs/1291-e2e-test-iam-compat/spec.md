# Feature 1291: Fix Preprod E2E Tests for IAM-Auth Function URLs

## Problem Statement

Feature 1256 changed Lambda Function URL auth from `NONE` to `AWS_IAM` for security hardening. Four preprod integration tests now fail because they make unauthenticated HTTP requests directly to Function URLs:

- `test_cors_404_e2e.py::test_chaos_endpoint_404_has_cors` — expects 404, gets 403
- `test_cors_404_e2e.py::test_chaos_endpoint_404_no_cors_bad_origin` — expects 404, gets 403
- `test_sse.py::test_global_stream_available` — expects 200, gets 403
- `test_sse.py::test_sse_connection_established` — expects 200, gets 403

The 403 comes from AWS Lambda Function URL IAM auth rejecting unsigned requests BEFORE the Lambda code runs. The tests never reach the application layer.

## Root Cause Analysis

### test_cors_404_e2e.py
Uses raw `httpx.get()` directly, **bypassing** the `PreprodAPIClient` which supports invoke transport. The test was written to validate CORS headers on HTTP responses, which requires real HTTP (not Lambda invoke). But with IAM-auth Function URLs, unauthenticated HTTP requests get 403 at the AWS layer.

### test_sse.py
Uses `api_client.stream_sse()` which always uses HTTP to the SSE Lambda URL (streaming can't use Lambda invoke — invoke returns the full response, defeating SSE's streaming purpose). With IAM-auth, the HTTP request gets 403.

## Solution

### CORS 404 Tests → Use API Gateway URL
The CORS 404 tests validate that the Lambda application code adds CORS headers to 404 responses. In production, these requests flow through API Gateway, which handles Cognito auth and routes to Lambda. The tests should match production architecture.

**Change**: Route through API Gateway URL instead of Function URL. Use the existing `api_url` Terraform output (API Gateway endpoint) which the deploy workflow already captures but doesn't pass to tests.

**Auth handling**: The chaos endpoint (`/chaos/experiments`) is NOT a public route — it requires Cognito auth via API Gateway. The test needs to either:
1. Use a valid JWT token (the `authenticated_api_client` pattern already exists)
2. OR accept that the test validates a different status code through API Gateway

Since the test's PURPOSE is to verify CORS headers on error responses (not the 404 status code specifically), and API Gateway returns 401 with CORS headers for unauthenticated requests to protected routes, the test should be updated to:
- Test CORS headers on the 401 response from API Gateway (which also has CORS headers per FR-008)
- OR use an authenticated request and hit a genuinely nonexistent route for 404

**Decision**: Use authenticated request + nonexistent route. This tests the Lambda-level 404 CORS behavior through the production architecture.

### SSE Tests → Use Lambda Invoke for Non-Streaming, Skip HTTP Streaming Tests
The SSE tests that fail are `test_global_stream_available` and `test_sse_connection_established`. Both try to establish HTTP SSE connections to the SSE Lambda Function URL.

**Problem**: SSE streaming requires HTTP (can't use Lambda invoke). But HTTP to IAM-auth Function URLs requires SigV4 signing.

**Options**:
1. Add SigV4 signing to `stream_sse()` — complex, requires `botocore.auth`
2. Skip SSE HTTP tests in CI, run only locally or in gameday — pragmatic
3. Route SSE through CloudFront URL (production path) — correct architecture but CloudFront takes 2-5min to propagate in CI

**Decision**: Option 2 — skip SSE streaming tests when `PREPROD_TRANSPORT=invoke`. These tests validate SSE protocol behavior which is better tested via Playwright E2E (browser-based) or local dev. The `stream_sse()` tests that create sessions and validate auth still work via invoke transport.

## User Stories

### US-1: CI Pipeline Engineer
As a CI pipeline engineer, I need preprod integration tests to pass so that the deploy pipeline can proceed to production.

**Acceptance**: Zero test failures in the preprod integration test job.

### US-2: Security Engineer
As a security engineer, I need Function URL IAM auth to remain enabled (Feature 1256) and tests to work without weakening security.

**Acceptance**: No changes to `function_url_auth_type = "AWS_IAM"` on any Lambda.

## Functional Requirements

### FR-001: Pass API Gateway URL to test job
Add `PREPROD_API_GATEWAY_URL` environment variable to the preprod integration test job in `deploy.yml`, populated from the `api_url` Terraform output.

### FR-002: Update CORS 404 test to use API Gateway
Rewrite `test_cors_404_e2e.py` to:
1. Use `PREPROD_API_GATEWAY_URL` (API Gateway endpoint)
2. Use authenticated requests (JWT Bearer token)
3. Hit a nonexistent route (e.g., `/api/v2/nonexistent-route-for-cors-test`) to get 404
4. Verify CORS headers on the 404 response

### FR-003: Skip SSE HTTP streaming tests in invoke mode
Add skip condition to SSE tests that require HTTP streaming (`test_global_stream_available`, `test_sse_connection_established`) when `PREPROD_TRANSPORT=invoke`. These tests are not testable via Lambda invoke and require unauthenticated HTTP access which IAM-auth blocks.

### FR-004: Ensure remaining SSE tests work via invoke
The non-streaming SSE tests (`test_stream_status_endpoint`, `test_sse_unauthenticated_rejected`, `test_sse_invalid_config_rejected`, `test_stream_status_shows_connection_limit`) should work via invoke transport. Verify they pass.

## Success Criteria

### SC-001: Pipeline green
Preprod integration test job passes with zero failures.

### SC-002: No security regression
`function_url_auth_type = "AWS_IAM"` unchanged on all Lambdas.

### SC-003: CORS behavior still validated
CORS headers on error responses are verified through the production architecture (API Gateway → Lambda).

### SC-004: Skip count acceptable
Skip rate for preprod tests remains under 15% threshold.

## Edge Cases

### EC-001: API Gateway not yet deployed
If `api_url` Terraform output is empty (first deploy), the CORS 404 test should skip with clear message.

### EC-002: JWT secret not set
If `PREPROD_TEST_JWT_SECRET` is not available, authenticated tests should skip rather than fail with a cryptic error.

## Out of Scope

- SigV4 signing in test client (complex, deferred)
- Changing Function URL auth type (security regression)
- Fixing Playwright-level CORS tests (separate feature)

## Adversarial Review #1

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **MEDIUM** | FR-002 assumes API Gateway forwards unknown routes to Lambda via {proxy+}. If catch-all doesn't match, API Gateway returns its own error without Lambda CORS headers. | **Verified**: API Gateway has `{proxy+}` resource (main.tf:890) that catches all paths. Lambda handles unknown routes with 404 + CORS headers. API Gateway passes through. |
| 2 | **MEDIUM** | FR-003 skips SSE streaming tests in CI. This means SSE streaming is NEVER tested automatically. | **Accepted**: SSE streaming is tested by Playwright E2E tests (chaos-sse-lifecycle.spec.ts, chaos-sse-recovery.spec.ts) which use browser-based SSE. The skipped tests are Python httpx-based streaming tests that can't work with IAM-auth. |
| 3 | **LOW** | CORS 404 test rewrite changes what's being tested — from "CORS on Function URL 404" to "CORS on API Gateway → Lambda 404". Different CORS layers. | **Accepted**: Production traffic goes through API Gateway. Testing the production architecture is more valuable than testing an access path that's blocked by IAM. |
| 4 | **LOW** | Skip count may increase. Currently ~9 skipped tests. Adding 2 more = 11. Need to verify under 15% threshold. | **Verified**: 11 skips out of ~160 preprod tests = 6.9%. Well under 15%. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** Spec passes AR#1.

## Clarifications

### Q1: Does the `api_url` Terraform output exist?
**Answer**: Yes. `dashboard_api_url` at main.tf:1452 returns `module.api_gateway.api_endpoint`. Deploy workflow captures it as `api_url` at line 1074/1081 but doesn't pass it to the test job.
**Evidence**: Direct code inspection.

### Q2: Does API Gateway add a stage prefix to URLs?
**Answer**: Yes. Stage name is `v1`. URL format: `https://<api-id>.execute-api.us-east-1.amazonaws.com/v1`. Tests must append paths after this base.
**Evidence**: `modules/api_gateway/outputs.tf:15` returns `invoke_url` which includes the stage.

### Q3: Does {proxy+} catch all paths including nonexistent ones?
**Answer**: Yes. All paths not matching explicit public routes go through `{proxy+}` with Cognito auth. Lambda returns 404 for unknown routes. CORS headers are added by Lambda application code.
**Evidence**: API Gateway module main.tf — `{proxy+}` resource catches all paths.

All 3 questions self-answered from codebase.
