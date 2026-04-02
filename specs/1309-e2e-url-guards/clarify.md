# Clarification -- Feature 1309: E2E URL Guards

## Questions Considered

### Q1: Should test_sentiment_history_regression.py be included?
**Analysis**: This file uses `os.environ.get("PREPROD_API_URL", "https://huiufpky5oy7wbh66jz5sutjme0mbcrb.lambda-url.us-east-1.on.aws")` -- a hardcoded fallback URL, not an empty string. It will never produce empty-string URL confusion.
**Decision**: Out of scope. Different failure mode (stale URL, not empty URL).

### Q2: Is the CORS origin fallback in test_cors_404_e2e.py actually correct?
**Analysis**: `PREPROD_CORS_ORIGIN` defaults to `"https://main.d29tlmksqcx494.amplifyapp.com"`. This is the actual Amplify deployment URL that must match Terraform's `cors_allowed_origins`. The test verifies that the API returns CORS headers for this specific origin. Changing the fallback would break the test's purpose.
**Decision**: Confirmed correct. No change needed.

### Q3: Should the ValueError in api_client.py include a check for whitespace-only URLs?
**Analysis**: `"   ".rstrip("/")` produces `"   "` which is truthy but not a valid URL. However, `os.environ.get()` never returns whitespace-only values from real environment variables. Env vars are either set (with real content) or unset (returning the default empty string). The `.rstrip("/")` only strips slashes, not whitespace.
**Decision**: Use `not self.base_url.strip()` would be over-defensive. `not self.base_url` (falsy check for empty string) matches the existing pattern across all reference files.

### Q4: Should the fixture guard use the same skip message format across all files?
**Analysis**: Reference files use varying messages:
- `"SSE_FUNCTION_URL not set"` (test_function_url_restricted.py)
- `"SSE_LAMBDA_URL not set"` (test_sse_connection_preprod.py)
- `"PROD_API_GATEWAY_URL not set"` (test_cors_prod_headers.py)
- `"PREPROD_API_URL / PREPROD_API_GATEWAY_URL not set"` (test_cors_404_e2e.py)

Pattern: `"<ENV_VAR_NAME> not set"`.
**Decision**: Use `"PREPROD_API_URL not set"` consistently for all 8 fixtures.

### Q5: Any additional files with the empty-string pattern?
**Analysis**: Grep for `os.environ.get.*""` across tests/e2e found no other files with the empty-string fallback pattern that lack guards. `test_function_url_restricted.py`, `test_sse_connection_preprod.py`, `test_cloudfront_sse.py`, and `test_cors_prod_headers.py` all already have guards.
**Decision**: The 3-file scope (cognito, waf, api_client) is complete.

## Spec Updates Required

None. All clarification questions confirmed the spec as written. No amendments needed.
