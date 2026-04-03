# Feature 1314/1315: Resolver CORS Post-Processing + Docstring Fix

## Problem Statement

The `APIGatewayRestResolver` at `handler.py:186` has no `CorsConfig`. As a result,
**successful Lambda responses have ZERO CORS headers**. Browsers silently block every
API response body (opaque CORS failure).

This was invisible because:
1. **Before Feature 1305**: All requests hit error paths returning 500. API Gateway
   gateway responses have CORS configured, so 4xx/5xx gateway errors included CORS.
   The browser never saw a successful response to reject.
2. **E2E tests use httpx**: No browser CORS enforcement. Tests pass but production fails.

### Why Powertools CorsConfig Cannot Solve This

Powertools `CorsConfig` only accepts a **single** `allow_origin` string. With
`allow_credentials=True`, the CORS spec forbids `*` (browsers reject it). This project
needs multi-origin support (Amplify production URL + localhost for dev).

The existing `_CORS_ALLOWED_ORIGINS` set (handler.py:109-115) already parses
comma-separated origins from the `CORS_ORIGINS` env var. The `_make_not_found_response()`
function (handler.py:260-304) already implements correct multi-origin CORS for 404
responses. We need to apply this same pattern to ALL responses.

## Scope

### In Scope

1. **Feature 1314**: Add CORS headers to ALL responses returned by `app.resolve()` in
   `lambda_handler()`, using the existing `_CORS_ALLOWED_ORIGINS` set and
   `_get_request_origin()` helper.

2. **Feature 1315**: Update the module docstring (handler.py:1-34) to accurately describe
   CORS architecture: Lambda application-level CORS via response post-processing, not
   infrastructure-level.

### Out of Scope

- Modifying API Gateway CORS configuration (gateway responses handle preflight/errors)
- Changing `_make_not_found_response()` (already correct)
- Changing `_CORS_ALLOWED_ORIGINS` parsing logic (already correct)
- Modifying router endpoints to add per-route CORS

## Approach: Option A -- Post-Process in lambda_handler

After `app.resolve(event, context)` returns the response dict at handler.py:1738, inject
CORS headers into the response based on the request Origin matching `_CORS_ALLOWED_ORIGINS`.

### Why Option A

| Option | Pros | Cons |
|--------|------|------|
| **A: Post-process in lambda_handler** | Single location, ~15 lines, leverages existing parsing, same pattern as `_make_not_found_response` | Not "framework-native" |
| B: Powertools middleware | Framework-native | Adds complexity, requires understanding middleware chain, same headers logic needed |
| C: CorsConfig single origin | Zero custom code | Breaks multi-origin, breaks localhost dev |

Option A wins on simplicity, correctness, and consistency with existing patterns.

### Implementation Details

**New function**: `_inject_cors_headers(response: dict, origin: str | None) -> dict`

- Extracts the Origin header from the event (via `_get_request_origin()` or directly
  from the event dict since we're outside Powertools context at this point)
- If origin is in `_CORS_ALLOWED_ORIGINS`, adds CORS headers to response
- Uses `multiValueHeaders` (v1 proxy format) since `APIGatewayRestResolver` returns v1
- Always adds `Vary: Origin` (cache correctness for CDN/proxies)
- Idempotent: if headers already present (e.g., from `_make_not_found_response`), does
  not overwrite

**CORS headers added** (same as `_make_not_found_response`):

```
Access-Control-Allow-Origin: <reflected-origin>
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET,POST,PUT,DELETE,PATCH,OPTIONS
Access-Control-Allow-Headers: Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID
Vary: Origin
```

**Injection point**: handler.py:1738-1748, between `app.resolve()` and `return response`.

### Response Format Handling

`APIGatewayRestResolver.resolve()` returns v1 proxy format:

```python
{
    "statusCode": 200,
    "multiValueHeaders": {"Content-Type": ["application/json"]},
    "body": "...",
    "isBase64Encoded": False,
}
```

The CORS injection must handle `multiValueHeaders` (dict of str -> list[str]).
It must also handle the edge case where `headers` (singular) exists instead.

### Idempotency

The `@app.not_found` handler and `_make_not_found_response()` already set CORS headers
on 404 responses. The post-processor must NOT overwrite these. Check: if
`Access-Control-Allow-Origin` is already present in the response, skip injection.

## Feature 1315: Docstring Fix

Update handler.py lines 1-34 to replace:

```
- CORS handled at infrastructure level (API Gateway gateway responses)
- Exception: env-gated 404 responses include application-level CORS
```

With:

```
- CORS handled at Lambda application level via response post-processing
  in lambda_handler() (Feature 1314). Supports multi-origin via
  _CORS_ALLOWED_ORIGINS parsed from CORS_ORIGINS env var.
- API Gateway gateway responses handle CORS for preflight (OPTIONS)
  and gateway errors (401/403/5xx).
```

## Acceptance Criteria

1. All successful API responses include correct CORS headers when Origin matches
2. Responses for non-matching/missing Origin include `Vary: Origin` but no CORS allow headers
3. Existing 404 CORS behavior (Feature 1268/1311) is preserved (idempotent)
4. Module docstring accurately describes CORS architecture
5. Unit tests cover: allowed origin, disallowed origin, missing origin, idempotency,
   multiValueHeaders format, Vary header always present
6. No `Access-Control-Allow-Origin: *` anywhere (credentials mode incompatible)

## Testing Strategy

### Unit Tests (new file: `tests/unit/test_resolver_cors.py`)

1. `test_cors_headers_added_for_allowed_origin` -- invoke lambda_handler with Origin in
   allowed list, verify CORS headers in response
2. `test_cors_headers_omitted_for_disallowed_origin` -- invoke with unknown origin
3. `test_cors_headers_omitted_for_missing_origin` -- invoke without Origin header
4. `test_vary_origin_always_present` -- Vary: Origin present regardless of origin match
5. `test_idempotent_with_not_found_cors` -- 404 response from not_found handler should
   not have duplicate/overwritten CORS headers
6. `test_no_wildcard_origin` -- ACAO never uses `*`
7. `test_second_allowed_origin_reflected` -- multi-origin: second origin reflected correctly
8. `test_multivalue_headers_format` -- CORS headers use list values in multiValueHeaders

### Existing Tests

- `test_cors_404_headers.py` -- continues to test `_make_not_found_response()` directly
- `test_dashboard_handler.py` -- existing handler tests should still pass

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Overwrite 404 CORS headers | Low | Medium | Idempotency check (skip if ACAO present) |
| Wrong header format (headers vs multiValueHeaders) | Low | High | Test with actual resolve() output |
| Origin extraction fails outside Powertools context | Medium | High | Extract from raw event dict, not app.current_event |
| EventBridge/v2 rejection paths miss CORS | N/A | None | Those paths return before resolve(), no browser involvement |
