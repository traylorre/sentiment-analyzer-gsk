# Feature 1297: Implementation Plan

## Technical Context

### Architecture
- **Dashboard Lambda production path**: API Gateway REST → `lambda:InvokeFunction` → v1 events
- **SSE Lambda production path**: CloudFront → Function URL (OAC/SigV4) → v2 events (unchanged)
- **Handler currently**: `LambdaFunctionUrlResolver` (v2 only) → crashes on v1 events

### Powertools Resolver Behavior (verified from source)

Both `APIGatewayRestResolver` and `LambdaFunctionUrlResolver` inherit from `ApiGatewayResolver`. Route registration (`@app.get("/path")`, `app.include_router(router)`) is identical. The only difference is event parsing:

| Field | `APIGatewayRestResolver` (v1) | `LambdaFunctionUrlResolver` (v2) |
|-------|-------------------------------|----------------------------------|
| HTTP method | `event["httpMethod"]` | `event["requestContext"]["http"]["method"]` |
| Path | `event["path"]` (no stage prefix in AWS_PROXY) | `event["rawPath"]` |
| Source IP | `event["requestContext"]["identity"]["sourceIp"]` | `event["requestContext"]["http"]["sourceIp"]` |
| Headers | `event["headers"]` (plain dict) | `event["headers"]` (plain dict) |
| current_event type | `APIGatewayProxyEvent` | `APIGatewayProxyEventV2` |

**Confirmed**: `event["path"]` does NOT include stage prefix in `AWS_PROXY` integration. Routes registered as `/health` match correctly.

## Implementation Strategy

### 1. Handler resolver switch (2 lines)

```python
# Before
from aws_lambda_powertools.event_handler import LambdaFunctionUrlResolver
app = LambdaFunctionUrlResolver()

# After
from aws_lambda_powertools.event_handler import APIGatewayRestResolver
app = APIGatewayRestResolver()
```

### 2. Handler logging simplification

```python
# Before (v2-first with v1 fallback)
"path": event.get("rawPath", event.get("path", "unknown")),
"method": event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "unknown")),

# After (v1 direct)
"path": event.get("path", "unknown"),
"method": event.get("httpMethod", "unknown"),
```

### 3. v2 event rejection guard (FR-004)

```python
# After EventBridge scheduler check, before app.resolve():
if event.get("version") == "2.0":
    logger.warning("Received Function URL v2 event — Dashboard Lambda expects API Gateway v1",
                    extra={"event_version": "2.0"})
    return {
        "statusCode": 400,
        "body": '{"error":"Dashboard Lambda expects API Gateway REST v1 events"}',
        "headers": {"content-type": "application/json"},
    }
```

### 4. Header case normalization fixes (AR#1 HIGH finding)

**`_get_request_origin()` in handler.py:**
```python
# Before
return app.current_event.headers.get("origin")

# After
headers = app.current_event.headers or {}
return next((v for k, v in headers.items() if k.lower() == "origin"), None)
```

**`get_header()` in event_helpers.py:**
```python
# Before
headers = event.get("headers") or {}
return headers.get(name.lower(), default)

# After
headers = event.get("headers") or {}
normalized = {k.lower(): v for k, v in headers.items()}
return normalized.get(name.lower(), default)
```

### 5. Docstring updates

Update handler.py module docstring:
- "Uses AWS Lambda Powertools APIGatewayRestResolver for routing"
- "Expects API Gateway REST v1 event format"
- Remove references to "Lambda Function URL v2 format"

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `src/lambdas/dashboard/handler.py` | Import + resolver + logging + v2 guard + origin fix + docstring | ~15 |
| `src/lambdas/shared/utils/event_helpers.py` | Header normalization in `get_header()` | ~3 |

## Files NOT Modified

| File | Why |
|------|-----|
| `router_v2.py` | Routes via `app.include_router()`, resolver-agnostic |
| `csrf_middleware.py` | Already reads `httpMethod` first (v1 native) |
| `rate_limit.py` | Already checks `identity.sourceIp` (v1 native) |
| `auth_middleware.py` | Normalizes headers independently |
| SSE handler | Different Lambda, different production path (v2 correct) |
| Infrastructure (*.tf) | No Terraform changes for this feature |

## Dependencies

- Feature 1298 must update test fixtures to v1 format, otherwise unit tests will fail
- Implementation order: 1297 handler change + 1298 test alignment should be in the same commit or consecutive commits

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Header case mismatch in production | Low (HTTP/2 lowercases) | Medium (CORS failure) | Explicit normalization in `_get_request_origin()` and `get_header()` |
| Route matching breaks | None | N/A | Verified: `event["path"]` has no stage prefix in AWS_PROXY |
| Middleware incompatibility | None | N/A | Verified: all middleware has v1-first patterns |
| v2 events silently rejected | Intentional | N/A | FR-004 guard returns 400 with clear message |

## Adversarial Review #2

### Drift Analysis

**DRIFT FOUND:** Clarification Q3 revealed that FR-004 (v2 rejection guard) creates a hard dependency: Feature 1298 must update test fixtures BEFORE or SIMULTANEOUSLY with Feature 1297. The original dependency graph had 1298 blocked by 1297. This is now reversed for implementation:

- **Spec order**: 1297 depends on nothing, 1298 depends on 1297
- **Implementation order**: 1298 (test fixtures) and 1297 (handler) must be in the SAME commit

This is a constraint on implementation order, not on spec/plan order. The artifacts are consistent — the dependency is correctly captured here.

### Cross-Artifact Consistency
- Plan's header normalization fixes match AR#1's HIGH finding resolution
- Plan's v2 guard matches FR-004 added after AR#1
- Plan's "no stage prefix" claim matches Q1's verified evidence
- Plan's file list is consistent with spec's requirements

### Gate Statement
**0 CRITICAL, 0 HIGH remaining. Drift found and resolved** (implementation ordering constraint documented). Proceeding to Stage 7.
