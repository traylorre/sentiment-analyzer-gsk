# Tasks: Feature 1314/1315

## Task 1: Add `_inject_cors_headers()` function

- **File**: `src/lambdas/dashboard/handler.py`
- **Location**: After `_make_not_found_response()` (after line 304), before `@app.not_found`
- **Action**: Add new function that:
  1. Extracts Origin from raw event headers (case-insensitive)
  2. Ensures `multiValueHeaders` exists on response dict
  3. Checks idempotency: if `Access-Control-Allow-Origin` already in response headers, return unchanged
  4. Always adds `Vary: ["Origin"]`
  5. If origin in `_CORS_ALLOWED_ORIGINS`, adds full CORS header set
  6. Returns mutated response dict
- **Depends on**: Nothing

## Task 2: Wire `_inject_cors_headers()` into `lambda_handler()`

- **File**: `src/lambdas/dashboard/handler.py`
- **Location**: Line 1738, after `response = app.resolve(event, context)`
- **Action**: Add call to `_inject_cors_headers(response, event)` between resolve and return
- **Depends on**: Task 1

## Task 3: Update module docstring (Feature 1315)

- **File**: `src/lambdas/dashboard/handler.py`
- **Location**: Lines 1-34 (module docstring)
- **Action**: Replace infrastructure-level CORS description with application-level post-processing description
- **Depends on**: Nothing (can parallel with Tasks 1-2)

## Task 4: Write unit tests

- **File**: `tests/unit/test_resolver_cors.py` (new)
- **Action**: Create test file with:
  1. `test_allowed_origin_gets_cors_headers` -- full lambda_handler invocation
  2. `test_disallowed_origin_no_cors_allow` -- unknown origin, Vary only
  3. `test_missing_origin_no_cors_allow` -- no Origin header
  4. `test_vary_origin_always_present` -- all cases have Vary
  5. `test_second_allowed_origin_reflected` -- multi-origin reflection
  6. `test_not_found_cors_not_duplicated` -- 404 route idempotency
  7. `test_no_wildcard_origin` -- ACAO never `*`
  8. `test_multivalue_headers_format` -- values are lists
- **Depends on**: Tasks 1-2

## Task 5: Validate existing tests still pass

- **Action**: Run `pytest tests/unit/test_cors_404_headers.py tests/unit/test_dashboard_handler.py -v`
- **Depends on**: Tasks 1-3
