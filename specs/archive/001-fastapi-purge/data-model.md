# Data Model: FastAPI/Mangum Permanent Removal

**Date**: 2026-02-09
**Spec**: [spec.md](spec.md)
**Research**: [research.md](research.md)

## Overview

This migration does not introduce new data entities or modify DynamoDB table schemas. The data model changes are limited to the request/response contract layer — how Lambda handlers receive HTTP requests and format HTTP responses.

## Request Models (Unchanged)

The 16 existing Pydantic request models remain the canonical validation layer. They are currently used via FastAPI's implicit `Depends()`/`Body()` binding. Post-migration, they are invoked explicitly at handler entry ("validation at the gate").

| Model | Location | Used By | Validation Trigger |
|-------|----------|---------|-------------------|
| OHLCRequestContext | src/lambdas/dashboard/ohlc.py | GET /api/v2/tickers/{ticker}/ohlc | Query + path params → model_validate() |
| SentimentHistoryRequest | src/lambdas/dashboard/sentiment.py | GET /api/v2/sentiment/history | Query params → model_validate() |
| AlertRuleCreate | src/lambdas/dashboard/alerts.py | POST /api/v2/alerts | JSON body → model_validate() |
| AlertRuleUpdate | src/lambdas/dashboard/alerts.py | PATCH /api/v2/alerts/{id} | JSON body → model_validate() |
| ConfigurationCreate | src/lambdas/dashboard/router_v2.py | POST /api/v2/configurations | JSON body → model_validate() |
| ConfigurationUpdate | src/lambdas/dashboard/router_v2.py | PATCH /api/v2/configurations/{id} | JSON body → model_validate() |
| TickerAdd | src/lambdas/dashboard/router_v2.py | POST /api/v2/tickers | JSON body → model_validate() |
| SessionCreate | src/lambdas/dashboard/router_v2.py | POST /api/v2/sessions | JSON body → model_validate() |
| AnonymousSessionCreate | src/lambdas/dashboard/router_v2.py | POST /api/v2/anonymous-sessions | JSON body (Body(default=None)) → model_validate() |
| RefreshTokenRequest | src/lambdas/dashboard/router_v2.py | POST /api/v2/auth/refresh | JSON body (Body(default=None)) → model_validate() |
| MagicLinkRequest | src/lambdas/dashboard/router_v2.py | POST /api/v2/auth/magic-link | JSON body → model_validate() |
| NotificationPreferences | src/lambdas/dashboard/router_v2.py | PATCH /api/v2/notifications/preferences | JSON body → model_validate() |
| OAuthCallback | src/lambdas/dashboard/router_v2.py | POST /api/v2/auth/oauth/callback | JSON body → model_validate() |
| UserLookup | src/lambdas/dashboard/router_v2.py | GET /api/v2/users/lookup | Query params → model_validate() |
| AdminSessionRevoke | src/lambdas/dashboard/router_v2.py | POST /api/v2/admin/sessions/revoke | JSON body → model_validate() |
| StreamConfig | src/lambdas/sse_streaming/config.py | GET /api/v2/stream | Query params → model_validate() |

## Response Models (Serialization Change Only)

3 endpoints use FastAPI `response_model=` for automatic schema filtering. Post-migration, these call `model.model_dump()` explicitly before `orjson.dumps()`.

| Model | Endpoint | Filtering Behavior |
|-------|----------|-------------------|
| OHLCResponse | GET /api/v2/tickers/{ticker}/ohlc | Strips extra fields from response dict |
| SentimentHistoryResponse | GET /api/v2/sentiment/history | Strips extra fields from response dict |
| StreamStatus | GET /api/v2/stream/status | Strips extra fields from response dict |

## New Data Structures

### API Gateway Proxy Integration Event (Input)

This is NOT a new model — it is the existing AWS contract. Documented here for test fixture design (FR-058).

```python
# Type annotation for handler input
class APIGatewayProxyEvent(TypedDict, total=False):
    httpMethod: str                              # "GET", "POST", etc.
    path: str                                    # "/api/v2/sentiment"
    resource: str                                # "/{proxy+}" or specific
    pathParameters: dict[str, str] | None        # {"ticker": "AAPL"}
    queryStringParameters: dict[str, str] | None # {"range": "1M"}
    headers: dict[str, str] | None               # lowercase keys
    body: str | None                             # JSON string for POST/PATCH
    isBase64Encoded: bool
    requestContext: dict                         # authorizer, identity, etc.
```

### API Gateway Proxy Integration Response (Output)

```python
class APIGatewayProxyResponse(TypedDict):
    statusCode: int                    # 200, 201, 400, 401, 403, 404, 405, 422, 500, 502, 503
    headers: dict[str, str]            # {"Content-Type": "application/json", ...}
    body: str                          # JSON string (orjson.dumps().decode())
    isBase64Encoded: bool              # True for binary static assets only
```

### Validation Error Response (422 — FastAPI Parity)

```python
class ValidationErrorDetail(TypedDict):
    loc: list[str | int]    # ["query", "resolution"] or ["body", "ticker"]
    msg: str                # "Input should be 'D', 'W', 'M' or 'Y'"
    type: str               # "enum", "string_type", "missing", etc.

class ValidationErrorResponse(TypedDict):
    detail: list[ValidationErrorDetail]
```

Construction from Pydantic ValidationError:
```python
from pydantic import ValidationError

try:
    ctx = OHLCRequestContext.model_validate(params)
except ValidationError as e:
    return {
        "statusCode": 422,
        "headers": {"Content-Type": "application/json"},
        "body": orjson.dumps({"detail": e.errors()}).decode(),
    }
```

### Mock Lambda Event Factory (Test Infrastructure — FR-058)

```python
def make_event(
    method: str = "GET",
    path: str = "/",
    path_params: dict[str, str] | None = None,
    query_params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
    body: dict | str | None = None,
    cookies: str | None = None,
) -> dict:
    """Construct a mock API Gateway Proxy Integration event."""
    base_headers = {"content-type": "application/json"}
    if headers:
        base_headers.update({k.lower(): v for k, v in headers.items()})
    if cookies:
        base_headers["cookie"] = cookies

    return {
        "httpMethod": method,
        "path": path,
        "resource": "/{proxy+}",
        "pathParameters": path_params,
        "queryStringParameters": query_params,
        "headers": base_headers,
        "body": orjson.dumps(body).decode() if isinstance(body, dict) else body,
        "isBase64Encoded": False,
        "requestContext": {
            "authorizer": {},
            "identity": {"sourceIp": "127.0.0.1"},
            "requestId": "test-request-id",
        },
    }
```

## Entity Relationships

No entity relationship changes. DynamoDB tables, GSIs, partition/sort key patterns all remain identical. The migration exclusively changes the transport layer (how HTTP requests enter the handler and how HTTP responses exit).

## State Transitions

No state transition changes. Business logic in `src/lambdas/shared/`, `src/lib/`, and adapter modules remains unchanged.
