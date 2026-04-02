# Feature 1309: E2E URL Guards

## Problem

Four E2E test files silently accept empty-string URLs when required environment
variables (`PREPROD_API_URL`, `SSE_LAMBDA_URL`, etc.) are not set. Instead of
failing fast with `pytest.skip()`, the tests attempt HTTP requests to empty or
malformed URLs, producing confusing `httpx` connection errors that mask the
actual issue: missing environment configuration.

## Root Cause

The pattern `os.environ.get("PREPROD_API_URL", "").rstrip("/")` returns `""`
when the env var is unset. Tests then construct URLs like `"/api/v2/configurations"`
with no host, causing opaque connection failures instead of clear skip messages.

## Affected Files

| File | Issue |
|------|-------|
| `tests/e2e/test_cognito_auth.py` | `api_url` fixture (4 classes) returns empty string silently |
| `tests/e2e/test_waf_protection.py` | `api_url` fixture (4 classes) returns empty string silently |
| `tests/e2e/test_cors_404_e2e.py` | Has `skip_if_no_url` for API URL but hardcodes CORS origin fallback without validation |
| `tests/e2e/helpers/api_client.py` | `PreprodAPIClient.__init__` accepts empty `base_url` in HTTP transport mode |

## Correct Pattern (Already Exists)

Reference implementations in the same codebase:

- `test_function_url_restricted.py:38-39` -- inline guard: `if not url: pytest.skip("...")`
- `test_sse_connection_preprod.py:55-56` -- fixture guard: `if not SSE_LAMBDA_URL: pytest.skip("...")`
- `test_cors_prod_headers.py:37-39` -- fixture guard with `if not url: pytest.skip("...")`

## Requirements

### FR-001: api_url fixture guards
Add `if not url: pytest.skip("PREPROD_API_URL not set")` to every `api_url`
fixture in `test_cognito_auth.py` and `test_waf_protection.py`.

### FR-002: CORS origin validation
In `test_cors_404_e2e.py`, the `PREPROD_CORS_ORIGIN` variable falls back to
a hardcoded Amplify URL. This is intentional (the origin must match Terraform
config). No change needed -- the `skip_if_no_url` autouse fixture already
guards the API URL correctly.

### FR-003: PreprodAPIClient base_url validation
In `api_client.py`, add a `ValueError` when `base_url` resolves to empty
string and transport mode is `"http"`. Invoke mode does not use `base_url`
for HTTP requests, so it should be exempt.

### FR-004: No behavior change for configured environments
When environment variables are properly set, all tests must behave identically
to current behavior. Guards are skip-only, not assert-only.

## Out of Scope

- Changing the SkipInfo/skipif pattern at module level (already correct)
- Adding guards to files that already have them
- Modifying any test logic or assertions
- Adding new test cases

## Verification

- `pytest tests/e2e/test_cognito_auth.py --collect-only` with no env vars: all tests show SKIPPED
- `pytest tests/e2e/test_waf_protection.py --collect-only` with no env vars: all tests show SKIPPED
- `PreprodAPIClient(transport="http")` with no env vars: raises `ValueError`
- `PreprodAPIClient(transport="invoke")` with no env vars: no error (invoke bypasses HTTP)
