# Feature 1296: Fix CORS 404 Test to Use Public Route

## Problem
`test_cors_404_e2e.py` sends a test JWT to `/api/v2/nonexistent-cors-test-route`. This falls through to `{proxy+}` which requires Cognito auth. API Gateway returns 401 (Cognito rejects the HS256 test JWT). Test expects 404.

## Fix
Hit a public route with `{proxy+}` instead: `/api/v2/tickers/nonexistent-cors-test`. The `/api/v2/tickers` route has `has_proxy = true, endpoint_auth = "NONE"` — Cognito is bypassed. The nonexistent sub-path reaches Lambda which returns 404 with CORS headers.

## FR-001
CORS 404 test uses `/api/v2/tickers/nonexistent-cors-test` (public proxy route, no auth needed).

## FR-002
Remove JWT auth headers from CORS 404 test. No `Authorization` header needed for public routes.

## SC-001
Both CORS 404 tests pass: `test_404_response_has_cors_headers`, `test_404_response_no_cors_for_unknown_origin`.

## Edge Cases
- EC-001: If `/api/v2/tickers` is removed from public routes in the future, test starts failing with 401. Acceptable — the test failure would correctly alert that CORS behavior changed.

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **MEDIUM** | Test depends on Feature 1295 (502 fix). Without the Lambda permission qualifier, even public routes return 502. | **Noted**: 1295 must deploy first. But both ship in same commit so this is automatic. |
| 2 | **LOW** | `/api/v2/tickers/nonexistent-cors-test` could theoretically match a future ticker symbol. | **Accepted**: No ticker API would match a path with hyphens. Ticker symbols are uppercase alphanumeric. |

**0 CRITICAL, 0 HIGH remaining.** Gate passes.

## Clarifications
All self-answered. Public route verified from main.tf:867.
