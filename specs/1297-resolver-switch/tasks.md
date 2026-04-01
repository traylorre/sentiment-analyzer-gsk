# Feature 1297: Tasks

## Task Dependency Graph

```
T1 (resolver switch) ─┐
T2 (logging cleanup)  ├── T5 (verify)
T3 (header fixes)     │
T4 (v2 guard)        ─┘
```

T1-T4 are independent (different code locations). T5 depends on all.

**CRITICAL CONSTRAINT:** These tasks must be committed TOGETHER with Feature 1298 (test fixture alignment). The v2 rejection guard (T4) will cause all v2-format tests to return 400.

## Tasks

### T1: Switch resolver class

**File:** `src/lambdas/dashboard/handler.py`
**Requirements:** FR-001

1. Change import: `LambdaFunctionUrlResolver` → `APIGatewayRestResolver`
2. Change line 172: `app = LambdaFunctionUrlResolver()` → `app = APIGatewayRestResolver()`
3. Update module docstring: "APIGatewayRestResolver" and "API Gateway REST v1 event format"

**Acceptance:** `APIGatewayRestResolver` is the sole resolver. No imports of `LambdaFunctionUrlResolver`.

---

### T2: Simplify handler logging

**File:** `src/lambdas/dashboard/handler.py`
**Requirements:** FR-002

Simplify the `lambda_handler` logging from v2-first fallback chains to v1-direct:
- `event.get("rawPath", event.get("path", "unknown"))` → `event.get("path", "unknown")`
- `event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "unknown"))` → `event.get("httpMethod", "unknown")`

**Acceptance:** No references to `rawPath` or `requestContext.http` in handler logging.

---

### T3: Fix header case sensitivity

**Files:** `src/lambdas/dashboard/handler.py`, `src/lambdas/shared/utils/event_helpers.py`
**Requirements:** FR-001 (expanded by AR#1)

1. Fix `_get_request_origin()` in handler.py to normalize header lookup:
   ```python
   headers = app.current_event.headers or {}
   return next((v for k, v in headers.items() if k.lower() == "origin"), None)
   ```

2. Fix `get_header()` in event_helpers.py to normalize dict keys:
   ```python
   headers = event.get("headers") or {}
   normalized = {k.lower(): v for k, v in headers.items()}
   return normalized.get(name.lower(), default)
   ```

**Acceptance:** Header lookups work regardless of original case.

---

### T4: Add v2 event rejection guard

**File:** `src/lambdas/dashboard/handler.py`
**Requirements:** FR-004

Add after EventBridge scheduler check, before `app.resolve()`:
- Detect: `if event.get("version") == "2.0"`
- Log warning with structured fields
- Return HTTP 400 with clear error message

**Acceptance:** v2 events return 400 with explanatory message, not opaque 500.

---

### T5: Verify middleware compatibility and no regression

**Requirements:** FR-003, NFR-001, NFR-002
**Depends on:** T1, T2, T3, T4 + Feature 1298

1. Confirm `csrf_middleware.py` works with v1 events (reads `httpMethod` first)
2. Confirm `rate_limit.py` works with v1 events (reads `identity.sourceIp`)
3. Confirm `auth_middleware.py` works with v1 events (format-agnostic)
4. Run unit tests after Feature 1298 aligns fixtures: `pytest tests/unit/ -v`
5. Run integration tests: `pytest tests/integration/ -v`

**Acceptance:** All tests pass. No middleware changes needed.

## Requirements Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T1, T3 |
| FR-002 | T2 |
| FR-003 | T5 |
| FR-004 | T4 |
| NFR-001 | T5 |
| NFR-002 | T5 |
| US-1 | T1 |
| US-2 | T1, T4 |
| EC-1 | T1 (verified in plan) |
| EC-2 | T3 |
| EC-3 | T3 |
| EC-4 | N/A (SSE unchanged) |

## Adversarial Review #3

### Implementation Readiness Assessment

**Highest-risk task:** T3 (header case fixes). The `_get_request_origin()` change affects every CORS-enabled response. If the iteration pattern has a bug, CORS fails silently for all users. Mitigated by: (a) the fix is 2 lines, (b) existing unit tests exercise CORS paths, (c) `auth_middleware.py` already uses the same normalization pattern successfully.

**Most likely source of rework:** Implementation ordering. T1-T4 + Feature 1298 must be in the same commit. If someone merges 1297 without 1298, every unit test returns 400 (v2 rejection guard) or fails (wrong resolver). Mitigated by: both features in the same PR.

### Final Review

| Check | Status |
|-------|--------|
| All requirements mapped to tasks | PASS — 12/12 |
| Task dependency chain is acyclic | PASS |
| No shared file conflicts with 1298 | PASS — 1297 modifies handler.py + event_helpers.py; 1298 modifies conftest.py + lambda_invoke_transport.py |
| No shared file conflicts with 1299 | PASS — 1299 modifies Terraform; 1297 modifies Python |
| Rollback plan | Revert single commit |
| 3am deployment risk | LOW — resolver switch is a class swap. Header fix is 2 lines. Guard is explicit rejection. No infrastructure changes. |

### Gate Statement

**READY FOR IMPLEMENTATION.** 0 CRITICAL, 0 HIGH remaining. Must be committed alongside Feature 1298.
