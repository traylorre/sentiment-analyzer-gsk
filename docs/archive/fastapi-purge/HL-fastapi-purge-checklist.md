# High-Level FastAPI/Mangum Purge Checklist

**Created:** 2026-02-09
**Status:** Not Started
**Branch:** TBD (create from `main`)
**Codename:** Final Purge

---

## Executive Summary

The dashboard Lambda currently uses **FastAPI + Mangum** as a request/response abstraction layer over AWS Lambda Proxy Integration. This adds:
- ~30ms latency per invocation (framework overhead)
- ~15MB RAM per invocation (FastAPI, Starlette, Uvicorn, Mangum)
- Dependency surface area (4 packages + transitive deps)
- Signature mismatch complexity (`Depends`, `Query` vs `event`/`context`)

**Goal:** Replace with direct AWS Lambda handler using native `event`/`context` pattern.

---

## Work Order

| # | Task | File | Status | Priority |
|---|------|------|--------|----------|
| 1 | Audit current FastAPI surface area | [audit-fastapi-surface.md](./audit-fastapi-surface.md) | [ ] TODO | P0 |
| 2 | Design native handler signature | [design-native-handler.md](./design-native-handler.md) | [ ] TODO | P1 |
| 3 | Replace request parsing (Query/Depends → event dict) | [fix-request-parsing.md](./fix-request-parsing.md) | [ ] TODO | P2 |
| 4 | Replace response format (Response → proxy dict) | [fix-response-format.md](./fix-response-format.md) | [ ] TODO | P3 |
| 5 | Replace middleware (timing, logging, X-Ray) | [fix-middleware-replacement.md](./fix-middleware-replacement.md) | [ ] TODO | P4 |
| 6 | Replace dependency injection (Depends → singletons) | [fix-dependency-injection.md](./fix-dependency-injection.md) | [ ] TODO | P5 |
| 7 | Update Terraform handler path | [fix-terraform-handler.md](./fix-terraform-handler.md) | [ ] TODO | P6 |
| 8 | Remove packages from requirements | [fix-requirements-cleanup.md](./fix-requirements-cleanup.md) | [ ] TODO | P7 |
| 9 | Update test suite (TestClient → mock event) | [fix-test-migration.md](./fix-test-migration.md) | [ ] TODO | P8 |
| 10 | Validation & smoke test | [fix-validation-smoketest.md](./fix-validation-smoketest.md) | [ ] TODO | P9 |

**Rationale for order:**
1. **Audit first** - Must know full surface area before cutting anything
2. **Handler design** - Define the target shape before migrating pieces
3. **Request parsing** - Core input transformation (FastAPI → event dict)
4. **Response format** - Core output transformation (Response → proxy dict)
5. **Middleware** - Cross-cutting concerns need explicit replacement
6. **Dependency injection** - Swap Depends() for static singletons
7. **Terraform** - Point handler to new entrypoint
8. **Requirements** - Remove dead packages only after code is migrated
9. **Tests** - Update test harness to match new handler shape
10. **Validation** - End-to-end verification that everything works

---

## Architecture: Before vs After

### Before (FastAPI + Mangum)

```
API Gateway → Lambda Runtime → Mangum(app) → FastAPI Router → Handler Function
                                    ↑              ↑              ↑
                              Translates        Routes &      Depends(),
                              event→ASGI     middleware      Query(), etc.
```

### After (Native Handler)

```
API Gateway → Lambda Runtime → lambda_handler(event, context)
                                    ↑
                              Direct event dict
                              parsing + proxy response
```

---

## Key Transformations

| FastAPI Pattern | Native Replacement | File Ref |
|----------------|-------------------|----------|
| `Query("ticker")` | `event["queryStringParameters"]["ticker"]` | [fix-request-parsing.md](./fix-request-parsing.md) |
| `Response(json)` | `{"statusCode": 200, "headers": {...}, "body": json.dumps(...)}` | [fix-response-format.md](./fix-response-format.md) |
| `@app.middleware("http")` | Inline two-phase handler logic | [fix-middleware-replacement.md](./fix-middleware-replacement.md) |
| `Depends(get_db)` | Static singleton `get_dynamo_client()` | [fix-dependency-injection.md](./fix-dependency-injection.md) |
| `handler = "main.handler"` | `handler = "ohlc.lambda_handler"` | [fix-terraform-handler.md](./fix-terraform-handler.md) |
| `TestClient(app)` | `lambda_handler(mock_event, mock_context)` | [fix-test-migration.md](./fix-test-migration.md) |

---

## Packages to Remove

| Package | Current Role | Replacement |
|---------|-------------|-------------|
| `fastapi` | Request routing, validation | Direct event parsing |
| `mangum` | ASGI-to-Lambda adapter | Removed (no adapter needed) |
| `uvicorn` | ASGI server (dev only) | Removed (Lambda runtime) |
| `starlette` | FastAPI dependency | Removed (transitive) |

---

## Files to Modify

### Primary Changes
| File | Change |
|------|--------|
| `src/lambdas/dashboard/ohlc.py` | Replace FastAPI handler with `lambda_handler(event, context)` |
| `src/lambdas/dashboard/main.py` | DELETE - no longer needed (app object + Mangum wrapper) |
| `infrastructure/terraform/main.tf` | Update `handler` from `main.handler` to `ohlc.lambda_handler` |
| `requirements.txt` | Remove fastapi, mangum, uvicorn, starlette |
| `requirements-ci.txt` | Remove same packages |

### Test Files
| File | Change |
|------|--------|
| `tests/unit/dashboard/test_ohlc.py` | Replace TestClient with direct handler invocation |
| `tests/integration/test_dashboard.py` | Update integration test harness |
| `tests/e2e/*.spec.ts` | No change (Playwright hits API Gateway, transparent) |

---

## Blind Spots Identified

### Structural
1. **Multiple routers** - FastAPI app may have more than just OHLC (news, tickers, SSE). Each router = separate migration
2. **Path parameters** - `/api/v2/tickers/{ticker}/ohlc` routing must be handled by API Gateway, not FastAPI
3. **CORS handling** - FastAPI middleware may handle CORS; must move to API Gateway config
4. **Error handlers** - `@app.exception_handler()` must become try/except in handler
5. **Request validation** - Pydantic models in FastAPI auto-validate; must add explicit validation

### Operational
6. **Rollback plan** - If native handler fails in prod, how to revert quickly
7. **Canary deployment** - Can we run both handlers in parallel during migration?
8. **API Gateway config** - Does current API Gateway config assume FastAPI routing?
9. **Health check endpoint** - `/health` or `/ping` may exist in FastAPI; needs equivalent

### Performance
10. **Cold start delta** - Measure before/after to prove improvement
11. **Memory reduction** - Measure before/after to validate 15MB savings claim
12. **Two-phase handler** - asyncio.wait_for (Phase 1) + write-through (Phase 2) must be preserved

### Testing
13. **Test coverage gap** - TestClient may test routes that don't exist in native handler
14. **Mock event fidelity** - Mock events must match real API Gateway proxy format exactly
15. **Playwright tests** - Should be transparent but verify no FastAPI-specific behavior leaks through

---

## Success Criteria

### Functional
- [ ] All existing API endpoints return identical responses
- [ ] CORS headers present in responses
- [ ] Error responses match previous format
- [ ] Cache behavior unchanged

### Performance
- [ ] Cold start latency reduced by >= 20ms
- [ ] Memory usage reduced by >= 10MB
- [ ] No regression in warm invocation latency

### Reliability
- [ ] All unit tests pass with new handler shape
- [ ] All integration tests pass
- [ ] Playwright E2E tests pass without modification
- [ ] No new error types in CloudWatch after deployment

### Cleanup
- [ ] fastapi, mangum, uvicorn, starlette removed from all requirements files
- [ ] No remaining imports of removed packages
- [ ] `main.py` deleted
- [ ] Terraform handler path updated

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Missed router/endpoint | Medium | High | Audit phase catalogs all routes |
| CORS breakage | Medium | High | Test CORS explicitly in smoke test |
| API Gateway routing mismatch | Low | Critical | Verify API Gateway config before deploy |
| Test coverage regression | Medium | Medium | Map TestClient tests 1:1 to handler tests |
| Stale imports in other files | Low | Low | grep for removed packages after cleanup |

---

## Context Protection Strategy

This work spans multiple sessions. To protect against context compaction:

1. **CONTEXT-CARRYOVER files** - Updated at end of each session with decisions + state
2. **Per-task files** - Each task file is self-contained with full problem/solution
3. **No file > 200 lines** - Prevents context window pressure when reading
4. **Cross-references** - Every sub-file links back to this checklist
5. **Decision log** - Architectural decisions recorded in sub-files, not just this overview

---

## References

- User briefing: "Cheap and Streamlined" AWS-native handler pattern
- Round 19: Static Init Singletons (`get_dynamo_client()`)
- Round 21.1: Two-Phase Handler pattern
- Round 26.3: Signature Mismatch analysis
- `docs/cache/HL-cache-remediation-checklist.md` - Parallel structure reference

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-02-09 | Document created from user briefing |
