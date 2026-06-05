# Feature 1319: Tasks

## Implementation Tasks

### T1: Add imports (threading, uuid, ThreadingHTTPServer)
- **File**: `scripts/run-local-api.py`
- **Lines**: 27-32 (import block)
- **Action**: Add `import threading`, `import uuid`, change `from http.server import BaseHTTPRequestHandler, HTTPServer` to `from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer`
- **Requirement**: R2
- **Status**: pending

### T2: Add handler serialization lock
- **File**: `scripts/run-local-api.py`
- **Lines**: After imports (new module-level constant)
- **Action**: Add `_handler_lock = threading.Lock()`
- **Requirement**: R2 (AR#1 CRITICAL: `app.current_event` singleton)
- **Status**: pending

### T3: Rewrite `_build_event()` — v2 → v1
- **File**: `scripts/run-local-api.py`
- **Lines**: 189-232 (full method replacement)
- **Action**: Replace Function URL v2 event construction with API Gateway REST v1 format matching `tests/conftest.py:make_event()`. Key changes:
  - Remove `"version": "2.0"`
  - `rawPath` → `path`
  - Add `httpMethod` at top level
  - Add `resource: "/{proxy+}"`
  - Add `multiValueHeaders`, `multiValueQueryStringParameters`
  - Add `pathParameters` with `proxy` capture
  - `requestContext.http.method` → `requestContext.httpMethod`
  - `requestContext.http.sourceIp` → `requestContext.identity.sourceIp`
  - Add `requestContext.path` with `/v1` stage prefix
  - Add `stageVariables: None`
  - `queryStringParameters: None` when absent (not `{}`)
- **Requirement**: R1
- **Status**: pending

### T4: Update `_build_event()` docstring
- **File**: `scripts/run-local-api.py`
- **Lines**: 190-194 (docstring)
- **Action**: Change "Lambda Function URL v2" → "API Gateway REST v1 proxy". Update comment on line 207.
- **Requirement**: R1
- **Status**: pending

### T5: Make `_FakeLambdaContext` per-request with UUID
- **File**: `scripts/run-local-api.py`
- **Lines**: 175-183
- **Action**: Change `aws_request_id` from class constant to `__init__` with `uuid.uuid4()`
- **Requirement**: R2 (AR#1 LOW: static request ID)
- **Status**: pending

### T6: Wrap `lambda_handler()` call in lock
- **File**: `scripts/run-local-api.py`
- **Lines**: 234-238 (`_invoke_handler`)
- **Action**: Add `with _handler_lock:` around `lambda_handler(event, context)`. Instantiate `_FakeLambdaContext()` per-request. Keep response writing outside lock.
- **Requirement**: R2
- **Status**: pending

### T7: Replace `HTTPServer` with `ThreadingHTTPServer`
- **File**: `scripts/run-local-api.py`
- **Lines**: 306
- **Action**: `HTTPServer(...)` → `ThreadingHTTPServer(...)`, add `server.daemon_threads = True`
- **Requirement**: R2
- **Status**: pending

### T8: Verify response format compatibility (R3)
- **File**: `scripts/run-local-api.py`
- **Lines**: 261-265
- **Action**: Read and verify that `multiValueHeaders` Set-Cookie extraction (line 262) works with v1 responses. No code change expected — current code already handles both formats.
- **Requirement**: R3
- **Status**: pending

### T9: Smoke test — start server and curl endpoints
- **Action**: Start server, verify:
  - `curl http://localhost:8000/api/v2/tickers/search?q=AAPL` → 200
  - `curl -X POST http://localhost:8000/api/v2/auth/anonymous` → 200
  - No "Rejected Function URL v2 event" in logs
- **Requirement**: US1
- **Status**: pending

### T10: Run existing pytest suite
- **Action**: `cd /home/zeebo/projects/sentiment-analyzer-gsk && python -m pytest tests/unit/ -x --timeout=60`
- **Requirement**: R4 (no breaking changes)
- **Status**: pending

## Requirement Coverage

| Requirement | Tasks |
|-------------|-------|
| R1 (Event format) | T3, T4 |
| R2 (Threading) | T1, T2, T5, T6, T7 |
| R3 (Response compat) | T8 |
| R4 (No breaking changes) | T10 |
| US1 (Valid responses) | T9 |
| US2 (Concurrent requests) | T1, T2, T6, T7 |
| US3 (Format match) | T3, T4 |

## Adversarial Review #3

**Highest-risk task**: T3 (`_build_event()` rewrite). Full method replacement with 15+ field changes. Mitigation: use `make_event()` as the canonical reference and compare field-by-field.

**Most likely rework**: `parse_qs` edge cases — empty values (`?key=`), missing values (`?key`), URL-encoded values. `parse_qs` with `keep_blank_values=True` matches API Gateway behavior for empty strings. Default `keep_blank_values=False` drops them.

**Implementation completeness**: All requirements, user stories, and AR#1 findings have ≥1 mapped task. No orphan requirements.

**READY FOR IMPLEMENTATION**
