# Fix: Replace Middleware (Timing, Logging, X-Ray)

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P4
**Status:** [ ] TODO
**Depends On:** [audit-fastapi-surface.md](./audit-fastapi-surface.md)

---

## Problem Statement

FastAPI middlewares add cross-cutting concerns (timing, logging, CORS, X-Ray tracing) as decorators or `app.add_middleware()` calls. In a native handler, these become inline code using the Two-Phase Handler pattern [21.1].

---

## Common Middleware Patterns to Replace

### 1. Request Timing

```python
# FastAPI middleware (current)
@app.middleware("http")
async def add_timing(request, call_next):
    start = time.time()
    response = await call_next(request)
    response.headers["X-Response-Time"] = str(time.time() - start)
    return response

# Native handler (target)
async def _async_handler(event, context):
    start = time.time()
    response = await _handle_request(event, context)
    response["headers"]["X-Response-Time"] = f"{time.time() - start:.3f}"
    return response
```

### 2. CORS

```python
# FastAPI middleware (current)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Native handler (target) - see _cors_headers() in design-native-handler.md
# Also handle OPTIONS preflight explicitly:
if event.get("httpMethod") == "OPTIONS":
    return {
        "statusCode": 200,
        "headers": _cors_headers(),
        "body": "",
    }
```

### 3. X-Ray Tracing

```python
# If using aws-xray-sdk with FastAPI middleware
# Native handler: X-Ray is configured at Lambda level, not app level
# No code change needed - Lambda runtime handles X-Ray automatically
```

### 4. Error Logging

```python
# FastAPI exception handler (current)
@app.exception_handler(Exception)
async def global_error_handler(request, exc):
    logger.error(f"Unhandled: {exc}")
    return JSONResponse(status_code=500, content={"error": "Internal error"})

# Native handler (target)
async def _async_handler(event, context):
    try:
        return await _handle_request(event, context)
    except Exception:
        logger.exception("Unhandled exception in handler")
        return _error_response(500, "Internal server error")
```

---

## Two-Phase Handler Integration [21.1]

The two-phase pattern replaces middleware timing + background tasks:

```python
async def _async_handler(event, context):
    """Two-phase handler: respond fast, then write-through."""
    # Phase 1: Respond within timeout
    try:
        result = await asyncio.wait_for(
            _handle_request(event, context),
            timeout=context.get_remaining_time_in_millis() / 1000 - 1.0,
        )
    except asyncio.TimeoutError:
        logger.error("Phase 1 timeout")
        return _error_response(504, "Request timeout")

    # Phase 2: Write-through to DynamoDB (fire-and-forget within remaining time)
    if result.get("_cache_data"):
        try:
            await asyncio.wait_for(
                _write_through_to_dynamodb(result["_cache_data"]),
                timeout=context.get_remaining_time_in_millis() / 1000 - 0.5,
            )
        except asyncio.TimeoutError:
            logger.warning("Phase 2 write-through timeout")

    return result
```

---

## Audit Required

- [ ] List all middleware currently registered
- [ ] Document behavior of each middleware
- [ ] Identify which are Lambda-level (X-Ray) vs app-level (CORS, timing)
- [ ] Check for request body parsing middleware

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/main.py` | TBD | Middleware definitions to remove |
| `src/lambdas/dashboard/ohlc.py` | TBD | Inline middleware logic |

---

## Testing

- [ ] Unit test: CORS headers present on all responses including errors
- [ ] Unit test: OPTIONS preflight returns 200 with CORS headers
- [ ] Unit test: X-Response-Time header present
- [ ] Unit test: Unhandled exceptions return 500 (not crash)

---

## Related

- [design-native-handler.md](./design-native-handler.md) - Two-phase pattern reference
- [fix-response-format.md](./fix-response-format.md) - CORS header implementation
