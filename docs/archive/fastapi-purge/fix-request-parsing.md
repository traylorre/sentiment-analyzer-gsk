# Fix: Replace Request Parsing (Query/Depends -> Event Dict)

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P2
**Status:** [ ] TODO
**Depends On:** [design-native-handler.md](./design-native-handler.md)

---

## Problem Statement

FastAPI uses `Query()`, `Path()`, and `Depends()` to declaratively parse request parameters. In a native Lambda handler, these must be extracted manually from the `event` dictionary.

### FastAPI Pattern (Current)

```python
@app.get("/api/v2/tickers/{ticker}/ohlc")
async def get_ohlc(
    ticker: str,                           # Path parameter
    range: str = Query(default="1M"),      # Query parameter
    resolution: str = Query(default="D"),  # Query parameter
):
    ...
```

### Native Pattern (Target)

```python
async def handle_ohlc(event: dict, context) -> dict:
    ticker = _get_path_param(event, "ticker")
    range_param = _get_query_param(event, "range", default="1M")
    resolution = _get_query_param(event, "resolution", default="D")
    ...
```

---

## Migration Checklist

### Per-Endpoint
- [ ] Map each `Query()` parameter to `event["queryStringParameters"]`
- [ ] Map each `Path()` parameter to `event["pathParameters"]`
- [ ] Preserve default values exactly
- [ ] Preserve type coercion (FastAPI auto-casts; we must do it explicitly)
- [ ] Add input validation that FastAPI provided implicitly

### Validation Replacements

```python
# FastAPI auto-validates; we must be explicit
if not ticker:
    return _error_response(400, "Missing required parameter: ticker")

if range_param not in {"1D", "1W", "1M", "3M", "6M", "1Y", "custom"}:
    return _error_response(400, f"Invalid range: {range_param}")
```

---

## Event Structure Reference

API Gateway Proxy Integration event format:

```json
{
    "resource": "/api/v2/tickers/{ticker}/ohlc",
    "path": "/api/v2/tickers/AAPL/ohlc",
    "httpMethod": "GET",
    "queryStringParameters": {
        "range": "1M",
        "resolution": "D"
    },
    "pathParameters": {
        "ticker": "AAPL"
    },
    "headers": {
        "Content-Type": "application/json",
        "Authorization": "Bearer ..."
    },
    "requestContext": {
        "authorizer": { ... }
    }
}
```

---

## Risk: Null queryStringParameters

API Gateway sends `"queryStringParameters": null` (not `{}`) when no query params present.

```python
# WRONG - TypeError: 'NoneType' object is not subscriptable
ticker = event["queryStringParameters"]["ticker"]

# RIGHT - defensive extraction
params = event.get("queryStringParameters") or {}
ticker = params.get("ticker")
```

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | TBD | Replace function signature, add manual parsing |

---

## Testing

- [ ] Unit test: Missing query parameter returns 400
- [ ] Unit test: Null queryStringParameters handled gracefully
- [ ] Unit test: Default values applied when parameters absent
- [ ] Unit test: All valid range/resolution values accepted

---

## Related

- [design-native-handler.md](./design-native-handler.md) - Defines helper functions
- [fix-response-format.md](./fix-response-format.md) - Companion output transformation
