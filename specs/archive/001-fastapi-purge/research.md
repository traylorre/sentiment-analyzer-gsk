# Research: FastAPI/Mangum Permanent Removal

**Date**: 2026-02-09
**Spec**: [spec.md](spec.md)
**Plan**: [plan.md](plan.md)

## Research Questions & Decisions

### R1: Dashboard Lambda Routing Framework

**Question**: What replaces FastAPI's routing for 102 endpoints across 11 routers?

**Decision**: AWS Lambda Powertools `APIGatewayRestResolver` with `Router` class

**Rationale**:
- Already a project dependency (aws-lambda-powertools 3.23.0)
- `include_router(router, prefix="/api/v2/auth")` maps 1:1 to FastAPI's `app.include_router()`
- Automatic API Gateway Proxy Integration format handling (returns `statusCode`, `headers`, `body`)
- Middleware support via `@app.use(middlewares=[...])` for CSRF/auth
- Path parameter extraction: `@app.get("/tickers/<ticker>/ohlc")` → `def get_ohlc(ticker: str)`
- Query/header access: `app.current_event.query_string_parameters`, `app.current_event.headers`
- Body parsing: `app.current_event.json_body`
- Response class: `from aws_lambda_powertools.event_handler import Response`

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|-------------|
| Custom lightweight router (dict-based) | 102 endpoints too many for manual routing; loses middleware, path param parsing, response formatting. High maintenance burden. |
| chalice | Separate framework with its own deployment model. Not Lambda-native in the same way. Would add new dependency. |
| Raw if/elif on event["path"] | Unmaintainable at 102 endpoints. No path parameter extraction. No middleware. |
| mangum replacement (a]sync) | Mangum IS the problem — wrapping ASGI apps. We want to eliminate the ASGI layer entirely. |

**Gap — 405 Method Not Allowed**: Powertools returns 404 for unmatched methods on valid routes. FR-017 requires 405. Mitigation: custom exception handler that checks if the path matches any route with a different method before returning 404. Approximately 15 lines of code in handler.py.

**Canonical Sources**:
- https://docs.powertools.aws.dev/lambda/python/latest/core/event_handler/api_gateway/
- https://docs.powertools.aws.dev/lambda/python/latest/core/event_handler/middlewares/
- https://github.com/aws-powertools/powertools-lambda-python

---

### R2: SSE Streaming Lambda Handler

**Question**: What replaces FastAPI + Uvicorn + Lambda Web Adapter for RESPONSE_STREAM?

**Decision**: Raw `awslambdaric` streaming with `HttpResponseStream`

**Rationale**:
- Lambda Powertools does NOT support RESPONSE_STREAM invoke mode (confirmed)
- No Python framework supports the three-argument streaming handler signature
- `awslambdaric` is bundled in `public.ecr.aws/lambda/python:3.13` base image
- Direct control over SSE protocol formatting (`data: {json}\n\n`)

**Handler Pattern**:
```python
from awslambdaric.types import HttpResponseStream

def lambda_handler(event, response_stream, context):
    metadata = {
        "statusCode": 200,
        "headers": {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    }
    response_stream = HttpResponseStream.from_stream(response_stream, metadata)

    for item in generate_events():
        try:
            response_stream.write(f"data: {orjson.dumps(item).decode()}\n\n".encode())
        except (RuntimeError, BrokenPipeError, IOError):
            # Client disconnected (FR-048)
            break

    response_stream.close()
```

**Client Disconnection Detection**: No `is_disconnected()` method. Detect via write exception (RuntimeError/BrokenPipeError/IOError). Wrap `response_stream.write()` in try/except, clean up ConnectionManager slots on failure.

**Limitations**:
- 20MB max streaming payload (soft limit)
- 15-minute Lambda timeout (hard ceiling for SSE connections)
- First byte must be written within 20 seconds

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|-------------|
| Keep Lambda Web Adapter for SSE only | Violates spec goal of complete removal. Retains uvicorn/FastAPI dependencies. |
| Powertools LambdaFunctionUrlResolver | Does not support RESPONSE_STREAM. Returns dict, not streaming. |
| WebSocket API (API Gateway) | Different protocol entirely. Breaks existing SSE clients. |

**Canonical Sources**:
- https://docs.aws.amazon.com/lambda/latest/dg/configuration-response-streaming.html
- https://github.com/aws/aws-lambda-python-runtime-interface-client
- https://docs.aws.amazon.com/lambda/latest/dg/lambda-urls.html

---

### R3: JSON Serialization

**Question**: What replaces FastAPI's JSONResponse for high-performance serialization?

**Decision**: orjson (new dependency)

**Rationale**:
- 3-10x faster than stdlib `json` for serialization
- Native handling: `datetime`, `date`, `time`, `UUID`, `dataclass`, `numpy` — no custom encoders (FR-011)
- 1.2MB installed size (vs ~15MB removed from FastAPI+Mangum+Uvicorn+Starlette)
- Pre-built wheels for both x86_64 and aarch64 (Graviton2 Lambda)
- Returns `bytes` — use `.decode()` for API Gateway proxy `body` (string required)

**Integration Pattern**:
```python
import orjson

# Pydantic model serialization
body = orjson.dumps(model.model_dump()).decode()

# Direct dict serialization (datetime handled natively)
body = orjson.dumps({"timestamp": datetime.now(UTC), "data": result}).decode()

# Deserialization
parsed = orjson.loads(event["body"])
```

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|-------------|
| stdlib json | No native datetime/dataclass support. Requires custom encoder. Slower. |
| ujson | Faster than stdlib but slower than orjson. No native datetime support. |
| msgspec | Faster than orjson for some cases but less mature. Different API. |

**Canonical Source**: https://github.com/ijl/orjson

---

### R4: OpenAPI Generation Without FastAPI

**Question**: How to generate OpenAPI docs as CI artifact without runtime FastAPI (FR-029)?

**Decision**: Custom Python script using Pydantic `model_json_schema()` + route registry

**Rationale**:
- Pydantic v2's `model_json_schema()` produces JSON Schema Draft 2020-12
- OpenAPI 3.1 uses JSON Schema 2020-12 natively (direct embedding, no conversion)
- Route registry built from Powertools `app.route` definitions
- Zero extra dependencies — uses Pydantic (already present) + stdlib json
- ~50-line script in `scripts/generate_openapi.py`, run in CI

**Pattern**:
```python
# scripts/generate_openapi.py
from src.lambdas.shared.models import OHLCRequestContext, SentimentResponse, ...

spec = {
    "openapi": "3.1.0",
    "info": {"title": "Sentiment Analyzer API", "version": "2.0.0"},
    "paths": {}
}
# Auto-populate paths from route registry + model schemas
for route in ROUTE_REGISTRY:
    spec["paths"][route.path] = {
        route.method: {
            "requestBody": {"content": {"application/json": {"schema": route.request_model.model_json_schema()}}},
            "responses": {"200": {"content": {"application/json": {"schema": route.response_model.model_json_schema()}}}}
        }
    }
```

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|-------------|
| apispec | Marshmallow-focused. Pydantic support via third-party plugin adds dependency weight. |
| spectree | Runtime validation framework. Adds runtime dependencies for CI-only use. Overkill. |
| datamodel-code-generator | Goes opposite direction (OpenAPI → Pydantic). Not applicable. |

**Canonical Sources**:
- https://docs.pydantic.dev/latest/concepts/json_schema/
- https://spec.openapis.org/oas/v3.1.0

---

### R5: Cookie Parsing and Construction

**Question**: How to handle cookies without FastAPI's Request.cookies / Response.set_cookie()?

**Decision**: Python stdlib `http.cookies.SimpleCookie`

**Rationale**:
- Zero additional dependencies
- Full support for all security attributes: HttpOnly, Secure, SameSite, Max-Age, Path, Domain
- Parsing: `cookie.load(event["headers"]["cookie"])` → `cookie["name"].value`
- Construction: `cookie["name"].OutputString()` → full Set-Cookie header value
- SameSite support since Python 3.8, fully supported in 3.13

**Pattern**:
```python
from http.cookies import SimpleCookie

# Parse incoming Cookie header (FR-050)
def parse_cookies(event: dict) -> dict[str, str]:
    cookie_header = event.get("headers", {}).get("cookie", "")
    if not cookie_header:
        return {}
    cookie = SimpleCookie()
    cookie.load(cookie_header)
    return {k: v.value for k, v in cookie.items()}

# Construct Set-Cookie header (FR-049)
def make_set_cookie(name: str, value: str, *, httponly: bool, secure: bool,
                    samesite: str, max_age: int, path: str = "/") -> str:
    cookie = SimpleCookie()
    cookie[name] = value
    cookie[name]["httponly"] = httponly
    cookie[name]["secure"] = secure
    cookie[name]["samesite"] = samesite
    cookie[name]["max-age"] = max_age
    cookie[name]["path"] = path
    return cookie[name].OutputString()
```

**Canonical Source**: https://docs.python.org/3/library/http.cookies.html

---

### R6: Dependency Injection Replacement

**Question**: What replaces FastAPI's 68 Depends() invocations?

**Decision**: Static module-level singletons with lazy initialization

**Rationale**:
- Lambda cold start initializes singletons once per container lifetime
- 6 unique dependency functions: `get_users_table` (~40 usages), `get_tiingo_adapter`, `get_finnhub_adapter`, `get_ticker_cache_dependency`, `no_cache_headers`, `require_csrf`
- Module-level `_instance = None` pattern with thread-safe init for SSE Lambda
- Test isolation via `unittest.mock.patch` targeting the module-level getter

**Pattern**:
```python
# src/lambdas/shared/dependencies.py
import boto3

_users_table = None

def get_users_table():
    global _users_table
    if _users_table is None:
        _users_table = boto3.resource("dynamodb").Table(os.environ["USERS_TABLE"])
    return _users_table
```

**Test Migration** (replaces `app.dependency_overrides`):
```python
# Before (FastAPI)
app.dependency_overrides[get_tiingo_adapter] = lambda: mock_tiingo

# After (unittest.mock)
with patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter", return_value=mock_tiingo):
    response = handler(event, context)
```

**Alternatives Considered**:
| Alternative | Why Rejected |
|-------------|-------------|
| dependency-injector library | Adds unnecessary dependency for 6 unique functions. Over-engineering. |
| Powertools Parameters | For SSM/Secrets Manager, not general DI. Different purpose. |
| Constructor injection | Lambda handler is a function, not a class. Module-level singletons are idiomatic. |

---

### R7: Case-Insensitive Header Lookup

**Question**: How to handle header case sensitivity differences between test code and API Gateway?

**Decision**: Utility function wrapping dict access with case normalization

**Rationale**:
- API Gateway normalizes all headers to lowercase in the event dict
- Test code and documentation may use mixed case (`Authorization`, `Content-Type`)
- Single utility function prevents scattered `.lower()` calls

**Pattern**:
```python
def get_header(event: dict, name: str, default: str | None = None) -> str | None:
    headers = event.get("headers") or {}
    return headers.get(name.lower(), default)
```

**Canonical Source**: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html (Header normalization behavior)

---

## Summary of All Decisions

| # | Question | Decision | New Dependency? |
|---|----------|----------|-----------------|
| R1 | Dashboard routing | Powertools APIGatewayRestResolver | No (existing) |
| R2 | SSE streaming | Raw awslambdaric HttpResponseStream | No (bundled in base image) |
| R3 | JSON serialization | orjson | Yes (1.2MB) |
| R4 | OpenAPI generation | Custom script + model_json_schema() | No |
| R5 | Cookie handling | stdlib http.cookies.SimpleCookie | No |
| R6 | Dependency injection | Module-level singletons | No |
| R7 | Header lookup | Utility function with case normalization | No |

**Net dependency change**: Remove 5 packages (~15MB), add 1 package (~1.2MB). Net reduction ~14MB.

## NEEDS CLARIFICATION

None. All research questions resolved.
