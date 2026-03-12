# Design: Native Lambda Handler Signature

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P1
**Status:** [ ] TODO
**Depends On:** [audit-fastapi-surface.md](./audit-fastapi-surface.md)

---

## Objective

Define the target handler signature and response format that replaces FastAPI/Mangum. This is the contract all subsequent migration tasks implement against.

---

## Target Handler Shape

```python
import json
import asyncio
from typing import Any

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda Proxy Integration handler.

    Args:
        event: API Gateway proxy event dict
        context: Lambda context object

    Returns:
        API Gateway proxy response dict with statusCode, headers, body
    """
    return asyncio.get_event_loop().run_until_complete(
        _async_handler(event, context)
    )

async def _async_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Async handler implementing two-phase pattern [21.1]."""
    # Phase 1: Respond within timeout
    # Phase 2: Write-through to DynamoDB
    ...
```

---

## Proxy Response Contract

Every return path must produce:

```python
{
    "statusCode": int,           # 200, 400, 404, 500, 503
    "headers": {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": str,  # CORS
        "Access-Control-Allow-Headers": str,
        "Access-Control-Allow-Methods": str,
        "X-Cache-Source": str,               # "fresh" | "memory" | "dynamodb"
    },
    "body": str,                 # json.dumps(payload)
}
```

---

## Event Parsing Helpers

```python
def _get_query_param(event: dict, name: str, default: str | None = None) -> str | None:
    """Extract query string parameter from API Gateway event."""
    params = event.get("queryStringParameters") or {}
    return params.get(name, default)

def _get_path_param(event: dict, name: str) -> str | None:
    """Extract path parameter from API Gateway event."""
    params = event.get("pathParameters") or {}
    return params.get(name)

def _get_http_method(event: dict) -> str:
    """Extract HTTP method from API Gateway event."""
    return event.get("httpMethod", "GET")
```

---

## Error Response Helper

```python
def _error_response(status_code: int, message: str) -> dict[str, Any]:
    """Build standardized error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            **_cors_headers(),
        },
        "body": json.dumps({"error": message}),
    }

def _cors_headers() -> dict[str, str]:
    """CORS headers matching current FastAPI middleware config."""
    # TODO: Extract actual origins from current FastAPI CORS config
    return {
        "Access-Control-Allow-Origin": "*",  # PLACEHOLDER - audit actual config
        "Access-Control-Allow-Headers": "Content-Type,Authorization",
        "Access-Control-Allow-Methods": "GET,OPTIONS",
    }
```

---

## Routing Strategy

### Option A: Single handler, internal dispatch (Recommended for dashboard)

```python
def lambda_handler(event, context):
    path = event.get("resource", "")
    method = event.get("httpMethod", "GET")

    if method == "OPTIONS":
        return _cors_preflight_response()

    routes = {
        "/api/v2/tickers/{ticker}/ohlc": handle_ohlc,
        "/api/v2/tickers/{ticker}/news": handle_news,
        "/health": handle_health,
    }

    handler = routes.get(path)
    if handler is None:
        return _error_response(404, f"Route not found: {path}")

    return asyncio.get_event_loop().run_until_complete(handler(event, context))
```

### Option B: One Lambda per endpoint

Not recommended - increases infrastructure complexity and cold start surface.

---

## Decision Points (Resolve During Audit)

- [ ] How many routes does the dashboard Lambda serve?
- [ ] Is there a single `app` or multiple routers?
- [ ] What CORS origins are currently configured?
- [ ] Are there WebSocket or SSE endpoints in this Lambda?
- [ ] Does the handler use `async def` or sync `def`?

---

## Related

- [audit-fastapi-surface.md](./audit-fastapi-surface.md) - Provides inputs to finalize this design
- [fix-request-parsing.md](./fix-request-parsing.md) - Implements the parsing helpers
- [fix-response-format.md](./fix-response-format.md) - Implements the response helpers
