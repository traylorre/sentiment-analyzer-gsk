# Feature 1296: Tasks

## T-001: Rewrite CORS 404 test to use public route
File: `tests/e2e/test_cors_404_e2e.py`
- Change URL from `/api/v2/nonexistent-cors-test-route` to `/api/v2/tickers/nonexistent-cors-test`
- Remove JWT auth headers (no Authorization header needed)
- Remove `create_test_jwt` import and helper method

## AR#3
Lowest risk — test-only change, no infrastructure modification.
**READY FOR IMPLEMENTATION.**
