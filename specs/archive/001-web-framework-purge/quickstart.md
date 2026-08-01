# Quickstart: FastAPI/Mangum Purge Migration Guide

**Date**: 2026-02-09
**Spec**: [spec.md](spec.md)
**Research**: [research.md](research.md)

## Prerequisites

- Python 3.13
- `make install` (refreshes venv after dependency changes)
- `make test-local` passes on current `main` (baseline)

## Migration Patterns

### Pattern 1: Dashboard Route (FastAPI → Powertools)

**Before** (FastAPI):
```python
from fastapi import APIRouter, Depends, Query
from src.lambdas.shared.middleware.require_role import require_admin

router = APIRouter(prefix="/api/v2/tickers", tags=["tickers"])

@router.get("/{ticker}/ohlc")
async def get_ohlc(
    ticker: str,
    range: OHLCRange = Query(default=OHLCRange.ONE_MONTH),
    resolution: OHLCResolution = Query(default=OHLCResolution.DAILY),
    tiingo: TiingoAdapter = Depends(get_tiingo_adapter),
    finnhub: FinnhubAdapter = Depends(get_finnhub_adapter),
):
    ctx = OHLCRequestContext(ticker=ticker, range=range, resolution=resolution)
    data = await tiingo.get_ohlc(ctx)
    return OHLCResponse(data=data)
```

**After** (Powertools):
```python
from aws_lambda_powertools.event_handler.router import Router
from src.lambdas.shared.dependencies import get_tiingo_adapter, get_finnhub_adapter

router = Router()

@router.get("/api/v2/tickers/<ticker>/ohlc")
def get_ohlc(ticker: str):
    # Validation at the gate
    params = router.current_event.query_string_parameters or {}
    try:
        ctx = OHLCRequestContext.model_validate({
            "ticker": urllib.parse.unquote(ticker),
            "range": params.get("range", "1M"),
            "resolution": params.get("resolution", "D"),
        })
    except ValidationError as e:
        return Response(
            status_code=422,
            content_type="application/json",
            body=orjson.dumps({"detail": e.errors()}).decode(),
        )

    tiingo = get_tiingo_adapter()
    data = tiingo.get_ohlc(ctx)
    response_body = OHLCResponse.model_validate(data).model_dump()
    return Response(
        status_code=200,
        content_type="application/json",
        body=orjson.dumps(response_body).decode(),
    )
```

### Pattern 2: Handler Entry Point

**Before** (FastAPI + Mangum):
```python
from fastapi import FastAPI
from mangum import Mangum

app = FastAPI(title="Dashboard API")
app.include_router(auth_router)
app.include_router(ticker_router)
# ... 9 more routers

handler = Mangum(app, lifespan="off")
```

**After** (Powertools):
```python
from aws_lambda_powertools.event_handler import APIGatewayRestResolver, Response
from aws_lambda_powertools import Logger, Tracer

logger = Logger()
tracer = Tracer()
app = APIGatewayRestResolver()

app.include_router(auth_router)
app.include_router(ticker_router)
# ... 9 more routers

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def lambda_handler(event, context):
    return app.resolve(event, context)
```

### Pattern 3: SSE Streaming Handler

**Before** (FastAPI + Lambda Web Adapter):
```python
from fastapi import FastAPI
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

@app.get("/api/v2/stream")
async def stream():
    return EventSourceResponse(generate_events())
```

**After** (Raw awslambdaric):
```python
from awslambdaric.types import HttpResponseStream
import orjson

def lambda_handler(event, response_stream, context):
    metadata = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    }
    response_stream = HttpResponseStream.from_stream(response_stream, metadata)

    for item in generate_events():
        try:
            payload = orjson.dumps(item).decode()
            response_stream.write(f"data: {payload}\n\n".encode())
        except (RuntimeError, BrokenPipeError, IOError):
            break  # Client disconnected

    response_stream.close()
```

### Pattern 4: Middleware Replacement

**Before** (FastAPI Depends):
```python
from fastapi import Depends, Request, HTTPException

async def require_admin(request: Request):
    auth = request.headers.get("Authorization")
    if not auth:
        raise HTTPException(status_code=401, detail="Missing authorization")
    # ... validate token
```

**After** (Powertools middleware):
```python
def require_admin_middleware(app, next_middleware):
    auth = app.current_event.get_header_value("authorization")
    if not auth:
        return Response(status_code=401, content_type="application/json",
                       body='{"detail": "Missing authorization"}')
    # ... validate token
    return next_middleware(app)

# Usage on route:
@router.post("/api/v2/admin/sessions/revoke", middlewares=[require_admin_middleware])
def revoke_session():
    ...
```

### Pattern 5: Test Migration (TestClient → Direct Invocation)

**Before** (TestClient):
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_get_ohlc():
    response = client.get("/api/v2/tickers/AAPL/ohlc?range=1M")
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
```

**After** (Direct handler invocation):
```python
from tests.conftest import make_event

def test_get_ohlc():
    event = make_event(
        method="GET",
        path="/api/v2/tickers/AAPL/ohlc",
        path_params={"ticker": "AAPL"},
        query_params={"range": "1M", "resolution": "D"},
    )
    response = lambda_handler(event, mock_context)
    assert response["statusCode"] == 200
    data = json.loads(response["body"])
    assert "data" in data
```

### Pattern 6: dependency_overrides → unittest.mock.patch

**Before**:
```python
app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo
with TestClient(app) as client:
    response = client.get("/api/v2/tickers/AAPL/ohlc")
```

**After**:
```python
with patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter", return_value=mock_tiingo):
    response = lambda_handler(event, mock_context)
```

### Pattern 7: Cookie Operations

**Before** (FastAPI):
```python
# Reading
token = request.cookies.get("refresh_token")

# Writing
response.set_cookie("csrf_token", value=token, httponly=False, secure=True, samesite="none")
```

**After** (stdlib):
```python
from http.cookies import SimpleCookie

# Reading (FR-050)
cookies = parse_cookies(event)  # utility function
token = cookies.get("refresh_token")

# Writing (FR-049)
set_cookie = make_set_cookie("csrf_token", value=token,
                             httponly=False, secure=True, samesite="none", max_age=3600)
response["headers"]["Set-Cookie"] = set_cookie
```

### Pattern 8: Contract Test Migration

**Before** (response.json()):
```python
def test_session_api_returns_user():
    response = client.post("/api/v2/sessions", json={"email": "test@example.com"})
    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] is not None
```

**After** (json.loads(response["body"])):
```python
def test_session_api_returns_user():
    event = make_event(
        method="POST",
        path="/api/v2/sessions",
        body={"email": "test@example.com"},
    )
    response = lambda_handler(event, mock_context)
    assert response["statusCode"] == 201
    data = json.loads(response["body"])
    assert data["user_id"] is not None
```

## Verification Checklist

After each file migration:

1. `grep -n "fastapi\|starlette\|mangum\|uvicorn\|TestClient" <file>` returns zero matches
2. `pytest <test_file> -v` passes
3. No `from fastapi import` or `from starlette import` imports remain
4. No `app.dependency_overrides` usage remains
5. All response assertions use `response["statusCode"]` and `json.loads(response["body"])`

## Local Development

**Before**: `uvicorn handler:app --reload`

**After**: Direct handler invocation with mock events:
```bash
python -c "
from src.lambdas.dashboard.handler import lambda_handler
import json
event = {'httpMethod': 'GET', 'path': '/api/v2/sentiment', 'headers': {}, 'queryStringParameters': None, 'pathParameters': None, 'body': None, 'isBase64Encoded': False, 'requestContext': {'requestId': 'local'}}
result = lambda_handler(event, None)
print(json.dumps(json.loads(result['body']), indent=2))
"
```

Or use `sam local start-api` with `template.yaml` for full API Gateway simulation.
