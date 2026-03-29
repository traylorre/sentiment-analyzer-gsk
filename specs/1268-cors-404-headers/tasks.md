# Feature 1268: CORS 404 Headers — Tasks

## Task Dependency Graph

```
T001 (parse CORS_ORIGINS) ─┐
T002 (_get_request_origin)  ├─→ T004 (update call sites) ─→ T005 (remove dead code)
T003 (_make_not_found_response) ┘                              │
                                                                ↓
T006 (unit tests: function) ─→ T008 (update existing CORS tests)
T007 (unit tests: env-gating CORS) ─→ T009 (integration tests)
                                           ↓
                                      T010 (Playwright tests)
                                           ↓
                                      T011 (E2E tests)
                                           ↓
                                      T012 (docstring updates)
```

## Tasks

### T001: Parse CORS_ORIGINS environment variable at module level

**File**: `src/lambdas/dashboard/handler.py`
**Location**: After line 97 (`SSE_LAMBDA_URL = os.environ.get("SSE_LAMBDA_URL", "")`)
**Depends on**: None
**Estimated effort**: XS

Add module-level parsing of the `CORS_ORIGINS` environment variable:

```python
# Feature 1268: Allowed CORS origins for env-gated responses
# Parsed from comma-separated CORS_ORIGINS env var (set by Terraform from var.cors_allowed_origins)
_CORS_ALLOWED_ORIGINS: set[str] = set(
    filter(None, os.environ.get("CORS_ORIGINS", "").split(","))
)
```

**Acceptance criteria**:
- `_CORS_ALLOWED_ORIGINS` is a `set[str]` parsed from `CORS_ORIGINS` env var
- Empty string entries are filtered out
- Missing env var results in empty set (fail-closed)

---

### T002: Add `_get_request_origin()` helper function

**File**: `src/lambdas/dashboard/handler.py`
**Location**: After the `_is_dev_environment()` function (after line 120)
**Depends on**: None
**Estimated effort**: XS

```python
def _get_request_origin() -> str | None:
    """Extract Origin header from current Powertools request.

    Returns None if Origin header is missing or if called outside
    a request context (defensive).
    """
    try:
        return app.current_event.headers.get("origin")
    except Exception:
        return None
```

**Acceptance criteria**:
- Returns the `origin` header value (lowercase key per Function URL normalization)
- Returns None if header missing
- Returns None if called outside request context (no crash)

---

### T003: Create `_make_not_found_response()` function

**File**: `src/lambdas/dashboard/handler.py`
**Location**: Replace the `_NOT_FOUND_RESPONSE` constant at lines 226-230
**Depends on**: T001 (needs `_CORS_ALLOWED_ORIGINS`)
**Estimated effort**: S

```python
def _make_not_found_response(origin: str | None = None) -> Response:
    """Create 404 response with conditional CORS headers for env-gated routes.

    Feature 1268: When the requesting origin is in the allowed CORS origins
    list, includes Access-Control-Allow-Origin and related headers so browsers
    can read the response body. Without these headers, browsers block the
    response entirely (opaque CORS failure).

    This is intentionally application-level CORS for a specific case:
    env-gated routes return 404 BEFORE the normal pipeline processes the
    request, and neither API Gateway (AWS_PROXY pass-through) nor Lambda
    Function URL (AWS_IAM auth only) adds CORS headers to Lambda-returned
    responses.

    Args:
        origin: The Origin header from the request, or None.

    Returns:
        Response with 404 status, JSON body, and conditional CORS headers.
    """
    headers: dict[str, str] = {"Vary": "Origin"}

    if origin and origin in _CORS_ALLOWED_ORIGINS:
        headers.update({
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS",
            "Access-Control-Allow-Headers": (
                "Content-Type,Authorization,Accept,Cache-Control,"
                "Last-Event-ID,X-Amzn-Trace-Id,X-User-ID"
            ),
        })
        logger.debug(
            "Env-gated 404 with CORS",
            extra={"origin": origin},
        )

    return Response(
        status_code=404,
        content_type="application/json",
        body=orjson.dumps({"detail": "Not found"}).decode(),
        headers=headers,
    )
```

**Acceptance criteria**:
- Returns 404 Response with `{"detail": "Not found"}` body
- Always includes `Vary: Origin` header
- Includes 4 CORS headers when origin is in `_CORS_ALLOWED_ORIGINS`
- Omits CORS origin header when origin is None, empty, or not in allowed list
- Never uses wildcard `*` for origin
- Logs at DEBUG level when CORS headers are added

---

### T004: Update all 12 env-gated call sites

**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T002, T003
**Estimated effort**: S

Replace every `return _NOT_FOUND_RESPONSE` with `return _make_not_found_response(_get_request_origin())`.

Call sites to update:

1. `serve_index()` — `GET /` (around line 237)
2. `serve_favicon()` — `GET /favicon.ico` (around line 258)
3. `serve_chaos()` — `GET /chaos` (around line 279)
4. `serve_static()` — `GET /static/<filename>` (around line 300)
5. `api_index()` — `GET /api` (around line 345)
6. `create_chaos_experiment()` — `POST /chaos/experiments` (around line 828)
7. `list_chaos_experiments()` — `GET /chaos/experiments` (around line 891)
8. `start_chaos_experiment()` — `POST /chaos/experiments/<id>/start` (around line 924)
9. `stop_chaos_experiment()` — `POST /chaos/experiments/<id>/stop` (around line 953)
10. `rollback_chaos_experiment()` — `POST /chaos/experiments/<id>/rollback` (around line 1002)
11. `list_chaos_reports()` — `GET /chaos/reports` (around line 1044)
12. `get_chaos_report()` — `GET /chaos/reports/<id>` (around line 1080)

**Acceptance criteria**:
- All 12 sites updated
- `grep -n '_NOT_FOUND_RESPONSE' handler.py` returns zero results after change
- Each call site passes the request origin to `_make_not_found_response`

---

### T005: Remove dead `_NOT_FOUND_RESPONSE` definitions

**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T004 (all references removed first)
**Estimated effort**: XS

Remove two code blocks:
1. Lines 123-127: First (dead) `_NOT_FOUND_RESPONSE` definition
2. Lines 226-230: Second `_NOT_FOUND_RESPONSE` definition (replaced by T003's function)

**Acceptance criteria**:
- No variable named `_NOT_FOUND_RESPONSE` exists in handler.py
- `_make_not_found_response` function exists in its place

---

### T006: Unit tests for `_make_not_found_response` function

**File**: `tests/unit/test_cors_404_headers.py` (new)
**Depends on**: T003
**Estimated effort**: M

```python
class TestMakeNotFoundResponse:
    """Unit tests for _make_not_found_response (Feature 1268)."""

    def test_valid_origin_includes_cors_headers(self):
        """CORS headers present when origin is in allowed list."""

    def test_invalid_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted for unknown origin."""

    def test_none_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted when origin is None."""

    def test_empty_origin_omits_cors_origin(self):
        """Access-Control-Allow-Origin omitted for empty string origin."""

    def test_response_body_is_not_found(self):
        """Response body is always {"detail": "Not found"}."""

    def test_response_status_is_404(self):
        """Response status code is always 404."""

    def test_vary_origin_always_present(self):
        """Vary: Origin header is always present regardless of origin."""

    def test_no_wildcard_origin(self):
        """Access-Control-Allow-Origin never uses wildcard *."""

    def test_credentials_header_with_valid_origin(self):
        """Access-Control-Allow-Credentials is 'true' when origin valid."""

    def test_multiple_allowed_origins(self):
        """Only the requesting origin is reflected, not all allowed origins."""
```

Test setup: Reload handler module with `CORS_ORIGINS` set to `"https://example.com,https://app.example.com"` before each test.

**Acceptance criteria**:
- All 10 test cases pass
- Tests verify headers on the Powertools Response object (not serialized dict)
- Tests use module reload to set `_CORS_ALLOWED_ORIGINS`

---

### T007: Unit tests for env-gated CORS through full handler invocation

**File**: `tests/unit/test_chaos_security.py` (update existing `TestChaosEnvironmentGating`)
**Depends on**: T004
**Estimated effort**: S

Add new test methods to the existing class:

```python
def test_chaos_route_404_has_cors_for_valid_origin(self, mock_lambda_context):
    """Env-gated 404 includes CORS headers when Origin is in allowed list."""

def test_chaos_route_404_no_cors_for_unknown_origin(self, mock_lambda_context):
    """Env-gated 404 omits CORS origin for unknown Origin header."""

def test_chaos_route_404_no_cors_for_missing_origin(self, mock_lambda_context):
    """Env-gated 404 omits CORS origin when no Origin header sent."""
```

These tests:
1. Reload handler with `ENVIRONMENT=preprod` and `CORS_ORIGINS=https://test.example.com`
2. Create event with `make_event(headers={"origin": "https://test.example.com"})`
3. Call `handler.lambda_handler(event, context)`
4. Assert `response["headers"]` contains (or doesn't contain) CORS headers

**Acceptance criteria**:
- Tests verify CORS headers in the serialized Lambda response dict
- Tests use the handler reload pattern with both ENVIRONMENT and CORS_ORIGINS
- Existing tests still pass unchanged

---

### T008: Update existing CORS test docstrings

**File**: `tests/unit/test_dashboard_handler.py`
**Location**: Lines 585-626
**Depends on**: T003
**Estimated effort**: XS

Update the docstrings of `test_cors_handled_by_lambda_function_url` and `test_no_cors_middleware_in_app` to note the env-gated exception:

```python
"""
P0-5: Test CORS is delegated to Lambda Function URL.

CORS is handled at the infrastructure level (Lambda Function URL
configuration in Terraform), NOT at the application level. This prevents
duplicate CORS headers which browsers reject.

Exception: Feature 1268 adds CORS headers to env-gated 404 responses
specifically, because neither Lambda Function URL (AWS_IAM auth) nor
API Gateway (AWS_PROXY pass-through) adds CORS to Lambda-returned responses.

See: infrastructure/terraform/main.tf for CORS configuration.
"""
```

**Acceptance criteria**:
- Both docstrings updated with the Feature 1268 exception note
- No assertion changes

---

### T009: Integration tests for CORS on env-gated responses

**File**: `tests/integration/test_cors_404_integration.py` (new)
**Depends on**: T004
**Estimated effort**: S

Full handler invocation integration tests:

```python
@pytest.mark.integration
class TestEnvGated404CorsIntegration:
    """Integration tests for CORS on env-gated 404 responses (Feature 1268).

    These test the full handler invocation path:
    handler.py → Powertools resolver → route handler → _make_not_found_response

    Note: These do NOT test through API Gateway. API Gateway behavior
    (AWS_PROXY pass-through) is verified by E2E tests in preprod.
    """

    def test_chaos_endpoint_404_cors_through_handler(self):
        """Full handler path returns 404 with CORS for valid origin."""

    def test_dashboard_root_404_cors_through_handler(self):
        """Dashboard root / returns 404 with CORS in non-dev."""

    def test_static_file_404_cors_through_handler(self):
        """Static file route returns 404 with CORS in non-dev."""

    def test_no_cors_when_origins_env_empty(self):
        """No CORS headers when CORS_ORIGINS env var is empty."""
```

**Acceptance criteria**:
- Tests verify multiple routes (chaos, dashboard, static)
- Tests verify behavior when CORS_ORIGINS is empty
- Tests marked `@pytest.mark.integration`

---

### T010: Playwright tests for CORS behavior

**File**: `frontend/tests/e2e/cors-env-gated-404.spec.ts` (new)
**Depends on**: T004
**Estimated effort**: M

```typescript
test.describe('CORS: Env-Gated 404 Responses (Feature 1268)', () => {
  test('fetch reads 404 body when CORS headers present', async ({ page }) => {
    // Use page.route() to mock chaos API returning 404 with CORS
    // Execute fetch in page context
    // Verify response.ok === false, response.status === 404
    // Verify response.json() resolves with {"detail": "Not found"}
  });

  test('fetch fails when CORS headers missing', async ({ page }) => {
    // Use page.route() to mock chaos API returning 404 WITHOUT CORS
    // Execute fetch in page context
    // Verify fetch throws or response is opaque (status 0)
  });
});
```

**Acceptance criteria**:
- Tests use `page.route()` for network interception
- Tests verify browser CORS enforcement behavior
- Tests follow existing Playwright conventions in `frontend/tests/e2e/`

---

### T011: E2E tests for preprod CORS behavior

**File**: `tests/e2e/test_cors_404_e2e.py` (new)
**Depends on**: T004
**Estimated effort**: S

```python
@pytest.mark.preprod
class TestEnvGated404CorsE2E:
    """E2E: Verify CORS headers on env-gated 404 in preprod.

    Requires deployed preprod environment. May be deferred to gameday.
    """

    def test_chaos_endpoint_404_has_cors(self):
        """Hit chaos endpoint in preprod, verify CORS headers present."""

    def test_chaos_endpoint_404_no_cors_bad_origin(self):
        """Hit chaos endpoint with unknown origin, verify no CORS origin."""
```

Uses `httpx` or `requests` to make HTTP calls to the preprod API Gateway endpoint with explicit `Origin` header.

**Acceptance criteria**:
- Tests marked `@pytest.mark.preprod`
- Tests make real HTTP calls to preprod API Gateway
- Tests verify `Access-Control-Allow-Origin` header presence/absence

---

### T012: Verify and clean up

**File**: `src/lambdas/dashboard/handler.py`
**Depends on**: T001-T005
**Estimated effort**: XS

Post-implementation verification:
1. `grep -n '_NOT_FOUND_RESPONSE' src/lambdas/dashboard/handler.py` returns empty
2. `grep -c '_make_not_found_response' src/lambdas/dashboard/handler.py` returns 13 (1 definition + 12 call sites)
3. `grep -n '_CORS_ALLOWED_ORIGINS' src/lambdas/dashboard/handler.py` returns at least 2 (definition + usage in function)
4. Run `make validate` — passes
5. Run `pytest tests/unit/test_cors_404_headers.py tests/unit/test_chaos_security.py -v` — all pass

**Acceptance criteria**:
- Zero references to `_NOT_FOUND_RESPONSE` remain
- All unit tests pass
- Validation passes

---

## Task Summary

| Task | File(s) | Effort | Depends On |
|------|---------|--------|------------|
| T001 | handler.py | XS | None |
| T002 | handler.py | XS | None |
| T003 | handler.py | S | T001 |
| T004 | handler.py | S | T002, T003 |
| T005 | handler.py | XS | T004 |
| T006 | test_cors_404_headers.py (new) | M | T003 |
| T007 | test_chaos_security.py | S | T004 |
| T008 | test_dashboard_handler.py | XS | T003 |
| T009 | test_cors_404_integration.py (new) | S | T004 |
| T010 | cors-env-gated-404.spec.ts (new) | M | T004 |
| T011 | test_cors_404_e2e.py (new) | S | T004 |
| T012 | handler.py | XS | T001-T005 |

**Total estimated effort**: ~M-L (straightforward, well-scoped changes)

## Cross-Artifact Consistency Check

- **spec.md FR-001** (CORS headers on env-gated 404) → T003 (function), T004 (call sites)
- **spec.md FR-002** (origin validation) → T003 (origin in allowed set check)
- **spec.md FR-003** (consistent across all routes) → T004 (all 12 sites)
- **spec.md FR-004** (no CORS on non-gated) → T003 (only in _make_not_found_response)
- **spec.md FR-005** (preflight handled) → Not a code change, verification only
- **spec.md NFR-001** (performance) → T001 (set lookup is O(1))
- **spec.md NFR-002** (security) → T003 (no wildcard, fail-closed), T006 (test_no_wildcard)
- **spec.md NFR-003** (observability) → T003 (DEBUG log)
- **plan.md Phase 1-6** → T001-T012 (1:1 mapping)
- **AR1-002** (dead code) → T005
- **AR1-003** (origin helper) → T002
- **AR1-004** (Vary header) → T003
- **AR1-006** (test CORS_ORIGINS) → T006, T007
- **AR2-001** (Playwright path) → T010
- **AR2-005** (update existing tests) → T007
- **AR2-006** (reload helper) → T007
- **AR2-008** (docstring updates) → T008

---

## Adversarial Review #3

**Reviewer**: Self-adversarial pass on tasks
**Date**: 2026-03-28

### Finding AR3-001: T003 and T005 ordering conflict

**Severity**: Low

T003 says "Replace the `_NOT_FOUND_RESPONSE` constant at lines 226-230" and T005 says "Remove `_NOT_FOUND_RESPONSE` at lines 226-230." These are the same operation. T003 should create the function at the same location (replacing the constant), and T005 should only handle removing the DEAD code at lines 123-127.

**Resolution**: Clarify: T003 replaces the constant at line 226-230 with the function. T005 removes only the dead definition at lines 123-127. Update T005 scope.

### Finding AR3-002: T004 line numbers will shift after T003/T005

**Severity**: Low (informational)

After T001 adds code near line 97 and T003 replaces code at line 226, the line numbers for T004's call sites will shift by a few lines. The line numbers in T004 are approximate ("around line X") which is correct. Implementation should use grep/search rather than hardcoded line numbers.

**Resolution**: No change needed — line numbers are already marked as approximate.

### Finding AR3-003: T006 tests the Response object directly but T007 tests the serialized dict

**Severity**: Low (intentional design)

T006 tests `_make_not_found_response()` return value (Powertools Response object with `.headers`, `.status_code`). T007 tests the Lambda handler response dict (`response["headers"]`). This is correct — T006 tests the function in isolation, T007 tests the full pipeline. The Response object's `.headers` dict and the serialized Lambda response's `headers` dict may have slightly different structures (Powertools may merge or transform headers during serialization).

Need to verify: does Powertools preserve custom headers exactly as-is when serializing a Response? Based on the Powertools source, yes — `headers` from Response are merged into the Lambda response dict's `headers` field.

**Resolution**: Both test approaches are correct. T006 uses Response attributes, T007 uses serialized dict. No change needed.

### Finding AR3-004: T010 Playwright test may not accurately test CORS

**Severity**: Medium

`page.route()` intercepts requests at the Playwright network layer BEFORE the browser's CORS enforcement. When you fulfill a route with `page.route()`, the browser treats it as a same-origin response — CORS doesn't apply. To test actual CORS behavior, you'd need a real cross-origin server.

This means the Playwright tests as described won't actually validate CORS behavior. They'd validate that the frontend can parse a 404 JSON response, but NOT that CORS headers make the difference.

**Alternative approaches**:
1. Use `page.evaluate(() => fetch('https://cross-origin-url/chaos/experiments'))` to make a real cross-origin request (requires a test server)
2. Accept that Playwright tests here are limited to "frontend handles 404 gracefully" and move CORS verification to unit/integration/E2E tests
3. Use `page.route()` but document the limitation

**Resolution**: Downgrade T010 to "frontend 404 handling" tests (not CORS validation). CORS is validated by T006/T007/T009/T011. Update T010 description to be honest about what it tests.

### Finding AR3-005: T011 E2E test uses httpx but doesn't verify CORS enforcement

**Severity**: Low

httpx (or requests) is not a browser — it doesn't enforce CORS. The E2E test verifies that the CORS headers ARE PRESENT in the response, but doesn't verify that a browser would actually accept them. This is sufficient because:
1. CORS header correctness is verified by unit tests
2. Browser CORS enforcement is a well-tested browser standard
3. If the headers are present and correct, browsers will accept them

**Resolution**: No change — verifying header presence in E2E is sufficient.

### Finding AR3-006: Task dependency graph shows T006 → T008 but T008 only depends on T003

**Severity**: Low

The dependency graph shows T006 feeding into T008, but T008 (docstring updates) doesn't depend on T006 (unit tests). T008 only depends on T003 (knowing the function exists to document it). The graph is slightly misleading.

**Resolution**: The graph is for visual ordering, not strict dependencies. The task table correctly shows dependencies. No change needed.

### Finding AR3-007: Missing test — CORS_ORIGINS with trailing/leading whitespace

**Severity**: Low

If Terraform outputs `CORS_ORIGINS = "https://a.com, https://b.com"` (note space after comma), the `split(",")` will produce `" https://b.com"` which won't match `"https://b.com"`. The `filter(None, ...)` removes empty strings but not whitespace-only strings.

**Resolution**: Add `.strip()` to the origin parsing:
```python
_CORS_ALLOWED_ORIGINS: set[str] = set(
    origin.strip()
    for origin in os.environ.get("CORS_ORIGINS", "").split(",")
    if origin.strip()
)
```
Add a unit test for this edge case in T006.

### Summary

| ID | Severity | Status |
|----|----------|--------|
| AR3-001 | Low | Clarify: T005 only removes dead code at line 123 |
| AR3-002 | Low | No change, line numbers already approximate |
| AR3-003 | Low | No change, both approaches correct |
| AR3-004 | Medium | Downgrade T010 scope to frontend 404 handling |
| AR3-005 | Low | No change, header presence check sufficient |
| AR3-006 | Low | No change, visual ordering only |
| AR3-007 | Low | Fix: add .strip() to origin parsing, add edge case test |
