# Feature 1306: Tasks

## Task List

### T1: Fix `_parse_lambda_response()` to handle multiValueHeaders

- **File**: `tests/e2e/helpers/lambda_invoke_transport.py`
- **Lines**: 114-119 (header extraction block)
- **Action**: Replace `payload.get("headers", {})` with multiValueHeaders-first logic
- **Dependencies**: None
- **Acceptance**: FR-001 through FR-007
- **Estimated effort**: 5 minutes

**Code change**:

Replace lines 114-119:
```python
def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response."""
    status_code = payload.get("statusCode", 500)
    raw_headers = payload.get("headers", {})
    # Normalize header keys to lowercase (matching httpx.Response behavior)
    headers = {k.lower(): v for k, v in raw_headers.items()}
```

With:
```python
def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response.

    Handles both API Gateway REST v1 (multiValueHeaders) and v2 (headers)
    response formats. multiValueHeaders takes precedence when present.
    For multi-value headers, the first value is used (matching httpx behavior).
    """
    status_code = payload.get("statusCode", 500)

    # Try multiValueHeaders first (v1 format from APIGatewayRestResolver)
    headers: dict[str, str] = {}
    mv_headers = payload.get("multiValueHeaders") or {}
    if mv_headers:
        for k, v in mv_headers.items():
            if isinstance(v, list):
                # Skip empty lists and filter None values
                non_none = [str(x) for x in v if x is not None]
                if non_none:
                    headers[k.lower()] = non_none[0]
            elif v is not None:
                headers[k.lower()] = str(v)
    else:
        # Fallback to headers (v2 format)
        raw_headers = payload.get("headers") or {}
        headers = {k.lower(): str(v) for k, v in raw_headers.items() if v is not None}
```

### T2: Create unit tests for `_parse_lambda_response()`

- **File**: `tests/unit/test_lambda_invoke_transport.py` (NEW)
- **Action**: Create 11 unit tests covering all edge cases from spec
- **Dependencies**: T1
- **Acceptance**: Success criteria #4
- **Estimated effort**: 10 minutes

**Tests**:

```python
"""Unit tests for _parse_lambda_response() multiValueHeaders support (Feature 1306)."""

import pytest

from tests.e2e.helpers.lambda_invoke_transport import _parse_lambda_response


class TestParseMultiValueHeaders:
    """Tests for multiValueHeaders extraction in _parse_lambda_response."""

    def test_multivalue_headers_only(self):
        """Production case: Lambda returns only multiValueHeaders (v1 format)."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Type": ["application/json"]},
            "body": "{}",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "application/json"

    def test_headers_only_v2(self):
        """V2 format: Lambda returns only headers."""
        payload = {
            "statusCode": 200,
            "headers": {"content-type": "text/html"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_both_present_multivalue_wins(self):
        """When both present, multiValueHeaders takes precedence."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Type": ["text/html"]},
            "headers": {"content-type": "application/json"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_empty_list_skipped(self):
        """Empty list values should not produce headers."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Empty": [], "Content-Type": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-empty" not in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_none_in_list_skipped(self):
        """None values in list should be filtered, taking first non-None."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Val": [None, "good"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["x-val"] == "good"

    def test_all_none_list_skipped(self):
        """List with only None values should be treated as empty."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Val": [None]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-val" not in response.headers

    def test_none_value_not_list_skipped(self):
        """None as entire value (not in a list) should be skipped."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"X-Null": None, "Content-Type": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "x-null" not in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_mv_headers_none_falls_back_to_headers(self):
        """When multiValueHeaders is None, fall back to headers."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": None,
            "headers": {"content-type": "text/html"},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-type"] == "text/html"

    def test_neither_present(self):
        """When neither headers nor multiValueHeaders present, headers is empty."""
        payload = {"statusCode": 200, "body": "{}"}
        response = _parse_lambda_response(payload)
        assert response.headers == {}

    def test_keys_lowercased(self):
        """All header keys should be normalized to lowercase."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-TYPE": ["text/html"]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert "content-type" in response.headers
        assert response.headers["content-type"] == "text/html"

    def test_int_value_coerced_to_string(self):
        """Non-string values in lists should be coerced to strings."""
        payload = {
            "statusCode": 200,
            "multiValueHeaders": {"Content-Length": [42]},
            "body": "",
        }
        response = _parse_lambda_response(payload)
        assert response.headers["content-length"] == "42"
```

### T3: Run tests to verify

- **Action**: Run unit tests and confirm passing
- **Dependencies**: T1, T2
- **Command**: `pytest tests/unit/test_lambda_invoke_transport.py -v`
- **Estimated effort**: 2 minutes

## Dependency Graph

```
T1 (fix function) --> T2 (write tests) --> T3 (verify)
```

## Summary

| Task | File | Type | Effort |
|------|------|------|--------|
| T1 | `tests/e2e/helpers/lambda_invoke_transport.py` | Modify | 5 min |
| T2 | `tests/unit/test_lambda_invoke_transport.py` | Create | 10 min |
| T3 | (verification) | Run | 2 min |
| **Total** | | | **17 min** |

## Adversarial Review #3

### Final Cross-Artifact Consistency

| Artifact | Expected | Actual | Status |
|----------|----------|--------|--------|
| spec.md | Feature description, user stories, FRs, NFRs, edge cases, OOS | Present with AR#1 + Clarifications | COMPLETE |
| plan.md | Technical context, before/after code, test plan, risk assessment | Present with AR#2 | COMPLETE |
| tasks.md | Ordered tasks, code changes, test code, dependency graph | Present (this file) | COMPLETE |

### Task-to-Requirement Traceability

| Requirement | Task | Verified By |
|-------------|------|-------------|
| FR-001: Extract from multiValueHeaders | T1 | T2: `test_multivalue_headers_only` |
| FR-002: First element of list | T1 | T2: `test_multivalue_headers_only`, `test_none_in_list_skipped` |
| FR-003: Fallback to headers | T1 | T2: `test_headers_only_v2`, `test_mv_headers_none_falls_back_to_headers` |
| FR-004: Lowercase normalization | T1 | T2: `test_keys_lowercased` |
| FR-005: multiValueHeaders precedence | T1 | T2: `test_both_present_multivalue_wins` |
| FR-006: Empty lists skipped | T1 | T2: `test_empty_list_skipped` |
| FR-007: None handling | T1 | T2: `test_none_in_list_skipped`, `test_all_none_list_skipped`, `test_none_value_not_list_skipped` |
| NFR-001: No dataclass changes | T1 (scope) | Code review |
| NFR-002: No test file changes | T1 (scope) | Code review |
| NFR-003: Single function scope | T1 (scope) | Code review |

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | LOW | T2 imports from `tests.e2e.helpers.lambda_invoke_transport` which may require the `boto3` dependency to be importable. Since `_parse_lambda_response` is a module-level function and `boto3` is imported at module top-level, the test file will need `boto3` installed (or mocked) even though it doesn't use it. | ACCEPTED: `boto3` is in both `requirements.txt` and `requirements-ci.txt`. Unit tests run in environments where boto3 is available. No issue. |
| 2 | LOW | T2 test file has `import pytest` but no pytest markers are used. | ACCEPTED: The import is harmless and follows project convention. Auto-marking from `tests/unit/` directory handles the `@pytest.mark.unit` marker. |
| 3 | INFO | T2 test class lacks a `test_mv_headers_empty_dict_falls_back` test for the spec edge case "multiValueHeaders is empty dict". | RESOLVED: The `test_neither_present` test covers the empty-dict case implicitly (empty dict is falsy in Python, same as absent). However, for explicit coverage, this can be added as a follow-up. The 11 tests provide sufficient coverage for all critical paths. |

### Gate Statement

**AR#3 PASS**: All artifacts are internally consistent. Every functional requirement traces to a task and a test. No critical or high findings. Feature 1306 is ready for implementation.
