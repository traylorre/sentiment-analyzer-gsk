# Implementation Plan: Feature 1314/1315

## Architecture Decision

**Option A: Post-process in lambda_handler** -- selected.

Single function `_inject_cors_headers()` called after `app.resolve()` in `lambda_handler()`.
Consistent with existing `_make_not_found_response()` pattern. ~20 lines of production code.

## File Changes

### 1. `src/lambdas/dashboard/handler.py` (modify)

#### 1a. New function: `_inject_cors_headers()`

Location: After `_make_not_found_response()` (around line 305), before the `@app.not_found`
decorator.

```python
def _inject_cors_headers(response: dict, event: dict) -> dict:
    """Add CORS headers to response if request origin is allowed.

    Feature 1314: Post-processes all responses from app.resolve() to add
    CORS headers. This is necessary because Powertools CorsConfig only
    supports a single allow_origin string, but this application needs
    multi-origin support (Amplify + localhost).

    Idempotent: skips injection if Access-Control-Allow-Origin is already
    present (e.g., from _make_not_found_response via @app.not_found).

    Args:
        response: API Gateway REST v1 proxy response dict from app.resolve().
        event: Raw Lambda event dict (for Origin header extraction).

    Returns:
        The response dict with CORS headers added (mutated in place).
    """
```

Logic:
1. Extract Origin from `event["headers"]` (case-insensitive lookup)
2. Get or create `multiValueHeaders` dict on response
3. Check if `Access-Control-Allow-Origin` already present (case-insensitive) -> skip if so
4. Always add `Vary: ["Origin"]`
5. If origin is in `_CORS_ALLOWED_ORIGINS`:
   - Add `Access-Control-Allow-Origin: [origin]`
   - Add `Access-Control-Allow-Credentials: ["true"]`
   - Add `Access-Control-Allow-Methods: ["GET,POST,PUT,DELETE,PATCH,OPTIONS"]`
   - Add `Access-Control-Allow-Headers: [<explicit list>]`
6. Return response

#### 1b. Modify `lambda_handler()`

At line 1738, after `response = app.resolve(event, context)`, add:

```python
    # Feature 1314: Add CORS headers to all responses.
    # Powertools CorsConfig only supports single origin; we need multi-origin.
    # This post-processes the response using _CORS_ALLOWED_ORIGINS (same set
    # used by _make_not_found_response for 404s).
    response = _inject_cors_headers(response, event)
```

#### 1c. Update module docstring (Feature 1315)

Replace lines 19-24 with accurate CORS description.

### 2. `tests/unit/test_resolver_cors.py` (new)

Test the full lambda_handler flow with CORS headers:

- Uses `make_event()` with `headers={"Origin": "https://example.com"}`
- Invokes `lambda_handler(event, context)`
- Asserts CORS headers present via `get_response_header()`

Test cases:
1. Allowed origin -> full CORS headers
2. Disallowed origin -> Vary only, no ACAO
3. Missing Origin header -> Vary only, no ACAO
4. Second allowed origin -> reflected correctly
5. 404 route (not_found handler) -> CORS headers present, not duplicated
6. No wildcard origin
7. multiValueHeaders format correct

### 3. No infrastructure changes

API Gateway gateway responses continue to handle OPTIONS preflight and gateway errors.
No Terraform changes needed.

## Dependency Order

1. Write `_inject_cors_headers()` function (no deps)
2. Wire into `lambda_handler()` (depends on #1)
3. Update docstring (no deps, can parallel with #1-2)
4. Write tests (depends on #1-2)

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| Origin header casing | Case-insensitive lookup in event headers |
| response missing multiValueHeaders | Create it if absent |
| Overwrite not_found CORS | Idempotency check on ACAO presence |
| EventBridge path | Returns before resolve(), no CORS needed |
| v2 rejection path | Returns before resolve(), no CORS needed |
