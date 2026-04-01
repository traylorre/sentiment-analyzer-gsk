# Feature 1297: Switch Dashboard Lambda to APIGatewayRestResolver

## Problem Statement

The Dashboard Lambda handler uses Powertools `LambdaFunctionUrlResolver` which parses Function URL v2 event format. The production path is API Gateway REST API → `lambda:InvokeFunction`, which sends v1 event format. This causes `KeyError` on `event["requestContext"]["http"]["method"]` → 500 Internal Server Error for all API Gateway requests.

### Root Cause

The handler was written for Function URL access (v2 events). API Gateway was added later for Cognito auth, WAF, and rate limiting. Nobody updated the handler to use `APIGatewayRestResolver` when the production ingress changed.

### Security-First Rationale

The v2 event format only arrives via paths that bypass application security:
- **Function URL**: IAM-protected (unreachable from frontend)
- **Direct Lambda invoke**: Requires IAM (bypasses Cognito, WAF, rate limiting)

The handler must speak the production format (v1). Supporting v2 events preserves the ability to process events from unauthenticated paths. A v1→v2 transform was rejected for this reason.

### Impact

- **11 preprod E2E tests fail** (API Gateway returns 500 for all routes)
- **Production traffic broken** through API Gateway
- **57% of E2E tests are false positives** (send v2 events via direct invoke, bypassing security)

## User Stories

### US-1: Production traffic works
**As** the Amplify frontend,
**I want** API Gateway requests to reach the Dashboard Lambda successfully,
**So that** users get correct responses with full security (Cognito + WAF + rate limiting).

**Acceptance Criteria:**
- All routes accessible via API Gateway return correct responses (not 500)
- The handler uses `APIGatewayRestResolver` matching the production event format

### US-2: Handler rejects non-production event formats
**As** a security engineer,
**I want** the handler to only process API Gateway v1 events,
**So that** events from paths that bypass security layers are not silently accepted.

**Acceptance Criteria:**
- `LambdaFunctionUrlResolver` is removed from the Dashboard Lambda
- `APIGatewayRestResolver` is the sole resolver
- v2 events (from Function URL or crafted invoke) are not processed by the resolver

## Requirements

### FR-001: Switch resolver class
- Change import from `LambdaFunctionUrlResolver` to `APIGatewayRestResolver`
- Change `app = LambdaFunctionUrlResolver()` to `app = APIGatewayRestResolver()`
- Update handler docstring to reflect API Gateway v1 format

### FR-002: Simplify handler logging
The `lambda_handler` logging currently uses v2-first fallback chains:
```python
"path": event.get("rawPath", event.get("path", "unknown")),
"method": event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "unknown")),
```
Simplify to v1-only:
```python
"path": event.get("path", "unknown"),
"method": event.get("httpMethod", "unknown"),
```

### FR-003: Verify middleware v1 compatibility
Confirm these middlewares work with v1 events (no code changes expected):
- `csrf_middleware.py`: reads `httpMethod` first (v1 native)
- `rate_limit.py`: checks `requestContext.identity.sourceIp` (v1 native)
- `auth_middleware.py`: reads `headers` dict (format-agnostic)
- `event_helpers.py`: `get_header()` uses `headers.get(name.lower())` (format-agnostic)

### FR-004: v2 event rejection guard
Add detection at the top of `lambda_handler` (after EventBridge scheduler check): if `event.get("version") == "2.0"`, log a warning with event source details and return HTTP 400 with body `{"error": "Dashboard Lambda expects API Gateway REST v1 events. Function URL v2 events are not supported."}`. This makes misrouting visible instead of producing an opaque Powertools 500.

### NFR-001: Zero regression on passing tests
After Feature 1298 aligns test fixtures, all currently-passing tests must continue to pass.

### NFR-002: 11 failing tests fixed
The 11 preprod tests that hit API Gateway with HTTP requests must pass after this change is deployed.

## Edge Cases

### EC-1: Router compatibility
Powertools `Router` class is resolver-agnostic. Routes registered via `@app.get()` and `app.include_router()` work identically with `APIGatewayRestResolver`. The base class `ApiGatewayResolver` handles route matching for both v1 and v2. No route changes needed.

### EC-2: current_event.raw_event consumers
Handler code accesses `app.current_event.raw_event` to get the underlying dict. With `APIGatewayRestResolver`, this returns the v1 event dict. Code that reads v1 fields (`headers`, `body`, `queryStringParameters`, `pathParameters`) works unchanged. Code that reads v2-only fields (`rawPath`, `requestContext.http`) will get `None`/`KeyError` — but the middleware already has v1-first patterns for all these.

### EC-3: Header case sensitivity
API Gateway REST with HTTP/2 lowercases headers. HTTP/1.1 preserves case. The `auth_middleware.py` explicitly normalizes: `{k.lower(): v for k, v in headers.items()}`. The `_get_request_origin()` function uses `app.current_event.headers.get("origin")` which is case-sensitive — but Powertools `APIGatewayProxyEvent` wraps headers, and in practice API Gateway REST lowercases them. Risk: LOW.

### EC-4: SSE Lambda unaffected
The SSE Lambda uses `LambdaFunctionUrlResolver` correctly — its production path is CloudFront → Function URL (v2 events). This feature changes ONLY the Dashboard Lambda.

## Success Criteria

1. `app = APIGatewayRestResolver()` in handler.py
2. No import of `LambdaFunctionUrlResolver` in handler.py
3. Handler logging uses v1 fields directly (no v2 fallback chains)
4. All middleware confirmed v1-compatible (no code changes needed)
5. All 11 failing preprod tests pass after deploy

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | `_get_request_origin()` does `app.current_event.headers.get("origin")` — case-sensitive lookup. API Gateway REST with HTTP/1.1 preserves original header case (`Origin` not `origin`). Returns `None` → CORS origin check fails → frontend gets opaque CORS errors. | **Must fix.** Add `_get_request_origin()` to FR-001 scope: normalize header lookup to lowercase. Change to `headers.get("origin") or headers.get("Origin")` or better: iterate headers with lowercased key match. |
| MEDIUM | Stage prefix concern: reviewer claimed `event["path"]` includes stage prefix. | **Invalid.** Verified via Powertools source AND AWS docs: in `AWS_PROXY` integration, `event["path"]` does NOT include stage prefix. `APIGatewayRestResolver` uses `event["path"]` for route matching (via `BaseProxyEvent.path`). Routes registered as `"/health"` match correctly. |
| MEDIUM | Middleware v2 field access audit unverified. | **Verified.** From prior session research: `csrf_middleware.py:50` reads `httpMethod` first (v1 native). `rate_limit.py:83-91` checks both `identity.sourceIp` (v1) and `http.sourceIp` (v2). `auth_middleware.py:276` reads `headers` dict (format-agnostic). All safe. |
| MEDIUM | CORSConfig transfer risk — if resolver had `cors=CORSConfig(...)`, dropping it silently removes CORS headers. | **Non-issue.** Confirmed: `app = LambdaFunctionUrlResolver()` has NO CORSConfig parameter. CORS is handled at infrastructure level (API Gateway gateway responses) and application level (Feature 1268). |
| LOW | v2 events hitting handler after switch would get opaque Powertools exception (500) instead of clear rejection. | **Add guard.** Add detection in `lambda_handler`: if `event.get("version") == "2.0"`, log warning and return 400 with message "Dashboard Lambda expects API Gateway v1 events". Makes misrouting visible instead of opaque 500. |
| LOW | `event_helpers.py:get_header()` lowercases lookup key but not dict keys. Pre-existing bug with increased surface after switch. | **Should fix in this feature.** Add `{k.lower(): v for k, v in headers.items()}` normalization in `get_header()`, matching the pattern already used in `auth_middleware.py`. |

### Spec Edits Made

1. **FR-001 expanded**: Now includes fixing `_get_request_origin()` header case sensitivity and `event_helpers.py:get_header()` normalization.
2. **New FR-004 added**: v2 event rejection guard with logging.

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** The HIGH finding (header case sensitivity) is resolved by expanding FR-001 scope to include header normalization fixes. Proceeding to Stage 3.

## Clarifications

### Q1: Does APIGatewayRestResolver strip or add stage prefix to event["path"]?
**Answer:** No. In AWS_PROXY integration, `event["path"]` is the path WITHOUT stage prefix (e.g., `/health` not `/v1/health`). Verified from Powertools source: `APIGatewayRestResolver` uses `BaseProxyEvent.path` → `self["path"]` for route matching. Stage prefix only appears in `event["requestContext"]["path"]` which is never used for routing.
**Evidence:** Powertools `api_gateway.py:2175-2194` (`_resolve()`), `common.py:220` (`BaseProxyEvent.path`).

### Q2: Does switching resolver change `current_event.headers` behavior?
**Answer:** Both return a plain `dict` (not `CaseInsensitiveDict`). The difference is that v2 events guarantee lowercase header keys while v1 events may have mixed case. This is mitigated by the header normalization fixes in FR-001 (AR#1 resolution).
**Evidence:** Powertools `APIGatewayProxyEvent.headers` and `APIGatewayProxyEventV2.headers` both return `self.get("headers")` — raw dict from event.

### Q3: Will the v2 rejection guard (FR-004) affect the direct invoke tests before Feature 1298 aligns them?
**Answer:** Yes. Tests sending v2 events to `lambda_handler()` will get 400 instead of routing. This is intentional — it forces Feature 1298 to be implemented alongside 1297. The features must be merged together or 1298 first, then 1297.
**Evidence:** Logical — FR-004 explicitly rejects v2 events. Tests sending v2 events must be updated before or simultaneously.

All questions self-answered. No questions deferred to user.
