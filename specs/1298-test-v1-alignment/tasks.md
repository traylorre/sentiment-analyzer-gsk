# Feature 1298: Tasks

## Task Dependency Graph

```
T1 (make_event v1) → T2 (transport v1) → T3 (verify)
```

## Tasks

### T1: Rewrite `make_event()` to v1 format

**File:** `tests/conftest.py`
**Requirements:** FR-001

Rewrite the function body to produce API Gateway REST proxy event format:
1. Top-level: `httpMethod`, `path`, `resource`, `stageVariables`
2. Headers: lowercase keys + `multiValueHeaders` (single-element lists)
3. Query params: `queryStringParameters` + `multiValueQueryStringParameters`
4. Path params: merge `{"proxy": path.lstrip("/")}` with explicit `path_params`
5. requestContext: `httpMethod`, `path` (with stage prefix), `stage`, `identity.sourceIp`, `identity.userAgent`, `resourcePath`, `resourceId`, `accountId`, `apiId`, `requestId`
6. Body: JSON-serialized for dicts, as-is for strings (unchanged)
7. `isBase64Encoded`: False (unchanged)
8. Update docstring: "API Gateway REST proxy event v1 format"

**Acceptance:** `make_event(method="GET", path="/health")` produces valid v1 event. All 331 callers work without changes.

---

### T2: Rewrite `LambdaInvokeTransport.build_event()` to v1 format

**File:** `tests/e2e/helpers/lambda_invoke_transport.py`
**Requirements:** FR-002

Apply same v1 format as T1. The transport's `build_event()` (or `_build_function_url_event()`) must produce v1 events for Dashboard Lambda invocations.

**Note:** If the transport has separate paths for SSE vs Dashboard Lambda, only change the Dashboard path. SSE should remain v2.

**Acceptance:** Direct Lambda invoke with v1 event returns valid response from Dashboard Lambda (after Feature 1297 resolver switch).

---

### T3: Verify all tests pass

**Requirements:** NFR-001, NFR-002
**Depends on:** T1, T2, Feature 1297 (all tasks)

1. Run unit tests: `pytest tests/unit/ -v` — all pass
2. Run integration tests: `pytest tests/integration/ -v` — all pass
3. Verify `make_function_url_event()` still produces v2 (SSE tests unaffected)
4. Verify no test files needed changes beyond fixture/transport

**Acceptance:** Zero regressions. All tests pass with v1 fixtures + `APIGatewayRestResolver`.

## Requirements Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T1 |
| FR-002 | T2 |
| FR-003 | T1 (preserve make_function_url_event) |
| NFR-001 | T3 |
| NFR-002 | T1, T2 (same commit as 1297) |

## Adversarial Review #3

### Implementation Readiness Assessment

**Highest-risk task:** T1 (make_event rewrite). A subtle field mismatch causes 331 test failures. Mitigated by: build from AWS canonical v1 example, validate with one test first.

**Most likely source of rework:** `pathParameters` handling. The merge of `{"proxy": path}` with explicit `path_params` could have edge cases for root path (`/`) or deeply nested paths. Mitigated by: unit tests already cover diverse paths.

### Gate Statement

**READY FOR IMPLEMENTATION.** 0 CRITICAL, 0 HIGH remaining. Must be committed alongside Feature 1297.
