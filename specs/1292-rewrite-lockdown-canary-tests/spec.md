# Feature 1292: Rewrite Lockdown & Canary Tests for Invoke Transport

## Problem
20 preprod tests in 3 files use raw `requests.get()` to Lambda Function URLs. Feature 1256 changed Function URL auth to `AWS_IAM`, so unauthenticated HTTP requests get 403 before reaching Lambda code.

## Files & Test Counts
- `tests/integration/test_canary_preprod.py` — 6 HTTP tests (2 metadata tests already pass)
- `tests/e2e/test_admin_lockdown_preprod.py` — 8 tests
- `tests/e2e/test_chaos_lockdown_preprod.py` — 6 tests

## Solution
Rewrite all 20 tests to use `PreprodAPIClient` with invoke transport. The client already supports GET/POST/DELETE via `boto3 lambda.invoke()`, which bypasses Function URL auth entirely.

Key changes per file:
- Replace `import requests` with `PreprodAPIClient` import
- Replace `requests.get(f"{URL}/path")` with `await api_client.get("/path")`
- Convert test classes to use async fixtures (`api_client` from conftest.py)
- Remove `DASHBOARD_URL` env var dependency — client uses `PREPROD_API_URL` + invoke transport
- Add `@pytest.mark.asyncio` to all test methods

## Functional Requirements

### FR-001: Canary tests use invoke transport
All 6 HTTP-based canary tests (`test_canary_preprod.py`) use `PreprodAPIClient` instead of raw `requests`. Health endpoint tests verify structure, performance, idempotency, and concurrency through invoke.

### FR-002: Admin lockdown tests use invoke transport
All 8 admin lockdown tests (`test_admin_lockdown_preprod.py`) use `PreprodAPIClient`. These validate Feature 1249: admin routes return 404, health/runtime strip sensitive fields, auth required for protected endpoints.

### FR-003: Chaos lockdown tests use invoke transport
All 6 chaos lockdown tests (`test_chaos_lockdown_preprod.py`) use `PreprodAPIClient`. These validate Feature 1250: all chaos endpoints return 404 in preprod.

## Success Criteria
- SC-001: All 20 rewritten tests pass in CI with `PREPROD_TRANSPORT=invoke`
- SC-002: No `requests` or `httpx` imports remain in the 3 files (all use PreprodAPIClient)
- SC-003: No `DASHBOARD_URL` env var dependency in the 3 files

## Edge Cases
- EC-001: Canary concurrent request test — `asyncio.gather()` with invoke may behave differently than `concurrent.futures` with HTTP. Verify concurrency still works.
- EC-002: Response object differences — `LambdaResponse` vs `httpx.Response`. Both have `.status_code`, `.json()`, `.text` but `.headers` may differ. Canary tests that check response headers need adjustment.

## Adversarial Review #1

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | **HIGH** | `LambdaResponse` may not have `.headers` dict. Canary tests check Content-Type and other headers. | **Resolved**: Canary health check tests that assert response headers must be adjusted — invoke responses don't have HTTP headers (Lambda returns JSON body only). Remove header assertions from invoke-mode tests; header behavior is validated by `test_function_url_restricted.py` via HTTP. |
| 2 | **MEDIUM** | Canary performance test asserts `< 5s`. Invoke adds ~100ms cold start overhead. | **Accepted**: 100ms on a 5s budget is 2%. Unlikely to cause flakiness. Monitor after deploy. |
| 3 | **LOW** | Converting synchronous `requests` tests to async `PreprodAPIClient` changes concurrency behavior. | **Verified**: `PreprodAPIClient` supports `asyncio.gather()` for concurrent invoke calls. The canary concurrent test can use this. |

**0 CRITICAL, 0 HIGH remaining.** Gate passes.

## Out of Scope
- Canary performance assertions (invoke adds ~100ms overhead vs direct HTTP — timing thresholds may need relaxing but that's a tuning issue, not a rewrite issue)
