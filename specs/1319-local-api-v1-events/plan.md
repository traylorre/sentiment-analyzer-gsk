# Feature 1319: Implementation Plan

## Technical Context

### File to Modify
- `scripts/run-local-api.py` — single file change, ~80 lines modified

### Canonical Reference
- `tests/conftest.py:make_event()` (lines 149-222) — the v1 event factory that all unit tests use. The `_build_event()` rewrite must produce structurally identical events.

### Key Constraint
Powertools `APIGatewayRestResolver` (line 188 of `handler.py`) stores request state on `app.current_event`. This module-level singleton is NOT thread-safe. All handler invocations must be serialized.

## Implementation Strategy

### Change 1: Event Format (R1)
Rewrite `_build_event()` to produce API Gateway REST v1 events. The structure mirrors `make_event()` exactly:

```python
def _build_event(self, method: str) -> dict:
    """Build an API Gateway REST v1 proxy event from the HTTP request."""
    parsed = urlparse(self.path)
    content_length = int(self.headers.get("Content-Length", 0))
    body = self.rfile.read(content_length).decode() if content_length else None

    headers = {k.lower(): v for k, v in self.headers.items()}
    query_params = parse_qs(parsed.query) if parsed.query else None

    # API Gateway REST v1: queryStringParameters uses last value
    single_params = (
        {k: v[-1] for k, v in query_params.items()} if query_params else None
    )
    # API Gateway REST v1: multiValueQueryStringParameters preserves all values
    multi_params = (
        {k: v for k, v in query_params.items()} if query_params else None
    )

    # pathParameters: greedy proxy capture
    proxy_path = parsed.path.lstrip("/")
    path_params = {"proxy": proxy_path} if proxy_path else None

    return {
        "resource": "/{proxy+}" if proxy_path else "/",
        "path": parsed.path,
        "httpMethod": method,
        "headers": headers,
        "multiValueHeaders": {k: [v] for k, v in headers.items()},
        "queryStringParameters": single_params,
        "multiValueQueryStringParameters": multi_params,
        "pathParameters": path_params,
        "stageVariables": None,
        "body": body,
        "isBase64Encoded": False,
        "requestContext": {
            "accountId": "000000000000",
            "apiId": "local",
            "resourceId": "local",
            "resourcePath": "/{proxy+}" if proxy_path else "/",
            "httpMethod": method,
            "path": f"/v1{parsed.path}",
            "stage": "v1",
            "requestId": "local-request",
            "identity": {
                "sourceIp": "127.0.0.1",
                "userAgent": headers.get("user-agent", "local-dev"),
            },
            "time": "",
            "timeEpoch": 0,
        },
    }
```

### Change 2: Threading with Serialization Lock (R2)
```python
import threading
from http.server import ThreadingHTTPServer

# Module-level lock for handler serialization
_handler_lock = threading.Lock()

class LambdaProxyHandler(BaseHTTPRequestHandler):
    def _invoke_handler(self, method: str) -> None:
        from src.lambdas.dashboard.handler import lambda_handler

        event = self._build_event(method)
        context = _FakeLambdaContext()  # per-request context with fresh UUID

        with _handler_lock:
            response = lambda_handler(event, context)

        # ... response writing (outside lock — safe, per-thread socket)
```

### Change 3: Per-Request Lambda Context (R2)
```python
import uuid

class _FakeLambdaContext:
    function_name = "local-dashboard"
    memory_limit_in_mb = 512
    invoked_function_arn = "arn:aws:lambda:us-east-1:000000000000:function:local-dashboard"

    def __init__(self):
        self.aws_request_id = str(uuid.uuid4())
```

### Change 4: Server Instantiation (R2)
```python
server = ThreadingHTTPServer(("127.0.0.1", port), LambdaProxyHandler)
server.daemon_threads = True  # Don't block shutdown on stale threads
```

### Change 5: Docstring Updates (R1)
Update the `_build_event()` docstring and class docstring to reference "API Gateway REST v1" instead of "Function URL v2".

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Handler lock causes Playwright timeouts | Low | Medium | Handler is ~50ms with moto. 4 workers × 50ms = 200ms queue time. Playwright timeout is 30s. |
| moto state corruption under threads | Low | Low | Handler lock serializes all DynamoDB access. moto has per-table locks as backup. |
| External API calls (Tiingo/Finnhub) hold lock | Medium | Medium | Only affects tests hitting real APIs. Most E2E tests use mock data. If needed, move to `with _handler_lock: ...` around just the handler call, not the response writing. |
| Existing tests break | Very Low | High | Only `run-local-api.py` changes. Unit tests use `make_event()` directly, not the server. |

## Verification

1. `python -c "from scripts.run_local_api import LambdaProxyHandler"` — import check
2. Start server, `curl http://localhost:8000/api/v2/tickers/search?q=AAPL` — 200 response
3. Start server, `curl http://localhost:8000/api/v2/auth/anonymous -X POST` — 200 response
4. Grep server logs for "Rejected Function URL v2 event" — should be absent
5. Run existing pytest suite — no regressions

## Adversarial Review #2

**Drift analysis**: No drift found between post-AR#1 spec and plan. All 6 spec changes from AR#1 (handler lock, `None` vs `{}`, `resource` field, stage prefix, `identity.userAgent`, `stageVariables`) are reflected in plan Change 1-4.

**Cross-artifact consistency**: Plan event structure matches `make_event()` (lines 192-222) field-for-field. Lock placement in Change 2 covers both CRITICALs from AR#1.

**Gate: 0 CRITICAL, 0 HIGH. No drift requiring realignment.**
