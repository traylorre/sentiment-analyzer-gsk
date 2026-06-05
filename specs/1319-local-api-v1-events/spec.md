# Feature 1319: Local API Server — API Gateway REST v1 Event Format

## Problem Statement

The local development API server (`scripts/run-local-api.py`) constructs Lambda **Function URL v2** events, but the dashboard Lambda handler (`src/lambdas/dashboard/handler.py`) expects **API Gateway REST v1** events. Feature 1297 switched the handler from `LambdaFunctionUrlResolver` to `APIGatewayRestResolver` and added an explicit v2 rejection guard (`event.get("version") == "2.0"` → HTTP 400). The local server was never updated to match.

This causes **every API endpoint** to return 400 in the local dev environment and CI E2E tests, making Playwright tests that depend on API data fail.

Additionally, the server uses Python's single-threaded `HTTPServer`, which cannot handle concurrent requests. This blocks the ability to run Playwright tests with multiple parallel workers.

## User Stories

### US1: Local API serves valid responses
**As a** developer running Playwright tests locally,
**I want** the local API server to produce API Gateway REST v1 events,
**So that** the dashboard Lambda handler processes requests correctly instead of rejecting them with 400.

**Acceptance Criteria:**
- `GET /api/v2/tickers/search?q=AMZN` returns 200 with ticker results (not 400)
- `POST /api/v2/auth/anonymous` returns 200 with session token
- `GET /api/v2/configurations` returns 200 with empty list
- All CRUD endpoints respond with correct status codes
- No `"Rejected Function URL v2 event"` log messages

### US2: Local API handles concurrent requests
**As a** developer running Playwright tests with multiple workers,
**I want** the local API server to handle concurrent HTTP requests,
**So that** parallel test execution doesn't cause request queuing or timeouts.

**Acceptance Criteria:**
- Server uses `ThreadingHTTPServer` for concurrent connection acceptance
- `threading.Lock` serializes `lambda_handler()` invocation (prevents `app.current_event` clobber)
- 4 concurrent connections accepted without TCP backlog rejection
- Per-request `_FakeLambdaContext` with unique `aws_request_id` (UUID) for log correlation

### US3: Event format matches production path
**As a** maintainer,
**I want** the local server's event format to match the canonical `make_event()` test fixture,
**So that** there is one source of truth for v1 event structure.

**Acceptance Criteria:**
- Event contains `httpMethod` (not `requestContext.http.method`)
- Event contains `path` (not `rawPath`)
- Event contains `multiValueHeaders` (dict of lists)
- Event contains `multiValueQueryStringParameters` (dict of lists)
- Event contains `pathParameters` with `proxy` capture
- Event does NOT contain `"version": "2.0"`
- Event contains `requestContext.identity.sourceIp` (not `requestContext.http.sourceIp`)
- Event contains `requestContext.resourcePath`, `stage`, `httpMethod`
- Event contains `resource: "/{proxy+}"` for route matching
- Event contains `requestContext.path` with stage prefix (e.g., `/v1/api/v2/...`)
- Event contains `requestContext.identity` with both `sourceIp` and `userAgent`
- Event contains `stageVariables: None`
- `queryStringParameters` is `None` (not `{}`) when no query string present
- `multiValueQueryStringParameters` is `None` when no query string present
- Docstring updated to reference "API Gateway REST v1" (not "Function URL v2")

## Requirements

### R1: Event Format Conversion
Convert `_build_event()` from Function URL v2 to API Gateway REST v1 format, matching the canonical structure in `tests/conftest.py:make_event()` (lines 192-222).

### R2: Threading Support with Handler Serialization
Replace `HTTPServer` with `ThreadingHTTPServer` for concurrent connection acceptance. Add a `threading.Lock` around the `lambda_handler()` invocation to serialize handler execution. This is required because Powertools' `APIGatewayRestResolver` stores request state on the module-level `app.current_event` singleton — concurrent handler execution would clobber auth tokens, request bodies, and CORS origins across threads. The lock also protects singleton initialization in `get_users_table()` and similar dependency getters.

### R3: Response Format Compatibility
The `_invoke_handler()` method must handle v1 response format. `APIGatewayRestResolver` returns `multiValueHeaders` (v1) instead of `cookies` (v2). Current code already handles both at lines 261-265 — verify this continues to work.

### R4: No Breaking Changes to CLI Interface
The server startup, port config, and command-line usage must remain identical. Only internal event format changes.

## Edge Cases

1. **Query params with multiple values**: `?tags=a&tags=b` must produce `multiValueQueryStringParameters: {"tags": ["a", "b"]}` and `queryStringParameters: {"tags": "b"}` (last-value-wins per API Gateway behavior).
2. **Empty body**: POST/PUT with no body should produce `body: null` (not empty string).
3. **Path with trailing slash**: `/api/v2/configurations/` must produce correct `pathParameters.proxy`.
4. **OPTIONS preflight**: Must continue to bypass Lambda handler and return 204 directly.
5. **Cookie extraction**: v1 uses `headers.cookie`, not `cookies` array. Ensure cookie-bearing requests work.
6. **Thread safety**: moto mock state is shared across threads. Verify moto's thread safety guarantees.

## Out of Scope

- Changing the dashboard Lambda handler
- Adding new API endpoints
- Changing the webServer configuration in `playwright.config.ts`
- Worker count changes (Features 1320/1321)

## Success Metrics

- `python scripts/run-local-api.py` starts without error
- `curl http://localhost:8000/api/v2/tickers/search?q=AAPL` returns 200
- No `"Rejected Function URL v2 event"` in server logs
- Existing unit tests in `tests/` continue to pass (they already use v1 format)

## Adversarial Review #1

| Severity | Finding | Resolution |
|----------|---------|------------|
| CRITICAL | `app.current_event` is a Powertools singleton — `ThreadingHTTPServer` causes cross-request event clobbering (auth tokens, bodies, CORS origins) | **Resolved**: Use `threading.Lock` to serialize `lambda_handler()` invocation. Connections accepted concurrently, handler executes one-at-a-time. Handler is ~50ms with moto, so 4 queued workers wait ~200ms max. |
| CRITICAL | `get_users_table()` singleton getter has unguarded `is None` check — TOCTOU race under threads | **Resolved**: The handler serialization lock also protects singleton initialization. Only one thread enters `lambda_handler()` at a time. |
| HIGH | moto thread safety is per-table-call only; app-layer read-modify-write not protected | **Accepted**: Mirrors production DynamoDB behavior. Handler serialization prevents concurrent app-layer sequences anyway. |
| HIGH | `queryStringParameters` must be `None` (not `{}`) when absent | **Resolved**: Updated spec US3 acceptance criteria. Implementation must emit `None` matching `make_event()`. |
| HIGH | `resource` field missing from event; Powertools uses it for route matching | **Resolved**: Added to US3 acceptance criteria. Must include `"resource": "/{proxy+}"`. |
| HIGH | `requestContext.path` must include stage prefix (`/v1/api/v2/...`) | **Resolved**: Added to US3 acceptance criteria. Must match `make_event()` format. |
| MEDIUM | CORS origin clobber across threads via `app.current_event.headers` | **Resolved**: Handler serialization lock prevents concurrent `current_event` access. |
| MEDIUM | Acceptance criteria missing `stageVariables`, `requestContext.identity.userAgent` | **Resolved**: Added to US3 acceptance criteria. |
| MEDIUM | CORS origin hardcoded to `localhost:3000` | **Deferred**: Out of scope for this feature. Existing behavior, not a regression. |
| LOW | `_FakeLambdaContext.aws_request_id` is static across threads | **Resolved**: Added per-request UUID to US2 acceptance criteria. |
| LOW | `multiValueHeaders` collapses multi-value HTTP headers to single values | **Deferred**: Matches `make_event()` behavior. Production fidelity improvement for future work. |

**Gate: 0 CRITICAL, 0 HIGH remaining. All resolved or deferred with justification.**

## Clarifications

All 5 questions self-answered from codebase evidence. No user input needed.

| # | Question | Answer | Evidence |
|---|----------|--------|----------|
| 1 | Does `parse_qs` return lists? Does API Gateway use last-value-wins? | Yes to both. `parse_qs("a=1&a=2")` → `{"a": ["1","2"]}`. APIGW `queryStringParameters` keeps last value. | `make_event()` lines 199-201, AWS APIGW docs |
| 2 | Is `ThreadingHTTPServer` available in Python 3.13? | Yes, added in 3.7. | `pyproject.toml` specifies Python 3.13 |
| 3 | Does `daemon_threads=True` risk losing responses on shutdown? | No. `server_close()` on KeyboardInterrupt handles graceful shutdown. Daemon only affects interpreter exit. | `run-local-api.py` lines 315-317 |
| 4 | Is response writing outside the lock thread-safe? | Yes. Each connection has its own `self.wfile` socket. | Python `socketserver` docs, BaseRequestHandler per-connection instantiation |
| 5 | Do any E2E tests depend on v2 event format? | No. E2E tests hit HTTP endpoints, never construct Lambda events. | Grep of `frontend/tests/e2e/` for v2 format markers: 0 matches |
