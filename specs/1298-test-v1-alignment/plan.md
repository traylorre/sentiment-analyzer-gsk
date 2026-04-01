# Feature 1298: Implementation Plan

## Technical Context

### Current `make_event()` output (v2)
```python
{
    "version": "2.0",
    "rawPath": "/health",
    "rawQueryString": "key=value",
    "headers": {"content-type": "application/json"},
    "queryStringParameters": {"key": "value"},
    "pathParameters": None,
    "body": None,
    "isBase64Encoded": False,
    "requestContext": {
        "accountId": "123456789012",
        "apiId": "test-api",
        "domainName": "test.lambda-url.us-east-1.on.aws",
        "http": {"method": "GET", "path": "/health", "sourceIp": "127.0.0.1", ...},
        "requestId": "test-request-id",
        "routeKey": "$default",
        "stage": "$default",
    },
}
```

### Target `make_event()` output (v1)
```python
{
    "resource": "/{proxy+}",
    "path": "/health",
    "httpMethod": "GET",
    "headers": {"content-type": "application/json"},
    "multiValueHeaders": {"content-type": ["application/json"]},
    "queryStringParameters": {"key": "value"},
    "multiValueQueryStringParameters": {"key": ["value"]},
    "pathParameters": {"proxy": "health"},
    "stageVariables": None,
    "body": None,
    "isBase64Encoded": False,
    "requestContext": {
        "accountId": "123456789012",
        "apiId": "test-api",
        "resourceId": "test",
        "resourcePath": "/{proxy+}",
        "httpMethod": "GET",
        "path": "/v1/health",
        "stage": "v1",
        "requestId": "test-request-id",
        "identity": {
            "sourceIp": "127.0.0.1",
            "userAgent": "test",
        },
    },
}
```

## Implementation Strategy

### `make_event()` rewrite

Same function signature, different output format. All 331 callers pass the same parameters (`method`, `path`, `headers`, `body`, `query_params`, `path_params`, `cookies`). The function maps these to v1 fields:

- `method` → `httpMethod` + `requestContext.httpMethod`
- `path` → `path` + `resource` (use `"/{proxy+}"` for proxy routes)
- `headers` → `headers` (lowercased) + `multiValueHeaders` (values as single-element lists)
- `body` → `body` (JSON-serialized for dicts, as-is for strings)
- `query_params` → `queryStringParameters` + `multiValueQueryStringParameters`
- `path_params` → `pathParameters` (merge with `{"proxy": path.lstrip("/")}`)
- `cookies` → merged into headers `cookie` key

### `LambdaInvokeTransport.build_event()` rewrite

Same approach. The transport constructs events from HTTP-like parameters and sends via `boto3.invoke()`. Switch output to v1 format matching `make_event()`.

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `tests/conftest.py` | Rewrite `make_event()` v2→v1 | ~25 |
| `tests/e2e/helpers/lambda_invoke_transport.py` | Rewrite `build_event()` v2→v1 | ~30 |

## Files NOT Modified

- `tests/conftest.py:make_function_url_event()` — stays v2 (SSE Lambda)
- All 21 test files using `make_event()` — signature unchanged
- All 147 E2E test files using `LambdaInvokeTransport` — API unchanged

## Dependencies

- Must be committed in same PR as Feature 1297 (resolver switch)
- No new packages

## Adversarial Review #2

### Drift Analysis
No drift. Spec and plan are aligned. The v1 event structure in the plan matches the AWS documentation canonical format.

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** No drift. Proceeding to Stage 7.
