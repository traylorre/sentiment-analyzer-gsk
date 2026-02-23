# Feature Specification: FastAPI & Mangum Permanent Removal

**Feature Branch**: `001-fastapi-purge`
**Created**: 2026-02-09
**Status**: Draft (Round 8)
**Input**: User description: "Remove FastAPI and Mangum permanently from all Lambda functions. Replace with native AWS Lambda Proxy Integration handlers using event/context pattern. No fallbacks - fail fast on errors. Remove all traces of fastapi, mangum, uvicorn, starlette from code, tests, requirements, and Terraform."

## Revision History

| Round | Date | Changes |
|-------|------|---------|
| 1 | 2026-02-09 | Initial spec from codebase audit (2 Lambdas, 20+ test files, 17+ routes) |
| 2 | 2026-02-09 | Incorporated architectural guidance: Powertools for dashboard, raw streaming for SSE, OHLCRequestContext validation pattern, dual-routing elimination, explicit tradeoff documentation |
| 3 | 2026-02-09 | Incorporated JSON processing strategies: validation-at-the-gate via Pydantic model_validate(), high-performance JSON serialization, raw stdout streaming for SSE, CI-generated OpenAPI docs, structural 422 error parity with FastAPI format |
| 4 | 2026-02-09 | Self-audit cross-reference against codebase: corrected route count (54+ across 9 routers), test count (25 files, 363 functions), added 8 new FRs (auth middleware, implicit endpoints, debug endpoint, static files, X-Ray, ConnectionManager, Pydantic request models, dependency_overrides test migration), added 4 new edge cases, added 4 new assumptions, tightened scope metrics throughout |
| 5 | 2026-02-09 | Final principal-engineer quality gate: corrected router count (9→11, including ohlc + sse routers), endpoint count (54+→102 total: 97 dashboard + 5 SSE), test function count (363→~395), tightened request model count (15+→16 confirmed), added 6 new FRs (exception_handler migration, response_model= migration, dashboard SSE EventSourceResponse, Response parameter type replacement, precise Depends() inventory, lifespan removal), added 2 new SCs, added 3 new edge cases, added 5 new assumptions, final contradiction scan clean |
| 6 | 2026-02-09 | Final sign-off audit (10-point): fixed FR-005 overbroad scope (scoped to dashboard Lambda, body described as "string" not "JSON string"), fixed FR-023 escape clause cross-references, updated FR-004 to include Body(), added 6 new FRs closing edge case gaps (FR-043 to FR-048: null params, URL decoding, event format validation, 6MB detection, cache write non-blocking, SSE disconnect cleanup), added 3 new FRs for uncovered FastAPI features (FR-049 set_cookie, FR-050 Request.cookies, FR-051 APIRouter prefix), added 3 new SCs (SC-019 405 behavior, SC-020 auth preservation, SC-021 cookie handling), added 4 new assumptions. Final totals: 51 FRs, 21 SCs, 17 edge cases, 28 assumptions, 5 tradeoffs. All 33 acceptance scenarios covered, all 11 numbers consistent, 0 contradictions |
| 7 | 2026-02-09 | Traceless removal audit: cross-referenced spec against actual codebase remnant scan (49 match categories). Found 5 blind spots. FR-052 NEW: AWS Lambda Web Adapter removal (binary, env vars, /health endpoint, base image change, EXPOSE port, fallback imports). FR-053 NEW: comment/docstring/inline-reference cleanup across all file types to satisfy SC-008. FR-054 NEW: SSE streaming Lambda /health endpoint removal. Updated SC-008 to add "aws-lambda-adapter" and "Lambda Web Adapter" to search terms. Added 3 new edge cases. Added 4 new assumptions. Added tradeoff: Lambda Web Adapter removal. Final totals: 54 FRs, 21 SCs, 20 edge cases, 32 assumptions, 6 tradeoffs |
| 8 | 2026-02-09 | Decision resolution + blind spot closure: Resolved /health (REMOVE per FR-054, AWS-native monitoring replaces it), resolved /debug (REMOVE, X-Ray + CloudWatch replace it). Fixed US2-AS5 contradiction with FR-054. Updated FR-033 to remove-only. FR-055 NEW: CI/CD deploy.yml smoke test import updates. FR-056 NEW: Terraform env var cleanup for adapter variables. FR-057 NEW: PYTHONPATH/module import verification after base image switch. Updated FR-002 (RESPONSE_STREAM handler signature), FR-052 (Terraform scope), FR-053 (expanded file scope: SPEC.md, CLAUDE.md, architecture docs, diagrams, pyproject.toml B008 entries). Added 2 new edge cases. Added 3 new assumptions. Final totals: 57 FRs, 21 SCs, 22 edge cases, 35 assumptions, 6 tradeoffs, 0 deferred decisions |
| 9 | 2026-02-09 | Testing-focused audit (Round 9): Deep codebase scan of 230+ test files across 6 test categories (unit, integration, e2e, contract, property, load). CORRECTED test file counts: 22 files import TestClient (not implied 25), only 6 files use dependency_overrides (not 16), 16 files import from fastapi. CORRECTED FR-038 scope: 6 files use dependency_overrides (not 16). Discovered 16 contract test files (462 tests) not previously addressed. FR-058 NEW: Shared mock Lambda event factory fixtures. FR-059 NEW: Contract test suite migration (16 files, 462 tests). FR-060 NEW: Module-level TestClient construction migration. FR-061 NEW: Case-insensitive header lookup in native handler. FR-062 NEW: `from fastapi import Response` test import replacement. Updated FR-020 (expanded to include starlette.testclient explicitly). Updated FR-038 (corrected from 16 to 6 files). Updated SC-015 (corrected test file and function counts). Updated US5 (corrected dependency_overrides count). Added 5 new edge cases. Added 5 new assumptions. Final totals: 62 FRs, 21 SCs, 27 edge cases, 40 assumptions, 6 tradeoffs, 0 deferred decisions |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dashboard API Continues Working After Framework Removal (Priority: P1)

An end user visits the dashboard application and interacts with all existing functionality: viewing sentiment data, OHLC charts, news articles, trends, ticker management, alerts, and admin features. Every API endpoint that previously worked through FastAPI now works identically through native Lambda handlers. The user experiences no behavioral change. Response payloads, status codes, headers, and error messages are byte-for-byte identical to the previous implementation.

**Why this priority**: The dashboard Lambda is the primary user-facing surface with 102 endpoints across 11 routers (17 direct handler routes + 59 router_v2.py endpoints + 21 ohlc endpoints + 5 SSE endpoints), and all business-critical functionality. If this breaks, all users are affected. This is the largest and most complex migration target.

**Independent Test**: Can be fully tested by invoking every dashboard API endpoint with known inputs and comparing response payloads, status codes, and headers against a recorded baseline from the current FastAPI implementation. Playwright E2E tests provide the external verification layer.

**Acceptance Scenarios**:

1. **Given** a deployed dashboard Lambda with the native handler, **When** a user requests `GET /api/v2/sentiment`, **Then** the response payload, status code (200), and Content-Type header are identical to the FastAPI-served response
2. **Given** a deployed dashboard Lambda with the native handler, **When** a user requests `GET /api/v2/tickers/{ticker}/ohlc?range=1M&resolution=D`, **Then** OHLC candle data is returned with the same schema and cache headers as before
3. **Given** a deployed dashboard Lambda with the native handler, **When** a user requests a non-existent route, **Then** a 404 error response is returned with a structured JSON error body
4. **Given** a deployed dashboard Lambda with the native handler, **When** a user sends an OPTIONS preflight request, **Then** CORS headers are returned matching the Lambda Function URL configuration (not application-level CORS)
5. **Given** a deployed dashboard Lambda with the native handler, **When** any endpoint raises an unhandled exception, **Then** the system returns a 500 error with structured JSON body and logs the full traceback (no silent swallowing)
6. **Given** a deployed dashboard Lambda with the native handler, **When** a user submits an invalid query parameter (e.g., `resolution=INVALID`), **Then** the system returns a 422 Unprocessable Entity with a structured validation error body describing exactly which parameter failed and why

---

### User Story 2 - SSE Streaming Continues Working After Framework Removal (Priority: P2)

An end user opens a real-time streaming connection to receive live sentiment updates. The SSE streaming Lambda, which currently uses FastAPI + Uvicorn + AWS Lambda Web Adapter with RESPONSE_STREAM mode, continues to deliver Server-Sent Events without interruption. Connection lifecycle (connect, receive events, reconnect with Last-Event-ID) works identically. The streaming Lambda writes directly to the response stream (bypassing standard JSON return patterns) because no lightweight framework supports Lambda RESPONSE_STREAM invoke mode.

**Why this priority**: SSE streaming is the second Lambda using FastAPI. It has a fundamentally different architecture from the dashboard (Uvicorn + Lambda Web Adapter vs Mangum), and streaming responses require direct stream writes that bypass the standard request/response cycle entirely.

**Independent Test**: Can be fully tested by opening an SSE connection to `/api/v2/stream`, verifying events arrive as `text/event-stream`, disconnecting, and reconnecting with `Last-Event-ID` header to verify resumption.

**Acceptance Scenarios**:

1. **Given** a deployed SSE Lambda with the native handler, **When** a client connects to `/api/v2/stream`, **Then** the response is `Content-Type: text/event-stream` and events arrive as a continuous stream with each event formatted as `data: {json}\n\n`
2. **Given** an active SSE connection, **When** new sentiment data is published, **Then** the client receives the event within the same latency window as the previous implementation
3. **Given** a disconnected SSE client with a Last-Event-ID, **When** the client reconnects with that header, **Then** missed events are replayed from the last known position
4. **Given** a deployed SSE Lambda with the native handler, **When** a client requests `/api/v2/configurations/{config_id}/stream`, **Then** configuration-specific filtered events are delivered
5. **Given** a deployed SSE Lambda writing to the response stream, **When** a serialization error occurs for a single event, **Then** that event is skipped with an ERROR log and the stream continues (stream integrity is preserved; individual event failures do not terminate the connection)

---

### User Story 3 - Input Validation Produces Structurally Identical 422 Errors (Priority: P3)

A user or API consumer submits a request with invalid parameters. The system validates all inputs at the handler entry point ("validation at the gate") and returns a 422 error response with **exactly the same JSON structure** that FastAPI previously produced: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. The frontend code that parses these error responses continues to work without modification.

**Why this priority**: Removing FastAPI silently removes automatic input validation. The frontend JavaScript code parses the specific `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` structure. If the 422 body format changes, the frontend error display breaks silently - users see raw JSON instead of friendly error messages.

**Independent Test**: Can be fully tested by sending requests with each known invalid parameter value and comparing the 422 response body byte-for-byte against a recorded baseline from the current FastAPI implementation.

**Acceptance Scenarios**:

1. **Given** a request with `resolution=INVALID`, **When** the dashboard Lambda processes it, **Then** a 422 response is returned with body containing `{"detail": [{"loc": ["query", "resolution"], "msg": "...", "type": "..."}]}`
2. **Given** a request with a missing required path parameter (empty ticker), **When** the dashboard Lambda processes it, **Then** a 400 response is returned describing the missing field
3. **Given** a request with `range=99Y` (unknown range), **When** the dashboard Lambda processes it, **Then** a 422 response is returned with `detail` array listing the valid range options
4. **Given** a valid request with all parameters correct, **When** the dashboard Lambda processes it, **Then** no validation error is raised and the request proceeds to business logic
5. **Given** the 422 response body, **When** the frontend JavaScript parses `response.detail[0].loc`, `response.detail[0].msg`, and `response.detail[0].type`, **Then** all three fields are present and contain meaningful values identical to the FastAPI format

---

### User Story 4 - Complete Dependency Elimination Verified (Priority: P4)

A developer or CI pipeline verifies that no trace of FastAPI, Mangum, Uvicorn, or Starlette remains anywhere in the codebase. This includes source code imports, test imports, requirements files, Dockerfiles, Terraform configurations, pyproject.toml linting exceptions, and local development scripts. A grep across the entire repository for these package names returns zero results.

**Why this priority**: Incomplete removal leaves dead code, unnecessary dependencies in container images, and confusing artifacts for future developers. This is the "clean room" verification that the purge is truly complete.

**Independent Test**: Can be fully tested by running `grep -rn "fastapi\|mangum\|starlette\|uvicorn\|Mangum\|FastAPI\|TestClient" src/ tests/ scripts/ infrastructure/ pyproject.toml` and asserting zero matches. Container image sizes can be compared before/after.

**Acceptance Scenarios**:

1. **Given** the completed codebase, **When** a recursive search for "fastapi", "mangum", "starlette", "uvicorn" is run across all source, test, config, and infrastructure files, **Then** zero matches are returned
2. **Given** the completed codebase, **When** `pip install -r requirements.txt` is run in each Lambda's directory, **Then** none of the removed packages are installed
3. **Given** the completed codebase, **When** the pyproject.toml ruff configuration is inspected, **Then** no linting exceptions for `Depends()` or `Query()` in function defaults (B008) remain
4. **Given** the completed codebase, **When** Docker images are rebuilt, **Then** image sizes are measurably smaller than before

---

### User Story 5 - All Tests Pass With Native Handler Invocation (Priority: P5)

A developer runs the full test suite and every test passes. Tests that previously used `fastapi.testclient.TestClient` or `starlette.testclient.TestClient` now invoke handlers directly with mock API Gateway event dictionaries and mock Lambda context objects. Test coverage is equal to or greater than before the migration.

**Why this priority**: The test suite is the safety net. 22 test files currently import TestClient, 16 import from fastapi directly, and 6 files use FastAPI's `app.dependency_overrides` pattern for mock injection (requiring `unittest.mock.patch` replacement). Additionally, 16 contract test files (462 test functions) assert on response schemas using TestClient response objects. Migrating tests validates that the handler behaves correctly and catches regressions that manual testing might miss.

**Independent Test**: Can be fully tested by running `pytest tests/ -v` and comparing pass/fail counts against a baseline recorded before migration.

**Acceptance Scenarios**:

1. **Given** the migrated test suite, **When** `pytest tests/unit/` is run, **Then** all unit tests pass with zero imports from fastapi or starlette
2. **Given** the migrated test suite, **When** `pytest tests/integration/` is run, **Then** all integration tests pass using mock event dictionaries instead of TestClient
3. **Given** the migrated test suite, **When** Playwright E2E tests are run against a deployed environment, **Then** all E2E tests pass without modification (they hit API Gateway, not the handler directly)

---

### User Story 6 - Shared Middleware Replaced With Explicit Per-Handler Logic (Priority: P6)

The shared middleware modules (`csrf_middleware.py`, `require_role.py`) that currently depend on FastAPI's `Request`, `HTTPException`, and `Depends` are replaced with equivalent logic that operates on the raw Lambda event dictionary. CSRF validation and role-based access control continue to function identically but without any framework dependency.

**Why this priority**: Shared middleware is a cross-cutting concern that affects multiple routes. Incorrect replacement could silently disable security controls. This must be handled with precision.

**Independent Test**: Can be fully tested by invoking protected endpoints with and without valid CSRF tokens and role claims, verifying that unauthorized requests are rejected with appropriate error codes.

**Acceptance Scenarios**:

1. **Given** a protected endpoint requiring CSRF, **When** a request arrives without a valid CSRF token, **Then** the system rejects the request with a 403 status code and a structured error body
2. **Given** a protected endpoint requiring admin role, **When** a request arrives from a non-admin user, **Then** the system rejects the request with a 403 status code
3. **Given** the shared middleware modules, **When** their source code is inspected, **Then** no imports from fastapi or starlette remain

---

### User Story 7 - Routing Defined in Exactly One Place (Priority: P7)

After the migration, every API route is defined in exactly one authoritative location. There is no dual-routing problem where route paths must be maintained in both an infrastructure configuration and an application-level router that can drift out of sync. If a route is added, changed, or removed, it requires a change in exactly one place.

**Why this priority**: The dual-routing problem (API Gateway routes vs FastAPI routes maintained separately) was identified as a source of hard-to-debug 404 errors when the two definitions drift. Eliminating this class of bug entirely is a key architectural goal of the purge.

**Independent Test**: Can be fully tested by comparing the set of routes known to the application handler against the set of routes configured in infrastructure, and verifying they are derived from the same source.

**Acceptance Scenarios**:

1. **Given** the migrated codebase, **When** a new API route is needed, **Then** it can be added by modifying code in exactly one location (the handler's route registration)
2. **Given** the migrated codebase, **When** a route is removed from the handler, **Then** requests to that path return 404 without requiring a separate infrastructure change
3. **Given** the migrated codebase, **When** all registered routes are listed programmatically, **Then** they match exactly the routes that API Gateway forwards to the Lambda

---

### User Story 8 - API Documentation Generated as Build Artifact (Priority: P8)

A developer or technical stakeholder can access up-to-date API documentation that is generated automatically from the same validation models used in the handler code. The documentation is a build artifact produced during CI/CD, not a runtime endpoint. It reflects the actual request/response schemas enforced by the system.

**Why this priority**: Losing Swagger UI (`/docs`) removes a valuable developer experience. Generating documentation from the same models that enforce validation ensures documentation cannot drift from implementation - a problem that manual documentation inevitably suffers.

**Independent Test**: Can be fully tested by running the documentation generation step in CI and verifying the output contains schemas for all registered endpoints.

**Acceptance Scenarios**:

1. **Given** the CI/CD pipeline, **When** a build runs, **Then** an OpenAPI specification file is generated from the validation models used in the handler code
2. **Given** the generated OpenAPI file, **When** a developer opens it in any OpenAPI viewer, **Then** all endpoints, request parameters, and response schemas are accurately documented
3. **Given** a change to a validation model, **When** the next CI build runs, **Then** the generated documentation reflects the change without manual intervention

---

### Edge Cases

- What happens when `queryStringParameters` is `null` (not `{}`) in the API Gateway event? The system MUST handle this without TypeError by treating null as empty.
- What happens when a path parameter contains URL-encoded characters (e.g., ticker `BRK.B` encoded as `BRK%2EB`)? The system MUST decode correctly.
- What happens when the Lambda runs out of memory mid-response? The system MUST NOT produce a partial response; Lambda runtime terminates and API Gateway returns 502.
- What happens when DynamoDB is unavailable during a cache write? The system MUST fail fast with an error log and return the primary response (cache write failure is non-blocking for the response but MUST be logged as an ERROR, not silently dropped).
- What happens when an SSE client connects but no events are available? The system MUST keep the connection alive with periodic heartbeat comments (`: heartbeat\n\n`).
- What happens when `handler.lambda_handler` is invoked with an event that does not match API Gateway Proxy format (e.g., direct invocation, EventBridge, SNS)? The system MUST reject unrecognized event shapes with a clear error rather than producing undefined behavior.
- What happens when a request contains a valid route path but an unsupported HTTP method (e.g., DELETE on a GET-only endpoint)? The system MUST return 405 Method Not Allowed, not 404.
- What happens when a validation error occurs in the request context object construction? The system MUST return 422 with the full validation error detail in FastAPI-compatible format, not swallow it into a generic 500.
- What happens when a response payload contains datetime objects or dataclass instances? The system MUST serialize them correctly without requiring custom JSON encoder functions (the serialization library must handle these natively).
- What happens when a response payload exceeds 6MB (API Gateway limit for synchronous invocations)? The system MUST detect this before returning and return a 502 error with a log entry, rather than letting API Gateway silently truncate the response.
- What happens when a test that previously used `app.dependency_overrides[get_tiingo_adapter] = mock_factory` is migrated? The system MUST provide an equivalent mock injection pattern (e.g., `unittest.mock.patch` targeting the singleton factory function) so that tests retain the same isolation guarantees.
- What happens when a POST/PATCH endpoint receives a request body matching one of the 16 Pydantic request models? The system MUST validate the entire body at the gate using the same Pydantic model, returning 422 for any field that fails validation, not just query/path parameters.
- What happens when a request hits the former SSE streaming Lambda `/debug` endpoint path after removal? The system MUST return 404 Not Found. Diagnostic data is available through X-Ray traces, CloudWatch Logs Insights, and CloudWatch Synthetics canaries — all of which provide superior observability without an in-process endpoint.
- What happens when X-Ray `patch_all()` is called before other imports at module level? The system MUST preserve this import ordering to ensure distributed tracing continues to instrument boto3 and httpx calls correctly.
- What happens when a `response_model=` endpoint (e.g., ohlc.py's OHLCResponse) returns extra fields not in the model? FastAPI's `response_model` silently filtered them. The native handler MUST replicate this filtering behavior by serializing through the Pydantic model's `model_dump()` to exclude unset/extra fields.
- What happens when the dashboard Lambda's sse.py module streams events to a client that disconnects mid-stream? The native handler MUST detect the disconnection and clean up resources without logging spurious errors (EventSourceResponse previously handled this).
- What happens when `no_cache_headers` or `set_refresh_token_cookie` (which currently receive a FastAPI `Response` object as a parameter via `Depends()`) need to set headers? The native handler MUST allow header manipulation on the proxy response dict before it is returned, replacing the `Response` parameter injection pattern.
- What happens when the AWS Lambda Web Adapter is removed but the SSE streaming Lambda's Dockerfile still references `python:3.13-slim` as the base image (which lacks the Lambda Runtime Interface Client)? The Lambda MUST use the official `public.ecr.aws/lambda/python:3.13` base image which includes the RIC, or the Lambda Runtime Interface Client must be installed explicitly.
- What happens when the SSE streaming Lambda's `try/except ImportError` fallback import pattern (logging_utils) is left in place after the Dockerfile path restructuring? The system MUST use a single deterministic import path — no fallback imports that mask misconfigured PYTHONPATH.
- What happens when SC-008's repository search finds the string "fastapi" inside a Dockerfile comment or requirements-file annotation? SC-008 MUST count these as failures; FR-053 ensures they are cleaned before the migration is complete.
- What happens when CI/CD deployment smoke tests in `.github/workflows/deploy.yml` import `from fastapi import FastAPI` and `from mangum import Mangum` after packages are removed? The deployment pipeline will FAIL, blocking all preprod and prod deployments. FR-055 ensures these smoke tests are updated to verify native handler imports before the packages are removed.
- What happens when the SSE streaming Lambda's module imports use `from app.logging_utils import ...` (WORKDIR /app) but the new base image `public.ecr.aws/lambda/python:3.13` uses WORKDIR `/var/task`? The imports will fail with ModuleNotFoundError. FR-057 ensures deterministic import paths compatible with the new base image.
- What happens when a test file constructs `client = TestClient(app)` at module level (not inside a fixture)? Module-level construction executes at import time, creating a FastAPI app and TestClient as side effects of importing the test module. FR-060 requires converting these to fixture-scoped construction for proper isolation.
- What happens when test code passes headers like `{"Authorization": "Bearer ..."}` with mixed-case keys but the Lambda event dict normalizes headers to lowercase? Header lookups in the handler will fail unless case-insensitive lookup is implemented. FR-061 ensures case-insensitive header extraction.
- What happens when test_cache_headers.py or test_refresh_cookie.py create `Response()` from fastapi to test header manipulation functions? After FR-042 migrates these functions to operate on plain dicts, the test mocks must also change from FastAPI Response objects to plain dicts. FR-062 ensures test imports are updated.
- What happens when contract tests (tests/contract/) assert on `response.json()` which is an httpx.Response method? After migration, handler returns a dict with `body` as a JSON string. Tests must use `json.loads(response["body"])` instead. FR-059 ensures contract test assertions are migrated.
- What happens when the conftest.py `ohlc_test_client` fixture (which uses dependency_overrides) is defined but never used by any test file? Dead fixture code referencing FastAPI will fail SC-008's zero-result search. FR-038 notes this fixture must be migrated or removed.

## Explicit Tradeoff Acknowledgment

This section documents capabilities that are **lost** by removing FastAPI and how each is addressed.

### Lost: Automatic Input Validation (422 Responses)

**What FastAPI provided**: Declaring `resolution: OHLCResolution` in a function signature caused FastAPI to automatically return a 422 Unprocessable Entity with a Pydantic-generated error body when invalid input was received. The error body had a specific structure: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`.

**How it is replaced**: "Validation at the Gate" - Pydantic validation is called explicitly at handler entry by constructing an immutable request context object (e.g., `OHLCRequestContext`) from the event parameters. Construction failure raises a validation error that is caught once at the top level and converted to a 422 response with the identical `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` structure. The validation is no longer implicit/hidden but produces byte-identical error responses.

**Risk if not addressed**: Invalid inputs pass silently to business logic, causing cryptic errors deep in the call chain. Or the 422 body format changes, breaking frontend error parsing.

### Lost: Swagger UI (/docs Endpoint)

**What FastAPI provided**: A free interactive API documentation page at `/docs` with request/response schemas, try-it-out functionality, and auto-generated OpenAPI specs.

**How it is replaced**: API documentation is generated as a CI/CD build artifact from the same Pydantic validation models used in the handler code. This ensures documentation cannot drift from implementation (a problem runtime `/docs` also had - the docs reflected the code, but manual YAML files can drift). The generated OpenAPI file can be viewed in any standard OpenAPI viewer.

**Risk if not addressed**: Developer experience degrades for API exploration. Mitigated by CI-generated documentation that is always current and derived from the same source of truth as runtime validation.

### Lost: Local Development Parity (uvicorn --reload)

**What FastAPI provided**: Running `uvicorn main:app --reload` gave developers a local HTTP server that behaved identically to production, with hot reload on file changes.

**How it is replaced**: Local development uses `sam local start-api` or direct handler invocation with mock event dictionaries. The `run-local-api.py` script is replaced with an equivalent mechanism that does not depend on Uvicorn.

**Risk if not addressed**: Local development friction increases. Mitigated by providing a replacement local invocation script and well-documented mock event fixtures.

### Lost: ASGI Middleware Chain

**What FastAPI provided**: A composable middleware chain where cross-cutting concerns (timing, logging, CORS, error handling) could be layered as decorators.

**How it is replaced**: Cross-cutting concerns are implemented as explicit function calls at handler entry/exit (e.g., timing wrapper, error handler). CORS is handled exclusively at the Lambda Function URL level in Terraform. This is intentionally less composable but more transparent - every cross-cutting concern is visible in the handler code, not hidden in a middleware stack.

**Risk if not addressed**: Cross-cutting concerns are forgotten during migration. Mitigated by auditing every middleware currently registered and documenting its replacement.

### Lost: Automatic JSON Serialization (JSONResponse)

**What FastAPI provided**: `JSONResponse` automatically serialized Python dicts, lists, and Pydantic models to JSON. It handled Content-Type headers and character encoding.

**How it is replaced**: JSON serialization is performed explicitly using a high-performance serialization library that natively handles datetime objects, dataclass instances, and Pydantic models without custom encoder functions. The response body is always a JSON string in the proxy response dict. This is faster than FastAPI's `JSONResponse` (which uses stdlib `json` internally) and removes the need for `default=str` workarounds.

**Risk if not addressed**: Serialization errors on datetime/dataclass fields cause 500 errors. Mitigated by choosing a serializer that handles these types natively.

### Lost: AWS Lambda Web Adapter (SSE Streaming Lambda)

**What the Lambda Web Adapter provided**: The adapter ran as a Lambda extension that bridged between the Lambda Runtime Interface and a local HTTP server (Uvicorn on port 8080). This allowed using standard web frameworks inside Lambda containers with `RESPONSE_STREAM` invoke mode. The adapter handled HTTP readiness checks (`/health`), request proxying, and connection lifecycle management.

**How it is replaced**: The SSE streaming Lambda writes directly to the Lambda response stream using the Lambda Runtime Interface Client's native streaming API. The handler implements the `awslambdaric` streaming response protocol (or equivalent) without an intermediate HTTP server. This eliminates an entire network hop (Lambda RIC → adapter → Uvicorn → FastAPI → handler → response), reducing latency and removing a failure point.

**Risk if not addressed**: The Lambda Web Adapter is a third-party binary (`public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1`) that adds ~10MB to the container image and introduces an opaque intermediary. Its removal simplifies the architecture but requires implementing the RESPONSE_STREAM protocol directly. If the direct streaming implementation has bugs, SSE connections will fail silently or produce malformed events.

## Requirements *(mandatory)*

### Functional Requirements

#### Handler Migration

- **FR-001**: System MUST replace the Mangum-wrapped FastAPI app in the dashboard Lambda with a native `lambda_handler(event, context)` function that processes API Gateway Proxy Integration events directly
- **FR-002**: System MUST replace the Uvicorn + AWS Lambda Web Adapter + FastAPI app in the SSE streaming Lambda with a native streaming handler that writes directly to the response stream, compatible with `RESPONSE_STREAM` invoke mode, without using any ASGI framework. The native streaming handler MUST use the RESPONSE_STREAM handler signature `lambda_handler(event, response_stream, context)` where `response_stream` is the writable stream object provided by the Lambda runtime
- **FR-003**: System MUST preserve identical response schemas, status codes, and header values for all existing endpoints across both Lambdas

#### Request/Response Contract

- **FR-004**: System MUST extract request parameters from `event["queryStringParameters"]`, `event["pathParameters"]`, and `event["headers"]` instead of using FastAPI's `Query()`, `Path()`, `Header()`, `Body()`, and `Depends()` abstractions
- **FR-043**: System MUST treat null `queryStringParameters`, `pathParameters`, and `multiValueQueryStringParameters` as empty dictionaries, preventing TypeErrors during parameter extraction
- **FR-044**: System MUST URL-decode path parameters extracted from `event["pathParameters"]` to handle encoded characters (e.g., `BRK%2EB` → `BRK.B`)
- **FR-005**: System MUST format all dashboard Lambda responses (BUFFERED invoke mode) as API Gateway Proxy Integration response dictionaries with `statusCode` (int), `headers` (dict), and `body` (string — JSON for API endpoints, HTML/text for static assets, base64 for binary). SSE streaming Lambda responses in RESPONSE_STREAM mode write directly to the response stream (see FR-002, FR-025) and are exempt from this format
- **FR-006**: System MUST NOT include application-level CORS middleware; CORS is handled exclusively by Lambda Function URL configuration in Terraform

#### Validation ("Validation at the Gate")

- **FR-007**: System MUST validate all incoming request parameters at handler entry by constructing an immutable request context object from the event parameters; construction failure MUST trigger a 422 response
- **FR-008**: System MUST use immutable request context objects (following the OHLCRequestContext pattern from R25) to group validated request parameters into a single object passed through the handler pipeline, replacing the FastAPI `Depends()` parameter sprawl
- **FR-009**: System MUST return 422 Unprocessable Entity for validation errors with a response body structurally identical to FastAPI's format: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` where `loc` is the parameter location array, `msg` is the human-readable message, and `type` is the error type identifier
- **FR-010**: System MUST NOT use try/except to catch validation errors in business logic; validation MUST occur exactly once at the handler entry point ("the gate"), and the single top-level error handler converts validation failures to 422 responses

#### JSON Serialization

- **FR-011**: System MUST serialize all JSON response bodies using a high-performance serialization library that natively handles datetime objects, dataclass instances, and Pydantic models without requiring custom encoder functions or `default=str` workarounds
- **FR-012**: System MUST deserialize incoming JSON request bodies (where applicable) using the same high-performance library for consistency

#### Dependency Management

- **FR-013**: System MUST replace all 68 FastAPI `Depends()` invocations across source files with static initialization singletons that are created once during the Lambda cold start init phase and reused across invocations. The 6 unique dependency functions to migrate are: `get_users_table` (~40 usages, dominant), `get_tiingo_adapter`, `get_finnhub_adapter`, `get_ticker_cache_dependency`, `no_cache_headers`, and `require_csrf`
- **FR-014**: System MUST remove `fastapi`, `mangum`, `uvicorn`, `starlette`, and `sse-starlette` from all requirements files, Dockerfiles, and pyproject.toml configurations
- **FR-015**: System MUST update Dockerfiles to invoke the native handler directly instead of through Uvicorn or Mangum

#### Routing

- **FR-016**: System MUST define routes in exactly one authoritative location per Lambda, eliminating the dual-routing problem where API Gateway and FastAPI maintained separate route tables that could drift
- **FR-017**: System MUST return 405 Method Not Allowed (not 404) when a valid route is requested with an unsupported HTTP method
- **FR-051**: System MUST preserve the URL prefix structure currently defined by 9 APIRouter `prefix=` configurations (e.g., `/api/v2/auth`, `/api/v2/configurations`, `/api/v2/tickers`, etc.) in the native routing mechanism, ensuring all existing endpoint paths remain unchanged

#### Security & Middleware

- **FR-018**: System MUST replace shared middleware modules (`csrf_middleware.py`, `require_role.py`) with equivalent logic that operates on raw event dictionaries without FastAPI dependencies
- **FR-019**: System MUST preserve all existing authentication and authorization behavior, extracting auth context from `event["requestContext"]["authorizer"]` and `event["headers"]` instead of FastAPI Depends chains
- **FR-031**: System MUST replace `auth_middleware.py` (`extract_auth_context`, `extract_auth_context_typed`) with equivalent functions that extract Bearer tokens and user identity from raw event dictionaries, independent of FastAPI's `Request` object
- **FR-049**: System MUST replace `Response.set_cookie()` calls (CSRF token cookie with `httponly=False, secure=True, samesite="none"`, and refresh token cookie with `httponly=True, secure=True, samesite="strict"`) with equivalent `Set-Cookie` header values in the proxy response dictionary, preserving all security attributes (httponly, secure, samesite, max_age, path)
- **FR-050**: System MUST replace `Request.cookies` dictionary access (used in CSRF validation and refresh token extraction) with cookie parsing from the raw `event["headers"]["Cookie"]` or `event["headers"]["cookie"]` header string

#### Implicit Endpoint Removal

- **FR-032**: System MUST NOT serve implicit FastAPI-generated endpoints (`/docs`, `/redoc`, `/openapi.json`) at runtime; these endpoints are removed with FastAPI itself and are replaced by CI-generated documentation (see FR-029)
- **FR-033**: System MUST remove the SSE streaming Lambda's `/debug` diagnostic endpoint entirely. Equivalent diagnostics are provided by X-Ray distributed tracing (FR-034), CloudWatch Logs Insights with EMF metrics, and CloudWatch Synthetics canaries — all of which are more reliable than an in-process debug endpoint that cannot observe Lambda freeze behavior or network-layer issues
- **FR-054**: System MUST remove the SSE streaming Lambda's `/health` endpoint, which exists solely as the Lambda Web Adapter readiness check (`AWS_LWA_READINESS_CHECK_PATH=/health`); this endpoint has no purpose once the adapter is removed. AWS-native health monitoring (CloudWatch Invocations/Errors/Duration metrics, CloudWatch Synthetics canaries hitting real data endpoints, and OHLCErrorResponse `status: "degraded"` field) replaces /health with more reliable observability that tests the entire path rather than a dummy 200 response

#### CI/CD Pipeline Updates

- **FR-055**: System MUST update CI/CD deployment workflow import smoke tests in `.github/workflows/deploy.yml` (preprod at approximately line 675 and prod at approximately line 1556) to verify native handler imports instead of FastAPI/Mangum imports. These inline Python scripts currently `from fastapi import FastAPI` and `from mangum import Mangum` and will break deployments once packages are removed
- **FR-056**: System MUST remove `AWS_LWA_INVOKE_MODE` and `AWS_LWA_READINESS_CHECK_PATH` environment variables from the Terraform SSE streaming Lambda module `environment_variables` block in `infrastructure/terraform/main.tf`, in addition to the Dockerfile removal covered by FR-052(b)(c). The RESPONSE_STREAM invoke mode is configured at the Lambda function level in Terraform, not through the adapter's environment variable

#### Module Import Path Verification

- **FR-057**: System MUST ensure the SSE streaming Lambda's module import paths work correctly with the `public.ecr.aws/lambda/python:3.13` base image's default WORKDIR (`/var/task`), removing all `try/except ImportError` fallback import patterns and using a single deterministic import path. The current `python:3.13-slim` base image uses WORKDIR `/app` which requires different import path configuration

#### Lambda Web Adapter Removal

- **FR-052**: System MUST completely remove the AWS Lambda Web Adapter from the SSE streaming Lambda's Dockerfile and Terraform configuration: (a) remove the `COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1 /lambda-adapter /opt/extensions/` layer, (b) remove the `AWS_LWA_INVOKE_MODE` environment variable from Dockerfile, (c) remove the `AWS_LWA_READINESS_CHECK_PATH` environment variable from Dockerfile, (d) remove `EXPOSE 8080` (the port existed for Uvicorn behind the adapter), (e) change the base image from `python:3.13-slim` to `public.ecr.aws/lambda/python:3.13` (Lambda Runtime Interface Client), (f) update the `CMD` to use the Lambda handler entry point format instead of Uvicorn, and (g) remove `AWS_LWA_INVOKE_MODE` and `AWS_LWA_READINESS_CHECK_PATH` environment variables from the Terraform SSE streaming Lambda module `environment_variables` block in infrastructure configuration

#### Trace Cleanup

- **FR-053**: System MUST remove all comments, docstrings, inline annotations, and requirement-file annotations that reference `fastapi`, `mangum`, `uvicorn`, `starlette`, `Mangum`, `FastAPI`, `TestClient`, or `Lambda Web Adapter` across all file types (Python, Dockerfile, requirements.txt, pyproject.toml, Makefile, markdown, Terraform .tf files, Mermaid .mmd diagram files, CLAUDE.md, SPEC.md). This includes: Dockerfile header comments (e.g., "FastAPI + Mangum for serving"), module docstrings (e.g., "FastAPI application for Server-Sent Events"), dependency comments (e.g., "# For FastAPI TestClient"), Terraform comments referencing Mangum/FastAPI/Lambda Web Adapter (infrastructure/terraform/main.tf, modules/api_gateway/main.tf), architecture diagram labels (docs/diagrams/*.mmd), SPEC.md technology descriptions, CLAUDE.md Active Technologies entries and code examples referencing TestClient/starlette, pyproject.toml B008 lint suppression entries that existed solely for FastAPI Depends()/Query() patterns, and non-exempt documentation files (docs/reference/, docs/security/, docs/testing/, docs/diagrams/). SC-008 enforces this requirement

#### Observability Preservation

- **FR-034**: System MUST preserve X-Ray `patch_all()` call at module level before other imports in all Lambda handlers, ensuring distributed tracing continues to instrument boto3, httpx, and other SDK calls
- **FR-035**: System MUST preserve the SSE streaming Lambda's `ConnectionManager` thread-safety (using `threading.Lock()`) for managing concurrent SSE connections

#### Static Assets

- **FR-036**: System MUST preserve static file serving capabilities including the whitelist pattern (8 allowed static files) using direct file reads and appropriate Content-Type headers, replacing FastAPI's `FileResponse` and `StaticFiles`

#### Request Body Validation

- **FR-037**: System MUST validate all incoming POST/PATCH request bodies (16 Pydantic request models across router_v2.py, ohlc.py, auth.py, alerts.py, alert_rule.py, configuration.py, and handler.py) at the handler entry point using the same Pydantic models, converting `event["body"]` JSON to the appropriate model via `model_validate()` and returning 422 on failure

#### Cleanup

- **FR-020**: System MUST replace all `fastapi.testclient.TestClient` and `starlette.testclient.TestClient` usage in tests (22 files total: 16 importing from fastapi, 1 from starlette, plus conftest.py fixtures) with direct handler invocation using mock event dictionaries and mock Lambda context objects. This includes both fixture-based TestClient (yielded from pytest fixtures) and module-level TestClient (constructed at import time as global `client = TestClient(app)`)
- **FR-021**: System MUST remove ruff B008 linting exceptions for `Depends()` and `Query()` in function defaults from pyproject.toml
- **FR-022**: System MUST remove the local development script's (`run-local-api.py`) FastAPI/Uvicorn dependency and replace with an equivalent local invocation mechanism
- **FR-038**: System MUST replace the 6 test files that use FastAPI's `app.dependency_overrides` pattern (conftest.py `ohlc_test_client` fixture, 3 OHLC integration tests overriding get_tiingo_adapter/get_finnhub_adapter, and 2 Lambda auth tests overriding get_users_table) with an equivalent mock injection mechanism (e.g., `unittest.mock.patch` targeting singleton factory functions) that provides the same test isolation. Note: the conftest.py `ohlc_test_client` fixture is defined but currently unused by any test file; its dependency_overrides pattern must still be migrated or removed

#### Test Infrastructure Migration

- **FR-058**: System MUST provide shared mock Lambda event factory fixtures in a test conftest.py (or equivalent shared test utility) that construct valid API Gateway Proxy Integration event dictionaries from test parameters (method, path, query params, headers, body), eliminating duplicated event dict construction across 22+ test files. The factory MUST support: GET with query parameters, POST/PATCH with JSON body, path parameter injection, header injection (including Authorization), and cookie header construction
- **FR-059**: System MUST migrate the 16 contract test files (462 test functions in tests/contract/) that assert on API response schemas using TestClient response objects (`response.status_code`, `response.json()`, `response.headers`) to assert on Lambda proxy response dictionaries (`response["statusCode"]`, `json.loads(response["body"])`, `response["headers"]`). Contract tests verify API contracts and must continue to validate identical response structures after migration
- **FR-060**: System MUST migrate test files that construct TestClient at module level (e.g., `app = FastAPI(); app.include_router(router); client = TestClient(app)` at import time in test_ohlc.py, test_sentiment_history.py) to use fixture-scoped handler invocation instead, preventing import-time side effects and ensuring proper test isolation
- **FR-061**: System MUST implement case-insensitive header lookup when extracting headers from `event["headers"]` in the native handler, because API Gateway normalizes HTTP headers to lowercase in the event dict but test code and HTTP clients may use mixed-case header names (e.g., `Authorization` vs `authorization`, `Content-Type` vs `content-type`)
- **FR-062**: System MUST replace test imports of `from fastapi import Response` (used in test_cache_headers.py and test_refresh_cookie.py to construct mock Response objects for testing header/cookie manipulation functions) with equivalent test patterns that operate on plain dictionaries, since the functions under test will no longer accept FastAPI Response objects after FR-042's migration

#### Error Handling

- **FR-023**: System MUST fail fast on all errors: no try/except blocks that silently swallow exceptions, no fallback return values that mask failures, no best-effort degradation unless explicitly designed as a circuit breaker with monitoring. Explicitly designed exceptions: (a) DynamoDB cache write failures are non-blocking per FR-047; (b) individual SSE event serialization failures skip the event per US2-AS5
- **FR-047**: System MUST treat DynamoDB cache write failures as non-blocking: log the error at ERROR level with full traceback and return the primary response to the client. This is an explicitly designed resilience pattern (not a silent fallback) per FR-023's escape clause
- **FR-024**: System MUST log all errors with full tracebacks before returning error responses; no error path may execute without producing a log entry
- **FR-039**: System MUST replace the SSE streaming Lambda's `@app.exception_handler(Exception)` global exception handler with an equivalent top-level try/except in the native handler that returns structured error responses and logs full tracebacks
- **FR-045**: System MUST validate that the incoming event matches API Gateway Proxy Integration format (contains `httpMethod`, `resource`, `requestContext`) before processing, rejecting unrecognized event shapes with a structured error response and ERROR log
- **FR-046**: System MUST detect response payloads exceeding the 6MB API Gateway synchronous invocation limit before returning, and return a 502 error with an ERROR log entry rather than allowing API Gateway to silently truncate the response

#### Behavioral Preservation

- **FR-025**: System MUST preserve the SSE streaming Lambda's `RESPONSE_STREAM` invoke mode and ability to deliver Server-Sent Events as a continuous byte stream, with each event serialized as `data: {json}\n\n`
- **FR-026**: System MUST preserve the dashboard Lambda's `BUFFERED` invoke mode for standard REST API responses
- **FR-027**: System MUST preserve file serving capabilities (`FileResponse` for HTML, favicon, static assets) using direct file reads and appropriate Content-Type headers
- **FR-028**: System MUST replace the FastAPI lifespan function (currently a no-op containing only logging) with equivalent module-level logging during the Lambda init phase; no resource initialization occurs in lifespan so no behavioral change is expected
- **FR-040**: System MUST replace 3 `response_model=` parameter usages (OHLCResponse, SentimentHistoryResponse in ohlc.py; StreamStatus in SSE handler.py) with explicit Pydantic `model_validate()` serialization in the response body, ensuring the same schema filtering behavior that `response_model` provided
- **FR-041**: System MUST replace the dashboard sse.py module's `EventSourceResponse` usage (from sse-starlette) with direct SSE-formatted text/event-stream responses for all 3 SSE endpoints (/stream, /configurations/{config_id}/stream, /stream/status), in addition to the SSE streaming Lambda's EventSourceResponse usage
- **FR-042**: System MUST replace `Response` base class usages as function parameter types (used by `no_cache_headers` and `set_refresh_token_cookie` in router_v2.py for header manipulation) with direct header dict manipulation on the proxy response dictionary
- **FR-048**: System MUST detect SSE client disconnection in both the dashboard Lambda's sse.py module and the SSE streaming Lambda, and clean up resources (release ConnectionManager slots, close generators) without logging spurious errors

#### Documentation

- **FR-029**: System MUST generate an OpenAPI specification file as a CI/CD build artifact, derived from the same validation models used in the handler code, ensuring documentation cannot drift from implementation
- **FR-030**: System MUST NOT serve API documentation at runtime (no `/docs` endpoint); documentation is a static build artifact only

### Key Entities

- **API Gateway Proxy Event**: The incoming request dictionary containing `resource`, `httpMethod`, `queryStringParameters`, `pathParameters`, `headers`, `body`, and `requestContext`. This replaces FastAPI's `Request` object.
- **API Gateway Proxy Response**: The outgoing response dictionary containing `statusCode`, `headers`, and `body` (JSON string). This replaces FastAPI's `Response`, `JSONResponse`, `HTMLResponse`, and `FileResponse` objects.
- **Lambda Context**: The runtime context object providing `function_name`, `memory_limit_in_mb`, `get_remaining_time_in_millis()`. This replaces Mangum's internal context management.
- **Request Context Object**: An immutable, validated, request-scoped data structure (following the OHLCRequestContext pattern) that groups all validated request parameters into a single object passed through the handler pipeline. Constructed once at handler entry ("the gate"), frozen for thread safety. Construction triggers Pydantic validation; failure produces a 422.
- **Validation Error Response**: The structured JSON body returned for 422 errors: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`. This is the canonical format that the frontend parses, and must be structurally identical to what FastAPI produced.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing API endpoints return responses with identical schemas, status codes, and business-critical headers when compared against a pre-migration baseline
- **SC-002**: Dashboard Lambda cold start time is reduced by at least 10ms compared to the FastAPI/Mangum baseline (conservative; audit suggests 10-30ms "Mangum Tax")
- **SC-003**: Dashboard Lambda peak memory usage is reduced by at least 10MB compared to the FastAPI/Mangum baseline (audit suggests 10-30MB "Import Tax")
- **SC-004**: SSE streaming connections deliver events with latency within 50ms of the pre-migration baseline
- **SC-005**: Full test suite (unit + integration) passes with zero failures and zero imports from removed packages
- **SC-006**: Playwright E2E tests pass without any modification, confirming external behavior is unchanged
- **SC-007**: Container image sizes for both Lambdas are reduced by at least 5MB each
- **SC-008**: A recursive search of the entire repository for the strings "fastapi", "mangum", "starlette", "uvicorn", "TestClient", "Mangum", "aws-lambda-adapter", and "Lambda Web Adapter" returns exactly zero results in source, test, config, and infrastructure files (documentation files under `specs/` and `docs/fastapi-purge/` are exempt as they describe the migration itself)
- **SC-009**: Zero new error types appear in CloudWatch logs within 24 hours of deployment compared to the pre-migration error baseline
- **SC-010**: Local development workflow remains functional with a replacement for `run-local-api.py` that does not depend on any removed packages
- **SC-011**: Invalid input requests that previously received 422 responses from FastAPI continue to receive 422 responses with byte-identical `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` structure
- **SC-012**: Each API route is defined in exactly one location; no route requires synchronized changes across multiple files or systems
- **SC-013**: JSON serialization of data-heavy responses (e.g., 30-day OHLC candle arrays with datetime fields) completes in less time per invocation than the pre-migration baseline, reducing billed compute duration
- **SC-014**: An OpenAPI specification file is generated in CI/CD that accurately reflects all registered endpoints, request parameters, and response schemas
- **SC-015**: All test files pass with zero TestClient or `dependency_overrides` patterns remaining: 22 TestClient files migrated, 6 dependency_overrides files migrated, 16 contract test files (462 tests) migrated. Total test count is equal to or greater than the pre-migration baseline
- **SC-016**: X-Ray distributed tracing continues to produce subsegments for boto3 and httpx calls in CloudWatch X-Ray console, verified within 24 hours of deployment
- **SC-017**: All 3 `response_model=` endpoints (OHLCResponse, SentimentHistoryResponse, StreamStatus) return schema-filtered responses identical to the FastAPI baseline, with no extra fields leaking through
- **SC-018**: All 68 `Depends()` usages across 6 unique dependency functions are replaced with static singletons; a grep for `Depends(` across source files returns zero results
- **SC-019**: Requests to valid routes with unsupported HTTP methods return 405 Method Not Allowed, not 404 Not Found
- **SC-020**: All protected endpoints reject unauthorized requests (missing CSRF token, invalid role, expired auth) with the same status codes (403, 401) as the pre-migration baseline
- **SC-021**: Cookie-based operations (CSRF token setting, refresh token setting and reading) continue to produce identical `Set-Cookie` headers with all security attributes (httponly, secure, samesite, max_age, path) preserved

## Assumptions

- CORS is fully handled at the Lambda Function URL level in Terraform and does NOT need application-level middleware. The audit confirms the dashboard Lambda already removed CORSMiddleware with comments explaining this.
- The SSE streaming Lambda's dual CORS (both FastAPI middleware AND Lambda Function URL) is a bug, not intentional. Removing the application-level CORS middleware is correct behavior.
- Both Lambdas are container-based (ECR), so handler path changes happen in Dockerfiles (`CMD` directive), not in Terraform `handler` attributes (which are already `null`).
- The `sse-starlette` package, which provides `EventSourceResponse`, must also be removed. SSE streaming will write `text/event-stream` formatted responses directly to the response stream.
- The `PathNormalizationMiddleware` in the SSE streaming Lambda (fixes Lambda Web Adapter double-slash issue) will no longer be needed if the Lambda Web Adapter itself is removed.
- The 22 test files importing TestClient plus 16 contract test files (462 test functions) using TestClient or FastAPI test patterns will each require individual migration to mock event dictionaries.
- The `httpx` dev dependency may remain if used elsewhere, but its use as a TestClient transport will be eliminated.
- OHLCRequestContext (from R25) is specified but not yet implemented in code. Its pattern (immutable validated object, constructed once at handler entry) is the canonical validation pattern for this migration, and will be implemented as part of this feature. Pydantic v2 (already at v2.12.5 in requirements) provides the `model_validate()` method used for construction.
- The SSE streaming Lambda cannot use a lightweight framework (e.g., AWS Lambda Powertools) because no such framework currently supports Lambda `RESPONSE_STREAM` invoke mode. It must write directly to the response stream.
- The dashboard Lambda's 102 endpoints across 11 routers (9 in router_v2.py + ohlc router + sse router) will use a lightweight routing mechanism (resolver pattern) that operates directly on the Lambda event dict without ASGI translation, preserving the Flask-style `@app.get()` developer experience while eliminating the Mangum/Starlette stack.
- Swagger UI (`/docs`) is acceptable to lose as a runtime endpoint. It is replaced by a CI-generated OpenAPI artifact derived from the same Pydantic models that enforce runtime validation.
- The `run-local-api.py` replacement does not need hot-reload parity with `uvicorn --reload`. Direct handler invocation with mock events is sufficient for local development.
- `orjson` is not currently in any requirements file and must be added as a new dependency. Its installed size (~1MB) is negligible compared to the ~15MB removed (FastAPI + Starlette + Mangum + Uvicorn).
- The 422 error response format (`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`) is consumed by frontend JavaScript code. Changing this structure would silently break the frontend error display. Structural parity is mandatory.
- Pydantic's `ValidationError.errors()` method already produces the `[{"loc": [...], "msg": "...", "type": "..."}]` array natively, which is the same output FastAPI used internally. No custom mapping is needed.
- `auth_middleware.py` provides `extract_auth_context()` and `extract_auth_context_typed()` functions that depend on FastAPI's `Request` object. These must be migrated independently from `csrf_middleware.py` and `require_role.py`, as they are used across multiple router modules.
- 6 test files use FastAPI's `dependency_overrides` for mock injection: conftest.py's `ohlc_test_client` fixture (defined but unused), 3 OHLC integration tests (test_happy_path.py, test_boundary.py, test_error_resilience.py) overriding get_tiingo_adapter/get_finnhub_adapter, and 2 Lambda auth tests (test_admin_sessions_revoke_auth.py, test_users_lookup_auth.py) overriding get_users_table. The remaining test files that use TestClient construct standalone FastAPI apps with routers and use `@patch` decorators for mocking instead of dependency_overrides. The replacement pattern (`unittest.mock.patch` targeting singleton factories) is functionally equivalent but syntactically different, requiring per-file migration.
- X-Ray `patch_all()` must remain at the top of each handler module (before other imports) to ensure correct instrumentation. This is not a FastAPI dependency but must be verified during migration to avoid accidental reordering.
- The SSE streaming Lambda has 2 middlewares registered (PathNormalizationMiddleware, CORSMiddleware) and a `/debug` endpoint. PathNormalizationMiddleware is only needed for Lambda Web Adapter's double-slash issue and can be removed when the adapter is removed. The `/debug` endpoint is removed entirely (decision resolved Round 8); equivalent diagnostics are provided by X-Ray distributed tracing, CloudWatch Logs Insights with EMF metrics, and CloudWatch Synthetics canaries.
- The total router count is 11: 9 routers in router_v2.py (auth, config, ticker, alert, notification, market, users, timeseries, admin) + ohlc.py router + sse.py router. All 11 are included via `include_routers(app)` at line 1945 of router_v2.py. The total endpoint count is 102 (97 dashboard + 5 SSE streaming).
- The FastAPI lifespan function in handler.py (lines 124-139) contains only logging statements. Mangum is configured with `lifespan="off"`, making the lifespan function effectively a no-op in production. It can be replaced with module-level logging without behavioral change.
- The dashboard sse.py module uses `EventSourceResponse` from sse-starlette separately from the SSE streaming Lambda. Both usages must be migrated: sse.py's 3 endpoints (/stream, /configurations/{config_id}/stream, /stream/status) and the SSE streaming Lambda's 2 streaming endpoints.
- The SSE streaming Lambda uses two different streaming approaches: `StreamingResponse` for the global `/api/v2/stream` endpoint (with manual SSE formatting) and `EventSourceResponse` for the `/api/v2/configurations/{config_id}/stream` endpoint. Both must be replaced with direct response stream writes.
- The `Response` base class from FastAPI is used as a parameter type in 2 dependency functions (`no_cache_headers` and `set_refresh_token_cookie` in router_v2.py) for header manipulation. These are injected via `Depends()` and modify response headers before the response is sent. In the native handler, header manipulation happens directly on the proxy response dict.
- `Response.set_cookie()` is used in 2 locations (CSRF token and refresh token) with specific security attributes. In the native handler, `Set-Cookie` header values must be constructed manually with identical attribute strings. Python's `http.cookies.SimpleCookie` or direct string formatting can replace the Starlette cookie serialization.
- `Request.cookies` is used in CSRF validation (`csrf_middleware.py:59`) and refresh token extraction (`router_v2.py:175`). In the native handler, cookies are parsed from the raw `Cookie` header string in the event dict. API Gateway passes cookies in `event["headers"]["Cookie"]` (case may vary).
- `Body()` from FastAPI is used in 2 endpoints (anonymous session creation and refresh token) for explicit request body parameter binding with `default=None`. In the native handler, this is replaced by parsing `event["body"]` with JSON deserialization and optional Pydantic validation.
- The 9 APIRouter instances use `prefix=` to define URL path prefixes and `tags=` for OpenAPI grouping. The prefix behavior (prepending a path segment to all routes in the router) must be preserved in the native routing mechanism. The `tags=` attribute is only relevant for OpenAPI generation (FR-029) and has no runtime effect.
- The SSE streaming Lambda's AWS Lambda Web Adapter (`public.ecr.aws/awsguru/aws-lambda-adapter:0.9.1`) is a third-party extension that proxies HTTP requests from the Lambda Runtime Interface to the local Uvicorn server. When both the adapter and Uvicorn are removed, the Dockerfile must change its base image from `python:3.13-slim` to `public.ecr.aws/lambda/python:3.13` (which includes the Lambda Runtime Interface Client) and use the `CMD ["handler.lambda_handler"]` entry point format.
- The SSE streaming Lambda's `/health` endpoint exists solely for the Lambda Web Adapter's readiness check (`AWS_LWA_READINESS_CHECK_PATH=/health`). It returns a simple 200 OK with no business logic. Once the adapter is removed, this endpoint serves no purpose and is removed (decision resolved Round 8). AWS-native monitoring (CloudWatch Invocations/Errors/Duration metrics, CloudWatch Synthetics canaries on real data endpoints, OHLCErrorResponse `status: "degraded"`) provides superior health observability that tests the entire path.
- The SSE streaming Lambda's `EXPOSE 8080` directive in the Dockerfile exists for the Uvicorn server that the Lambda Web Adapter forwards to. This port exposure is meaningless in a native Lambda handler and must be removed.
- The SSE streaming Lambda's non-root user configuration (`adduser lambda`, `USER lambda`, `chown -R lambda:lambda /app`) was designed for the `python:3.13-slim` base image. If the Dockerfile switches to `public.ecr.aws/lambda/python:3.13`, the Lambda Runtime Interface Client runs as root by default and the non-root configuration must be reviewed for compatibility. The security benefit of non-root execution should be preserved if the base image supports it.
- The RESPONSE_STREAM invoke mode uses a different handler signature than BUFFERED mode: `lambda_handler(event, response_stream, context)` instead of `lambda_handler(event, context)`. The `response_stream` parameter is a writable stream object provided by the Lambda runtime. This means the SSE streaming Lambda and dashboard Lambda have structurally different handler signatures.
- The CI/CD deployment workflow (`.github/workflows/deploy.yml`) contains inline Python import smoke tests that verify Docker images can import core packages. Both preprod (~line 675) and prod (~line 1556) jobs currently test `from fastapi import FastAPI` and `from mangum import Mangum`. These tests will fail as soon as packages are removed from requirements files, blocking deployments. They must be updated before or simultaneously with FR-014 (package removal).
- The Terraform SSE streaming Lambda module sets `AWS_LWA_INVOKE_MODE` and `AWS_LWA_READINESS_CHECK_PATH` as Lambda environment variables independently of the Dockerfile ENV directives. Both the Dockerfile and Terraform sources must be cleaned to avoid the Terraform `terraform apply` re-injecting adapter environment variables after the Dockerfile cleanup.
- The test suite contains 230+ test files across 6 categories (unit, integration, e2e, contract, property, load), significantly more than the 25 files previously counted. The 25-file count referred only to files directly importing TestClient or FastAPI test patterns. The contract test suite (16 files, 462 test functions in tests/contract/) was not previously included in scope but must be migrated because contract tests assert on TestClient response objects.
- API Gateway normalizes HTTP request headers to lowercase in the Lambda event dict. The native handler's header extraction must use case-insensitive lookup (e.g., lowercase all keys before lookup, or use a case-insensitive dict wrapper) to handle both real API Gateway events (lowercase) and test mock events (which may use mixed case for readability).
- The property test conftest.py (tests/property/conftest.py) already provides a `lambda_response` Hypothesis strategy that generates valid Lambda proxy integration response dicts. This existing pattern should be leveraged and extended for property-based testing of the native handler.
- Some test files construct TestClient at module level (`client = TestClient(app)` outside any fixture or class), which means FastAPI app construction happens at import time. These must be converted to fixture-scoped construction to prevent import-time side effects and ensure test isolation per FR-060.
- The conftest.py `ohlc_test_client` fixture (lines 504-531) uses `dependency_overrides` but is defined and never imported by any test file. This dead fixture will fail SC-008's search but poses no functional risk. It must be removed or migrated.
