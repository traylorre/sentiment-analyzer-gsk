# Fix: Replace Response Format (Response -> Proxy Dict)

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P3
**Status:** [ ] TODO
**Depends On:** [design-native-handler.md](./design-native-handler.md)

---

## Problem Statement

Mangum's sole job is converting a FastAPI `Response` object into the JSON dictionary that API Gateway expects. We replace this with 3 lines of explicit formatting.

### FastAPI Pattern (Current)

```python
from fastapi.responses import JSONResponse

return JSONResponse(
    content=candles,
    headers={"X-Cache-Source": "fresh"}
)
```

### Native Pattern (Target)

```python
return {
    "statusCode": 200,
    "headers": {
        "Content-Type": "application/json",
        "X-Cache-Source": "fresh",
        **_cors_headers(),
    },
    "body": json.dumps(candles),
}
```

---

## Migration Checklist

### Response Types to Convert
- [ ] `JSONResponse(content=...)` -> proxy dict with `json.dumps()`
- [ ] `Response(status_code=404)` -> `_error_response(404, message)`
- [ ] `Response(status_code=503)` -> `_error_response(503, message)`
- [ ] `HTTPException(status_code=...)` -> `_error_response(code, detail)`

### Critical: body Must Be a String

```python
# WRONG - API Gateway rejects dict body
return {"statusCode": 200, "body": {"data": [...]}}

# RIGHT - body must be json.dumps string
return {"statusCode": 200, "body": json.dumps({"data": [...]})}
```

### Critical: Pydantic Model Serialization

If response uses `.dict()` or `.model_dump()`:

```python
# FastAPI auto-serializes pydantic models
return OHLCResponse(candles=candles)

# Native handler must serialize explicitly
response = OHLCResponse(candles=candles)
return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json", **_cors_headers()},
    "body": response.model_dump_json(),
}
```

---

## CORS Headers

Must match whatever FastAPI CORS middleware currently provides. Extract exact values during audit.

```python
def _cors_headers() -> dict[str, str]:
    """CORS headers - values from FastAPI CORS middleware audit."""
    return {
        "Access-Control-Allow-Origin": os.environ.get("ALLOWED_ORIGINS", "*"),
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Requested-With",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | TBD | Replace all return statements |

---

## Testing

- [ ] Unit test: Response body is always a string (not dict)
- [ ] Unit test: Content-Type header present in all responses
- [ ] Unit test: CORS headers present in all responses
- [ ] Unit test: Error responses include structured error body
- [ ] Integration test: API Gateway accepts response format

---

## Related

- [fix-request-parsing.md](./fix-request-parsing.md) - Companion input transformation
- [fix-middleware-replacement.md](./fix-middleware-replacement.md) - CORS specifics
