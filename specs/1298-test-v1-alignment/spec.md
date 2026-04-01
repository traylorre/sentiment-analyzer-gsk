# Feature 1298: Align Test Infrastructure to Production Event Format (v1)

## Problem Statement

All test event factories and transports construct Function URL v2 events (`version: "2.0"`, `rawPath`, `requestContext.http.method`). The Dashboard Lambda's production path is API Gateway REST → v1 events (`httpMethod`, `path`, `requestContext.identity`). After Feature 1297 switches the handler to `APIGatewayRestResolver`, v2 events will be explicitly rejected (400).

Tests must speak the production event format.

### Security-First Rationale

Tests that bypass the production event format are false positives. They validate a code path that doesn't exist in production. When the production path breaks (Feature 1295: Lambda permission missing), these tests pass. Aligning tests to v1 ensures they exercise the same event parsing, middleware, and routing as production traffic.

## Requirements

### FR-001: Switch `make_event()` to v1 format
Update `tests/conftest.py:make_event()` to produce API Gateway REST proxy event format:
- `httpMethod` instead of `requestContext.http.method`
- `path` instead of `rawPath`
- `requestContext.identity.sourceIp` instead of `requestContext.http.sourceIp`
- `resource: "/{proxy+}"` and `pathParameters.proxy`
- `multiValueHeaders` (all values as lists)
- `multiValueQueryStringParameters` (all values as lists)
- No `version: "2.0"` field
- No `rawQueryString` field
- Headers lowercased (matching HTTP/2 normalization by API Gateway)

### FR-002: Switch `LambdaInvokeTransport` to v1 format
Update `tests/e2e/helpers/lambda_invoke_transport.py:build_event()` to produce v1 format matching FR-001.

### FR-003: Preserve `make_function_url_event()` as v2
`tests/conftest.py:make_function_url_event()` stays v2 �� it's used by SSE Lambda tests whose production path IS Function URL v2 (CloudFront → OAC → Function URL).

### NFR-001: Zero test logic changes
Only event construction changes. No test assertions, test logic, or test file structure changes. The 331 usages of `make_event()` update automatically.

### NFR-002: Same commit as Feature 1297
Must be merged in the same commit as the resolver switch to avoid a window where tests fail.

## Success Criteria

1. `make_event()` produces v1 format
2. `LambdaInvokeTransport.build_event()` produces v1 format
3. `make_function_url_event()` unchanged (still v2)
4. All unit tests pass with new fixtures + new resolver
5. All integration tests pass
6. All 11 failing preprod E2E tests pass after deploy

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | `make_event()` has 331 usages across 21 files. If the v1 format is subtly wrong (e.g., missing `resource` field, wrong `requestContext` structure), all 331 tests will fail with opaque Powertools errors, not clear "wrong format" errors. Debugging 331 failures is nightmare. | **Mitigate**: Build v1 fixture from AWS documentation's canonical example. Run ONE test first (e.g., `test_dashboard_handler.py::test_health`) to validate the fixture before running all 331. |
| MEDIUM | FR-001 says "headers lowercased (matching HTTP/2 normalization)." But v1 events from API Gateway with HTTP/1.1 clients preserve original case. Our v1 fixture lowercasing headers is MORE normalized than real production v1 events. This means tests won't catch case-sensitivity bugs in code that reads headers directly. | **Accept**: Feature 1297 T3 fixes header normalization in `get_header()` and `_get_request_origin()`. Tests with lowercase headers validate the happy path. Real case-sensitivity bugs are caught by the 66 HTTP-based E2E tests that send real HTTP requests through API Gateway. |
| MEDIUM | `LambdaInvokeTransport` change affects 147 E2E tests that run against real preprod Lambda. If the v1 event format is wrong, these tests fail at deploy time in CI, not locally. | **Mitigate**: The v1 event format in `LambdaInvokeTransport` should match `make_event()` exactly. Both use the same canonical v1 structure. |
| LOW | `multiValueHeaders` and `multiValueQueryStringParameters` are technically optional in v1 proxy events. Some Lambda Powertools versions handle their absence. Including them is more realistic but adds complexity. | **Include them**: They're part of the real v1 format. Omitting them would make tests less realistic than production. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** HIGH finding mitigated by incremental validation approach. Proceeding to Stage 3.

## Clarifications

### Q1: Should `pathParameters` include `{"proxy": path.lstrip("/")}` for all routes?
**Answer:** Yes. API Gateway REST with `{proxy+}` resource always populates `pathParameters.proxy` with the matched path segment. For `/health`, proxy = `"health"`. For `/api/v2/metrics`, proxy = `"api/v2/metrics"`. If `path_params` is explicitly provided (e.g., for routes like `/chaos/experiments/<id>`), merge: `{"proxy": path.lstrip("/"), **path_params}`.
**Evidence:** AWS API Gateway proxy integration documentation.

### Q2: Should `requestContext.path` include the stage prefix?
**Answer:** Yes. `requestContext.path` = `/v1` + path (stage prefix included). `path` (top-level) = path WITHOUT stage prefix. The resolver uses `path` (top-level), not `requestContext.path`. Using `"v1"` as the stage name matches the Terraform configuration (`var.stage_name` default = `"v1"`).
**Evidence:** Feature 1297 clarification Q1, verified from Powertools source.

All questions self-answered. No questions deferred to user.
