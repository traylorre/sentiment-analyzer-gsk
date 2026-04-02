# Feature 1306: Transport multiValueHeaders Support

## Description

The E2E test transport (`lambda_invoke_transport.py`) parses Lambda responses but only reads from `payload.get("headers", {})`. AWS Lambda handlers using Powertools `APIGatewayRestResolver` return responses with `multiValueHeaders` (API Gateway REST v1 format) and do NOT include a `headers` key. This causes `LambdaResponse.headers` to be empty, making all header-based assertions in E2E tests fail (e.g., `Expected application/json, got: ""`).

The fix must handle both `multiValueHeaders` (v1) and `headers` (v2) response formats in `_parse_lambda_response()`, matching the precedence and extraction logic already proven in `tests/conftest.py:get_response_header()`.

## User Stories

### US-1: Developer running E2E tests via invoke transport

**As a** developer running E2E tests with `transport="invoke"`,
**I want** `LambdaResponse.headers` to be populated from `multiValueHeaders` when present,
**So that** assertions like `response.headers.get("content-type", "")` work identically whether the Lambda returns v1 or v2 format.

**Acceptance Criteria:**
- AC-1.1: When Lambda returns `multiValueHeaders` only, `LambdaResponse.headers` contains all headers with single string values.
- AC-1.2: When Lambda returns `headers` only (v2 format), behavior is unchanged from current implementation.
- AC-1.3: When Lambda returns both `multiValueHeaders` and `headers`, `multiValueHeaders` takes precedence (v1 is the canonical format from APIGatewayRestResolver).
- AC-1.4: All header keys in `LambdaResponse.headers` are lowercase (matching httpx.Response behavior).

### US-2: CI pipeline running preprod E2E suite

**As the** CI pipeline,
**I want** the invoke transport to correctly parse all Lambda response formats,
**So that** E2E tests pass without false failures caused by empty headers.

**Acceptance Criteria:**
- AC-2.1: `test_dashboard_buffered.py` tests pass with content-type assertions succeeding.
- AC-2.2: All other E2E tests using `LambdaResponse` via invoke transport pass header assertions.
- AC-2.3: No regression for tests using httpx transport (they don't use `_parse_lambda_response`).

## Requirements

### Functional Requirements

| ID | Requirement | Priority |
|----|------------|----------|
| FR-001 | `_parse_lambda_response()` MUST extract headers from `multiValueHeaders` when present | P0 |
| FR-002 | For `multiValueHeaders`, each header value MUST be the first element of the list (matching httpx single-value semantics) | P0 |
| FR-003 | `_parse_lambda_response()` MUST fall back to `headers` when `multiValueHeaders` is absent or empty | P0 |
| FR-004 | All header keys MUST be normalized to lowercase | P0 |
| FR-005 | When both `multiValueHeaders` and `headers` are present, `multiValueHeaders` MUST take precedence | P1 |
| FR-006 | Empty lists in `multiValueHeaders` values MUST be skipped (not produce empty string headers) | P1 |
| FR-007 | `None` values in `multiValueHeaders` MUST be handled without raising exceptions | P1 |

### Non-Functional Requirements

| ID | Requirement | Priority |
|----|------------|----------|
| NFR-001 | Zero changes to `LambdaResponse` dataclass interface (headers remains `dict[str, str]`) | P0 |
| NFR-002 | Zero changes to test files (fix is entirely in the transport layer) | P0 |
| NFR-003 | Change is confined to `_parse_lambda_response()` function only | P0 |
| NFR-004 | Compatible with existing `get_response_header()` logic in `tests/conftest.py` | P1 |

## Success Criteria

1. All 8 `test_dashboard_buffered.py` tests pass with `transport="invoke"`.
2. All E2E tests that assert on `response.headers` pass with invoke transport.
3. No changes to any test file or the `LambdaResponse` dataclass.
4. Unit tests cover: multiValueHeaders-only, headers-only, both-present, empty-list, None-value edge cases.

## Edge Cases

| Case | Input | Expected Behavior |
|------|-------|-------------------|
| multiValueHeaders only (production case) | `{"multiValueHeaders": {"Content-Type": ["application/json"]}}` | `headers["content-type"] == "application/json"` |
| headers only (v2 format) | `{"headers": {"content-type": "application/json"}}` | `headers["content-type"] == "application/json"` |
| Both present | `{"multiValueHeaders": {"Content-Type": ["text/html"]}, "headers": {"content-type": "application/json"}}` | `headers["content-type"] == "text/html"` (multiValueHeaders wins) |
| Empty list value | `{"multiValueHeaders": {"X-Empty": []}}` | `X-Empty` is not present in headers |
| None value in list | `{"multiValueHeaders": {"X-Bad": [None, "good"]}}` | `headers["x-bad"] == "good"` (skip None, take first non-None) |
| None as entire value | `{"multiValueHeaders": {"X-Null": None}}` | `X-Null` is not present in headers |
| Mixed case keys | `{"multiValueHeaders": {"Content-TYPE": ["text/html"]}}` | `headers["content-type"] == "text/html"` |
| multiValueHeaders is empty dict | `{"multiValueHeaders": {}}` | Fall through to `headers` |
| multiValueHeaders is None | `{"multiValueHeaders": None}` | Fall through to `headers` |
| Neither present | `{}` | `headers == {}` |
| Set-Cookie with multiple values | `{"multiValueHeaders": {"Set-Cookie": ["a=1", "b=2"]}}` | `headers["set-cookie"] == "a=1"` (first value, matching httpx single-value) |
| Single-element list | `{"multiValueHeaders": {"Content-Type": ["application/json"]}}` | `headers["content-type"] == "application/json"` |

## Out of Scope

- Changing the `LambdaResponse` dataclass to support multi-value headers (e.g., `dict[str, list[str]]`). The httpx.Response interface uses single-value headers.
- Fixing `_build_apigw_rest_event()` (it correctly builds v1 events already).
- Modifying any E2E test files.
- Supporting `Set-Cookie` as a multi-value header via a special case. httpx.Response also collapses to single value. Tests that need multi-value Set-Cookie should use a different approach.
- Changes to `get_response_header()` in `tests/conftest.py` (it already handles both formats correctly for unit/integration tests).

## Adversarial Review #1

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | CRITICAL | **Header merging precedence ambiguity**: Spec says multiValueHeaders wins when both present, but what about per-header merging? If multiValueHeaders has `Content-Type` and headers has `X-Custom`, should both be included? | RESOLVED: Yes. multiValueHeaders is the primary source; any headers NOT in multiValueHeaders should be pulled from `headers` as fallback. Updated FR-005 intent: multiValueHeaders is primary, headers fills gaps. This matches the reference implementation's cascading lookup. However, for simplicity and because production only returns multiValueHeaders, the implementation will use multiValueHeaders exclusively when present (non-empty), falling back to headers entirely when multiValueHeaders is absent/empty. Per-header merging adds complexity for a case that doesn't occur in practice. |
| 2 | HIGH | **Case sensitivity in precedence check**: If multiValueHeaders has `Content-Type` and headers has `content-type`, are these the same header? | RESOLVED: Yes. Both are normalized to lowercase before insertion into the dict. Since multiValueHeaders is checked first and all keys are lowered, the headers fallback would overwrite with the same key. But since we use whole-dict fallback (not per-header merge), this is moot: if multiValueHeaders is non-empty, headers dict is ignored entirely. |
| 3 | HIGH | **Set-Cookie multi-value loss**: Taking only first value from Set-Cookie loses authentication cookies. | RESOLVED: Acceptable. httpx.Response also stores headers as `dict[str, str]` internally (with special multi-header support via `response.headers.get_list()`). Our `LambdaResponse` is a simplified compatibility shim. E2E tests that check Set-Cookie only check presence or first value. No E2E test iterates multiple Set-Cookie values. If needed in future, `LambdaResponse` can be extended (separate feature). |
| 4 | MEDIUM | **None filtering in lists**: FR-007 says handle None but doesn't specify behavior for `[None]` (list with only None). | RESOLVED: A list containing only None values should be treated as empty, meaning that header is skipped. Spec edge case table updated to clarify: skip None, take first non-None. If all values are None, header is absent. |
| 5 | LOW | **String coercion**: What if multiValueHeaders contains `{"Content-Length": [42]}` (int instead of string)? | RESOLVED: Coerce to string via `str()`. This is defensive and costs nothing. The reference implementation in conftest.py already does `str(v)` for non-list values. |

### Gate Statement

**AR#1 PASS**: All CRITICAL and HIGH findings resolved. The spec is coherent, edge cases are enumerated, and precedence rules are clear. Proceeding to planning.

## Clarifications

### Q1: Is the transport always "invoke" when this bug manifests, or can it happen with "http" transport too?

**Answer (from codebase)**: Only with `transport="invoke"`. The `_parse_lambda_response()` function is only called by `LambdaInvokeTransport.invoke()` (line 192). When `transport="http"`, the client uses httpx which returns real `httpx.Response` objects with properly parsed HTTP headers. The bug is confined to the invoke transport path.

Source: `tests/e2e/helpers/api_client.py:79-82` (invoke transport initialization), `tests/e2e/helpers/lambda_invoke_transport.py:192` (only call site).

### Q2: What determines whether the API client uses invoke or http transport?

**Answer (from codebase)**: The `PREPROD_TRANSPORT` environment variable, defaulting to `"http"`. Can also be passed explicitly via `PreprodAPIClient(transport="invoke")`. The E2E conftest creates the client via `PreprodAPIClient()` which reads from the environment.

Source: `tests/e2e/helpers/api_client.py:55-66`.

### Q3: Are there existing unit tests for `_parse_lambda_response()`?

**Answer (from codebase)**: No. There are no unit tests for `lambda_invoke_transport.py` at all. The plan includes creating `tests/unit/test_lambda_invoke_transport.py` with 11 test cases covering all edge cases.

Source: Glob search for `test*transport*` and `test*lambda*invoke*` returned no results.

### Q4: Does the `LambdaResponse` need to support iteration over multiple values for the same header (like httpx's `headers.get_list()`)?

**Answer (from codebase)**: No. `LambdaResponse.headers` is typed as `dict[str, str]` (line 41). All E2E tests access headers via `response.headers.get("header-name", "")` which expects a single string value. No test calls `.get_list()` or iterates multi-values. The single-value-per-key model is sufficient.

Source: `tests/e2e/helpers/lambda_invoke_transport.py:41`, grep for `response.headers` across E2E tests.

### Q5: Could the Lambda handler ever return BOTH `headers` and `multiValueHeaders` with different values for the same header?

**Answer (from codebase)**: In practice, no. Powertools `APIGatewayRestResolver` only returns `multiValueHeaders`. The property test strategy in `tests/property/conftest.py:24-31` generates only `multiValueHeaders`. However, the fix handles this defensively: when `multiValueHeaders` is non-empty, `headers` is ignored entirely. This is the safest approach since `multiValueHeaders` is the canonical v1 format.
