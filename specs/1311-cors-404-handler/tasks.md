# Tasks: CORS 404 Handler

**Branch**: `1311-cors-404-handler` | **Date**: 2026-04-02
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

---

## Task 1: Register `@app.not_found` Handler

**FR**: FR-001, FR-002
**File**: `src/lambdas/dashboard/handler.py`

### Description

Register a Powertools `@app.not_found` handler that intercepts all unmatched routes and delegates to the existing `_make_not_found_response()` function with the request origin.

### Subtasks

- [ ] 1.1: Add `@app.not_found` decorated function after `_make_not_found_response()` (after line 302)
- [ ] 1.2: Call `_make_not_found_response(_get_request_origin())` inside the handler
- [ ] 1.3: Add DEBUG-level log entry with request path and method for operational visibility
- [ ] 1.4: Update module docstring to mention the catch-all not-found handler

### Acceptance Criteria

- Unmatched routes return HTTP 404 with `Content-Type: application/json`
- Response body is `{"detail": "Not found"}`
- Allowed origins receive CORS headers
- Unknown origins receive only `Vary: Origin`
- Existing env-gated routes are unaffected

---

## Task 2: Unit Tests for Not-Found Handler

**FR**: FR-001, FR-002
**File**: `tests/unit/test_cors_404_handler.py` (NEW)

### Description

Add unit tests that exercise the `@app.not_found` handler by making requests to unmatched routes through the Powertools resolver.

### Subtasks

- [ ] 2.1: Create test file with fixtures for CORS origins and API Gateway REST v1 event format
- [ ] 2.2: Test unmatched route with allowed origin returns 404 + CORS headers
- [ ] 2.3: Test unmatched route with unknown origin returns 404 without `Access-Control-Allow-Origin`
- [ ] 2.4: Test unmatched route with no `Origin` header returns 404 without CORS headers
- [ ] 2.5: Test response body is valid JSON `{"detail": "Not found"}`
- [ ] 2.6: Test `Vary: Origin` header is always present

### Acceptance Criteria

- All tests pass with `pytest tests/unit/test_cors_404_handler.py -v`
- Tests use monkeypatch for environment variables (no real AWS calls)
- Tests construct API Gateway REST v1 events directly (no HTTP client needed)
