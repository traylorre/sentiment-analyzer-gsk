# Tasks: FastAPI/Mangum Permanent Removal

**Input**: Design documents from `/specs/001-fastapi-purge/`
**Prerequisites**: plan.md (tech stack), spec.md (62 FRs, 8 user stories), research.md (7 decisions), data-model.md (contracts), quickstart.md (migration patterns)
**Organization**: Tasks grouped by user story for independent implementation. Tests accompany each phase as the spec mandates test migration (US5).

## Phase 1: Setup (Shared Infrastructure)

> Purpose: Install new dependencies, create shared utilities, establish test fixtures that all subsequent phases depend on.

- [x] T001 Add orjson dependency to pyproject.toml `[project.optional-dependencies]` and src/lambdas/dashboard/requirements.txt and src/lambdas/sse_streaming/requirements.txt (FR-011, FR-012, R3)
- [x] T002 Create src/lambdas/shared/utils/event_helpers.py with `get_header(event, name, default)` for case-insensitive header lookup (FR-061, R7) and `get_query_params(event)` / `get_path_params(event)` returning empty dict on None (FR-043)
- [x] T003 Create src/lambdas/shared/utils/url_decode.py with `decode_path_param(value)` using `urllib.parse.unquote()` for URL-encoded path parameters like BRK%2EB → BRK.B (FR-044)
- [x] T004 Create src/lambdas/shared/utils/cookie_helpers.py with `parse_cookies(event)` and `make_set_cookie(name, value, httponly, secure, samesite, max_age, path)` using stdlib `http.cookies.SimpleCookie` (FR-049, FR-050, R5)
- [x] T005 Create src/lambdas/shared/utils/response_builder.py with `json_response(status_code, body, headers=None)` using orjson.dumps().decode() and `error_response(status_code, detail)` and `validation_error_response(pydantic_error)` producing FastAPI-parity 422 format (FR-005, FR-009, FR-011)
- [x] T006 Create src/lambdas/shared/utils/event_validator.py with `validate_apigw_event(event)` checking for httpMethod, resource, requestContext keys; raise on unrecognized shapes (FR-045)
- [x] T007 Create src/lambdas/shared/utils/payload_guard.py with `check_response_size(body_str)` detecting >6MB responses before return, returning 502 with ERROR log (FR-046)
- [x] T008 Add `make_event()` mock Lambda event factory fixture to tests/conftest.py supporting method, path, path_params, query_params, headers, body, cookies parameters per contracts/mock-event-factory.yaml (FR-058)
- [x] T009 Add `mock_lambda_context` fixture to tests/conftest.py returning a mock object with function_name, memory_limit_in_mb, invoked_function_arn, aws_request_id attributes

> **Checkpoint**: `pytest tests/unit/ -k "test_event_helpers or test_cookie or test_response_builder"` passes (utilities are independently testable).

## Phase 2: Foundational (Blocking Prerequisites)

> Purpose: Migrate shared modules that all handlers depend on. MUST complete before user story phases.

> ⚠️ CRITICAL: These tasks modify shared code used by multiple handlers. Complete and verify before proceeding to handler migration.

- [x] T010 Create src/lambdas/shared/dependencies.py with 6 lazy-init singleton getters: `get_users_table()`, `get_tiingo_adapter()`, `get_finnhub_adapter()`, `get_ticker_cache_dependency()`, `get_no_cache_headers()`, `get_require_csrf()` — replacing 68 Depends() invocations (FR-013, R6)
- [x] T011 Migrate src/lambdas/shared/middleware/csrf_middleware.py — replace FastAPI `Request`/`HTTPException`/`Depends` with raw event dict extraction using `get_header()` and `parse_cookies()`, return proxy error dict on failure (FR-018)
- [x] T012 Migrate src/lambdas/shared/middleware/require_role.py — replace FastAPI `Depends`/`HTTPException` with Powertools middleware signature `(app, next_middleware)` extracting auth from `app.current_event` (FR-018)
- [x] T013 Migrate src/lambdas/shared/auth/ modules — replace `extract_auth_context` and `extract_auth_context_typed` to extract Bearer tokens from raw event["headers"]["authorization"] instead of FastAPI Request (FR-031)
- [x] T014 [P] Replace FastAPI `Response` base class parameter usage in `no_cache_headers` and `set_refresh_token_cookie` functions (src/lambdas/dashboard/router_v2.py) with direct header dict manipulation on proxy response (FR-042)
- [x] T015 Create top-level error handler pattern in src/lambdas/shared/utils/error_handler.py — `handle_request(handler_fn, event, context)` wrapping handler in try/except, converting ValidationError → 422 and Exception → 500 with full traceback logging (FR-023, FR-024, FR-039, FR-010)
- [x] T016 Replace FastAPI lifespan function (src/lambdas/dashboard/handler.py lines 124-139, currently no-op with logging only) with module-level logging during Lambda init (FR-028)
- [x] T017 Preserve X-Ray `patch_all()` at module level before other imports in src/lambdas/dashboard/handler.py and src/lambdas/sse_streaming/handler.py (FR-034)

> **Checkpoint**: All shared modules importable with zero fastapi/starlette imports. `grep -rn "from fastapi\|from starlette" src/lambdas/shared/` returns zero matches.

## Phase 3: US1 — Dashboard API Continues Working (P1)

> **Goal**: Migrate dashboard Lambda entry point and all 11 routers from FastAPI+Mangum to Powertools APIGatewayRestResolver. All 102 endpoints return identical responses.
>
> **Independent Test**: `pytest tests/unit/test_dashboard_handler.py -v` passes with native handler invocation.

### Implementation

- [x] T018 [US1] Rewrite src/lambdas/dashboard/handler.py — replace `FastAPI()` app + `Mangum(app, lifespan="off")` with `APIGatewayRestResolver()` + `@logger.inject_lambda_context @tracer.capture_lambda_handler def lambda_handler(event, context): return app.resolve(event, context)` including all 11 `app.include_router()` calls (FR-001, FR-026, R1)
- [x] T019 [US1] Migrate src/lambdas/dashboard/router_v2.py — convert 9 FastAPI `APIRouter(prefix=...)` definitions to Powertools `Router()` with route decorators using full paths (e.g., `@router.get("/api/v2/auth/login")`) replacing implicit prefix concatenation (FR-051). Replace all `Depends()` calls with singleton getter calls. Replace `async def` with `def` (FR-013)
- [x] T020 [US1] Migrate src/lambdas/dashboard/ohlc.py — convert FastAPI router to Powertools Router, replace `Depends(get_tiingo_adapter)` / `Depends(get_finnhub_adapter)` with `get_tiingo_adapter()` / `get_finnhub_adapter()` calls, add explicit `OHLCRequestContext.model_validate()` at entry (FR-001, FR-008)
- [x] T021 [US1] Migrate src/lambdas/dashboard/alerts.py — already zero FastAPI imports, pure service functions (FR-037)
- [x] T022 [P] [US1] Migrate src/lambdas/dashboard/sentiment.py — already zero FastAPI imports, pure service functions (FR-040)
- [x] T023 [P] [US1] Replace dashboard sse.py 3 SSE endpoints — convert EventSourceResponse (sse-starlette) to direct SSE-formatted text/event-stream responses with `data: {json}\n\n` format using orjson (FR-041)
- [x] T024 [US1] Preserve static file serving for 8 whitelisted files — already implemented in handler.py using Powertools Response (done in T018) (FR-027, FR-036)
- [x] T025 [US1] Update src/lambdas/dashboard/Dockerfile — CMD already correct, updated comment to remove FastAPI/Mangum references (FR-015)
- [x] T026 [US1] Remove implicit FastAPI-generated endpoints (/docs, /redoc, /openapi.json) — verified eliminated automatically by removing FastAPI app (FR-032)

> **Checkpoint**: Dashboard handler invocable with mock event dict. `python -c "from src.lambdas.dashboard.handler import lambda_handler; print(lambda_handler({'httpMethod':'GET','path':'/api/v2/sentiment','headers':{},'queryStringParameters':None,'pathParameters':None,'body':None,'isBase64Encoded':False,'requestContext':{'requestId':'test'}},None))"` returns valid proxy response.

## Phase 4: US3 — Input Validation Produces Identical 422 Errors (P3)

> **Goal**: All 16 Pydantic request models validated explicitly at handler entry ("validation at the gate"). 422 responses byte-identical to FastAPI format.
>
> **Independent Test**: Send invalid params to each endpoint, verify 422 body matches `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.

### Implementation

- [x] T027 [US3] Add explicit `model_validate()` calls at entry of all POST/PATCH handlers in router_v2.py for: ConfigurationCreate, ConfigurationUpdate, TickerAdd, SessionCreate, AnonymousSessionCreate, RefreshTokenRequest, MagicLinkRequest, NotificationPreferences, OAuthCallback, AdminSessionRevoke — with try/except ValidationError → `validation_error_response()` (FR-007, FR-037)
- [x] T028 [US3] Add explicit `model_validate()` at entry of GET handlers using query/path params: OHLCRequestContext (ohlc.py), SentimentHistoryRequest (sentiment.py), UserLookup (router_v2.py), StreamConfig (sse_streaming/config.py) — mapping param source to loc prefix (query→"query", path→"path") (FR-008)
- [x] T029 [US3] Replace 3 `response_model=` usages in ohlc.py (OHLCResponse), sentiment.py (SentimentHistoryResponse), and sse handler (StreamStatus) with explicit `Model.model_validate(data).model_dump()` before orjson serialization (FR-040)
- [x] T030 [US3] Handle `Body(default=None)` pattern for AnonymousSessionCreate and RefreshTokenRequest — parse event["body"] as None-safe JSON, validate conditionally (FR-037 edge case)

> **Checkpoint**: `curl` (or mock event) with `resolution=INVALID` returns 422 with `{"detail": [{"loc": ["query", "resolution"], "msg": "...", "type": "enum"}]}`.

## Phase 5: US6 — Middleware Replaced With Explicit Per-Handler Logic (P6)

> **Goal**: CSRF, auth, and role middleware fully operational on raw event dicts. Zero FastAPI imports in middleware modules.
>
> **Independent Test**: Protected endpoint rejects unauthenticated request with 401/403.

### Implementation

- [x] T031 [US6] Wire Powertools middleware decorators on protected routes — add `middlewares=[require_csrf_middleware]` and `middlewares=[require_admin_middleware]` to applicable route decorators in router_v2.py (FR-018, FR-019)
- [x] T032 [US6] Implement cookie-based CSRF validation in csrf_middleware.py using `parse_cookies(event)` + `get_header(event, "x-csrf-token")` comparison, return 403 proxy response on mismatch (FR-049, FR-050)
- [x] T033 [US6] Implement Set-Cookie headers for CSRF token (httponly=False, secure=True, samesite="none") and refresh token (httponly=True, secure=True, samesite="strict") using `make_set_cookie()` in response construction (FR-049)
- [x] T034 [P] [US6] Verify auth extraction from event["requestContext"]["authorizer"] and event["headers"]["authorization"] preserves all existing 401/403 behavior (FR-019, FR-031)

> **Checkpoint**: `grep -rn "from fastapi\|from starlette" src/lambdas/shared/middleware/` returns zero matches. Auth/CSRF tests pass.

## Phase 6: US7 — Routing Defined in Exactly One Place (P7)

> **Goal**: 405 Method Not Allowed for valid routes with wrong HTTP method. All routes defined once in handler code.
>
> **Independent Test**: `DELETE /api/v2/sentiment` (GET-only route) returns 405 with `Allow: GET, HEAD` header.

### Implementation

- [x] T035 [US7] Implement custom 405 handler in src/lambdas/dashboard/handler.py — on Powertools 404, check if event["path"] matches any registered route with a different method; if yes return 405 with Allow header listing valid methods (FR-017)
- [x] T036 [US7] Verify all 9 APIRouter prefix= paths (/api/v2/auth, /api/v2/configurations, /api/v2/tickers, /api/v2/alerts, /api/v2/notifications, /api/v2/market, /api/v2/users, /api/v2/timeseries, /api/v2/admin) are preserved as Powertools Router route prefixes in include_router() (FR-051)

> **Checkpoint**: Wrong-method request returns 405 (not 404). Route list matches pre-migration exactly.

## Phase 7: US2 — SSE Streaming Continues Working (P2)

> **Goal**: SSE Lambda migrated from FastAPI+Uvicorn+Lambda Web Adapter to raw awslambdaric RESPONSE_STREAM. Live sentiment updates delivered identically.
>
> **Independent Test**: Mock response_stream receives `data: {json}\n\n` events. Client disconnection detected via write exception.

> Note: This phase is INDEPENDENT of Phases 3-6 (different Lambda). Can execute in parallel.

### Implementation

- [x] T037 [US2] Rewrite src/lambdas/sse_streaming/handler.py — replace FastAPI app + Uvicorn + Lambda Web Adapter with custom runtime bootstrap + generator-based handler yielding SSE bytes via chunked transfer encoding to Lambda Runtime API (FR-002, FR-025, R2)
- [x] T038 [US2] Implement SSE event formatting — `_format_sse_event()` writes `event: {type}\nid: {id}\ndata: {json}\n\n` for typed events, with `_streaming_metadata()` for HTTP prelude (FR-025, FR-041)
- [x] T039 [US2] Implement client disconnection detection — `_consume_async_stream()` catches BrokenPipeError/IOError/RuntimeError, GeneratorExit propagation triggers finally blocks for connection cleanup (FR-048)
- [x] T040 [US2] Preserve ConnectionManager thread-safety — connection.py unchanged, threading.Lock() preserved. Handler uses connection_manager.release() in finally blocks (FR-035)
- [x] T041 [US2] Remove SSE /health endpoint (Lambda Web Adapter readiness check only) and /debug endpoint entirely — not present in new handler (FR-054, FR-033)
- [x] T042 [US2] Rewrite src/lambdas/sse_streaming/Dockerfile — kept python:3.13-slim base (custom runtime needs Python), removed Lambda Web Adapter COPY, removed EXPOSE 8080, removed AWS_LWA_* ENV vars, ENTRYPOINT runs bootstrap, WORKDIR /var/task (FR-052 items a-f)
- [x] T043 [US2] Fix import paths for WORKDIR change `/app` → `/var/task` — removed all `try/except ImportError` fallback patterns, single deterministic import path via PYTHONPATH=/var/task/packages:/var/task (FR-057)
- [x] T044 [US2] Remove sse-starlette from src/lambdas/sse_streaming/requirements.txt and replace all `EventSourceResponse` / `StreamingResponse` imports with direct generator yields (FR-041, FR-014)

> **Checkpoint**: SSE handler callable with mock event + mock response_stream. Stream writes produce valid SSE format.

## Phase 8: US5 — All Tests Pass With Native Handler Invocation (P5)

> **Goal**: Migrate 22 TestClient files, 16 contract test files (462 tests), 6 dependency_overrides files. Test count ≥ pre-migration.
>
> **Independent Test**: `pytest tests/unit/ tests/integration/ tests/contract/ -v` all pass with zero fastapi/starlette imports.

### Implementation

- [ ] T045 [US5] Remove unused `ohlc_test_client` fixture from tests/conftest.py (lines 504-531) — dead code using dependency_overrides and TestClient that is never imported by any test (FR-038)
- [ ] T046 [US5] Migrate 3 OHLC integration test files using dependency_overrides (tests/integration/ohlc/test_happy_path.py, test_boundary.py, test_error_resilience.py) — replace `app.dependency_overrides[get_tiingo_adapter]` with `patch("src.lambdas.dashboard.ohlc.get_tiingo_adapter", return_value=mock)`, replace TestClient with `make_event()` + direct handler call (FR-038, FR-020)
- [ ] T047 [US5] Migrate 2 integration sentiment_history test files (tests/integration/sentiment_history/test_happy_path.py, test_boundary.py) — same TestClient → make_event() pattern (FR-020)
- [ ] T048 [US5] Migrate 2 Lambda auth test files using dependency_overrides (tests/unit/lambdas/dashboard/test_admin_sessions_revoke_auth.py, test_users_lookup_auth.py) — replace `app.dependency_overrides[get_users_table]` with `patch()` (FR-038)
- [ ] T049 [P] [US5] Migrate module-level TestClient construction in tests/unit/dashboard/test_ohlc.py and tests/unit/dashboard/test_sentiment_history.py — move `app = FastAPI(); client = TestClient(app)` from module level into fixtures (FR-060)
- [ ] T050 [P] [US5] Migrate tests/unit/dashboard/test_sse.py — replace FastAPI WebSocket/TestClient imports with mock event dict testing (FR-020)
- [ ] T051 [P] [US5] Migrate tests/unit/dashboard/test_cache_headers.py and test_refresh_cookie.py — replace `from fastapi import Response` with plain dict test patterns (FR-062)
- [ ] T052 [P] [US5] Migrate tests/unit/lambdas/dashboard/test_serve_index.py and test_atomic_magic_link_router.py — TestClient → make_event() (FR-020)
- [ ] T053 [P] [US5] Migrate tests/unit/lambdas/shared/middleware/test_require_role.py and tests/unit/middleware/test_csrf.py — FastAPI Request/app imports → raw event dict testing (FR-020)
- [ ] T054 [P] [US5] Migrate 4 SSE streaming unit tests (tests/unit/sse_streaming/test_config_stream.py, test_connection_limit.py, test_global_stream.py, test_path_normalization.py) — replace Starlette/FastAPI TestClient with mock event + mock response_stream (FR-020)
- [ ] T055 [P] [US5] Migrate tests/unit/test_dashboard_handler.py and test_preload_strategy.py — TestClient → make_event() + direct handler invocation (FR-020)
- [ ] T056 [P] [US5] Migrate 2 integration dashboard tests (tests/integration/test_dashboard_dev.py, test_dashboard_preprod.py) — TestClient → make_event() (FR-020)
- [ ] T057 [US5] Migrate tests/integration/test_e2e_lambda_invocation_preprod.py — TestClient → make_event() if applicable; may already use direct invocation (FR-020)
- [ ] T058 [US5] Migrate all 16 contract test files (462 tests in tests/contract/) — replace `response.status_code` → `response["statusCode"]`, `response.json()` → `json.loads(response["body"])`, `response.headers` → `response["headers"]` (FR-059)
- [ ] T059 [US5] Verify case-insensitive header lookup works in all migrated tests — ensure tests using `headers={"Authorization": "Bearer ..."}` work with lowercase normalization in `make_event()` (FR-061)
- [ ] T060 [US5] Verify E2E tests (tests/e2e/) pass UNMODIFIED — they hit API Gateway/Function URLs, not handler directly; no migration needed (SC-006)

> **Checkpoint**: `pytest tests/ -v --ignore=tests/e2e` passes. `grep -rn "from fastapi\|from starlette\|TestClient" tests/ --include="*.py"` returns zero matches (excluding tests/e2e/).

## Phase 9: US4 — Complete Dependency Elimination Verified (P4)

> **Goal**: Zero trace of FastAPI/Mangum/Uvicorn/Starlette anywhere in codebase. Clean room verification.
>
> **Independent Test**: SC-008 grep scan returns zero matches across entire repo (specs/docs/fastapi-purge/ exempt).

### Implementation

- [ ] T061 [US4] Remove fastapi, mangum, uvicorn, starlette, sse-starlette from root requirements.txt, requirements-dev.txt, requirements-ci.txt, and all per-Lambda requirements.txt files (FR-014)
- [ ] T062 [US4] Remove ruff B008 lint exceptions for Depends()/Query() from pyproject.toml `[tool.ruff.per-file-ignores]` or `[tool.ruff.lint]` (FR-021)
- [ ] T063 [US4] Remove or replace run-local-api.py — eliminate FastAPI/Uvicorn dependency, replace with direct handler invocation script or SAM CLI instructions (FR-022)
- [ ] T064 [US4] Update CI/CD deploy.yml smoke test imports — replace `from fastapi import FastAPI` and `from mangum import Mangum` (preprod ~line 675, prod ~line 1556) with native handler import verification (FR-055)
- [ ] T065 [US4] Remove AWS_LWA_INVOKE_MODE and AWS_LWA_READINESS_CHECK_PATH from Terraform SSE Lambda module environment_variables block in infrastructure/terraform/ (FR-056, FR-052g)
- [ ] T066 [US4] Run full trace removal scan (FR-053) — remove all comments, docstrings, inline annotations referencing fastapi/mangum/uvicorn/starlette/TestClient/Lambda Web Adapter across: Python files, Dockerfiles, requirements.txt, pyproject.toml, Makefile, CLAUDE.md, SPEC.md, Terraform .tf files, Mermaid .mmd diagrams, non-exempt docs/ files. Exempt: specs/001-fastapi-purge/, docs/fastapi-purge/
- [ ] T067 [US4] Verify Docker image sizes measurably smaller — rebuild dashboard and SSE images, compare sizes against pre-migration baseline (SC-007 target: ≥5MB each)
- [ ] T068 [US4] Run SC-008 verification: `grep -rn "fastapi\|mangum\|starlette\|uvicorn\|TestClient\|Mangum\|aws-lambda-adapter\|Lambda Web Adapter" . --include="*.py" --include="*.txt" --include="*.toml" --include="*.yml" --include="*.yaml" --include="*.tf" --include="*.md" --include="*.mmd" --exclude-dir=specs/001-fastapi-purge --exclude-dir=docs/fastapi-purge` returns zero matches

> **Checkpoint**: SC-008 scan passes. `pip install -r requirements.txt` installs none of removed packages. Docker images are smaller.

## Phase 10: US8 — API Documentation Generated as Build Artifact (P8)

> **Goal**: OpenAPI spec generated in CI from Pydantic validation models. No runtime /docs endpoint.
>
> **Independent Test**: `python scripts/generate_openapi.py` produces valid OpenAPI 3.1 JSON with all 102 endpoint schemas.

### Implementation

- [ ] T069 [US8] Create scripts/generate_openapi.py — read route registry + all 16 Pydantic request models + 3 response models, assemble OpenAPI 3.1 spec using `model_json_schema()`, write to stdout or file (FR-029, R4)
- [ ] T070 [US8] Add `generate-openapi` Makefile target and integrate into CI/CD pipeline as build artifact (FR-029, FR-030)
- [ ] T071 [US8] Validate generated OpenAPI spec — check all 102 endpoints present, request/response schemas match Pydantic models, no /docs or /redoc endpoints appear (FR-030, SC-014)

> **Checkpoint**: `make generate-openapi` produces valid openapi.json. OpenAPI viewer shows all endpoints.

## Phase 11: Polish & Cross-Cutting Concerns

> Purpose: Final verification, performance benchmarking, documentation updates.

- [ ] T072 [P] Verify CORS is handled exclusively by Lambda Function URL config — confirm no application-level CORS middleware remains (FR-006)
- [ ] T073 [P] Benchmark dashboard cold start and peak memory — verify ≥10ms cold start reduction (SC-002) and ≥10MB memory reduction (SC-003)
- [ ] T074 [P] Benchmark SSE event latency — verify within 50ms of pre-migration baseline (SC-004)
- [ ] T075 [P] Benchmark JSON serialization — verify orjson faster per invocation than FastAPI baseline (SC-013)
- [ ] T076 Run full test suite: `pytest tests/ -v` — verify SC-005 (zero removed package imports), SC-015 (test count ≥ pre-migration)
- [ ] T077 Verify X-Ray distributed tracing — confirm subsegments for boto3/httpx appear in CloudWatch after deployment (SC-016)
- [ ] T078 Update CONTEXT-CARRYOVER document with final migration status, post-migration metrics, and any remaining follow-up items

> **Checkpoint**: All 21 success criteria (SC-001 through SC-021) verified. Full test suite green. Zero trace of removed packages.

---

## Dependencies & Execution Order

### Phase Dependencies

```text
Phase 1 (Setup) ─────────────────┐
                                  ▼
Phase 2 (Foundational) ──────────┤
                                  ▼
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
Phase 3 (US1: Dashboard)   Phase 7 (US2: SSE)   [PARALLEL]
              │                   │
              ▼                   │
Phase 4 (US3: Validation)        │
              │                   │
              ▼                   │
Phase 5 (US6: Middleware)        │
              │                   │
              ▼                   │
Phase 6 (US7: 405 Routing)      │
              │                   │
              ├───────────────────┘
              ▼
Phase 8 (US5: Test Migration)
              │
              ▼
Phase 9 (US4: Dependency Elimination)
              │
              ▼
Phase 10 (US8: OpenAPI)
              │
              ▼
Phase 11 (Polish)
```

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|-----------|-------------------|
| US1 (Dashboard) | Phase 2 | US2 (different Lambda) |
| US2 (SSE) | Phase 2 | US1, US3, US6, US7 (different Lambda) |
| US3 (Validation) | US1 (routes must exist) | US2 |
| US6 (Middleware) | US1 (routes must exist) | US2 |
| US7 (405 Routing) | US1 (resolver must exist) | US2 |
| US5 (Tests) | US1, US2, US3, US6 (handlers must be migrated) | — |
| US4 (Elimination) | US5 (tests must pass first) | — |
| US8 (OpenAPI) | US1 (routes must exist) | US4 |

### Parallel Opportunities

**Phase 1**: T001-T009 all touch different files → all parallelizable
**Phase 2**: T010-T013 touch different modules → parallelizable. T014-T017 touch different files → parallelizable
**Phase 3**: T022, T023 parallelizable (different source files). T024, T025 parallelizable
**Phase 7 + Phases 3-6**: US2 (SSE Lambda) fully parallel with US1/US3/US6/US7 (Dashboard Lambda)
**Phase 8**: T046-T057 all touch different test files → highly parallelizable (12 parallel streams)
**Phase 11**: T072-T075 all independent benchmarks → parallelizable

### Parallel Execution Example

```text
# Maximum parallelism for Phase 8 (Test Migration):
Stream A: T046 (OHLC integration) → T047 (sentiment integration)
Stream B: T048 (Lambda auth) → T049 (module-level TestClient)
Stream C: T050 (SSE tests) → T054 (SSE streaming unit)
Stream D: T051 (cache/cookie tests) → T052 (serve_index/magic_link)
Stream E: T053 (middleware tests) → T055 (dashboard handler test)
Stream F: T056 (integration dashboard) → T057 (e2e lambda)
Then: T058 (16 contract files, 462 tests — bulk migration)
Then: T059 (header case verification), T060 (E2E unchanged)
```

---

## Implementation Strategy

### MVP First (Recommended)
Phase 1 → Phase 2 → Phase 3 (US1) only. Dashboard Lambda operational with Powertools. Validates core architecture before migrating SSE or tests.

### Incremental Delivery
All phases, story-by-story. Each phase is independently deployable (except US4 which requires all prior phases).

### Parallel Team Strategy
- **Developer A**: Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 (Dashboard track)
- **Developer B**: Phase 1 → Phase 2 → Phase 7 (SSE track, starts after Phase 2)
- **Merge**: Phase 8 (test migration) → Phase 9 (elimination) → Phase 10 → Phase 11

---

## Notes

- `[P]` = Task touches files independent of other tasks in same phase; safe to parallelize
- `[USN]` = Task belongs to user story N for traceability
- Every phase has a **Checkpoint** — stop point to verify before proceeding
- Tests are integrated into each phase (not a separate TDD phase) because the spec mandates test migration as part of the work
- Commit after each phase checkpoint (not per-task) to maintain clean git history
- The spec explicitly states **NO FALLBACKS** — all error paths fail fast with structured errors
- FR-047 (DynamoDB cache non-blocking) and US2-AS5 (SSE event skip) are the only explicitly designed resilience patterns; everything else fails immediately
