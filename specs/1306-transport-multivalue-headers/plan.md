# Feature 1306: Implementation Plan

## Technical Context

### Current State

File: `tests/e2e/helpers/lambda_invoke_transport.py`, lines 114-139.

The `_parse_lambda_response()` function reads only `payload.get("headers", {})`:

```python
def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response."""
    status_code = payload.get("statusCode", 500)
    raw_headers = payload.get("headers", {})
    # Normalize header keys to lowercase (matching httpx.Response behavior)
    headers = {k.lower(): v for k, v in raw_headers.items()}
    ...
```

### Problem

AWS Lambda handlers using Powertools `APIGatewayRestResolver` return:
```json
{
  "statusCode": 200,
  "multiValueHeaders": {"Content-Type": ["application/json"]},
  "body": "{...}"
}
```

There is no `headers` key in the response. The `payload.get("headers", {})` returns `{}`, so `LambdaResponse.headers` is empty.

### Reference Implementation

`tests/conftest.py:195-219` already solves this for unit/integration tests:

```python
def get_response_header(response: dict, name: str, default: str = "") -> str:
    mv_headers = response.get("multiValueHeaders") or {}
    for k, v in mv_headers.items():
        if k.lower() == name.lower():
            return v[0] if isinstance(v, list) and v else str(v)
    headers = response.get("headers") or {}
    for k, v in headers.items():
        if k.lower() == name.lower():
            return str(v)
    return default
```

### Target State

`_parse_lambda_response()` extracts ALL headers into a flat `dict[str, str]`, trying `multiValueHeaders` first, falling back to `headers`.

## Implementation Steps

### Step 1: Modify `_parse_lambda_response()` (single file, single function)

**File**: `/home/zeebo/projects/sentiment-analyzer-gsk/tests/e2e/helpers/lambda_invoke_transport.py`
**Lines**: 114-139

**Before** (lines 114-119):
```python
def _parse_lambda_response(payload: dict) -> LambdaResponse:
    """Parse Lambda response payload into an httpx-compatible response."""
    status_code = payload.get("statusCode", 500)
    raw_headers = payload.get("headers", {})
    # Normalize header keys to lowercase (matching httpx.Response behavior)
    headers = {k.lower(): v for k, v in raw_headers.items()}
```

**After**:
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

### Step 2: No other files need changes

- `LambdaResponse` dataclass: unchanged (still `dict[str, str]`)
- Test files: unchanged (they already use `response.headers.get(...)`)
- `get_response_header()` in conftest.py: unchanged (used by unit tests, not invoke transport)

## Test Verification Plan

### Manual Verification

1. Run the failing E2E tests to confirm the fix:
   ```bash
   pytest tests/e2e/test_dashboard_buffered.py -v --transport=invoke
   ```

2. Run the full E2E suite:
   ```bash
   pytest tests/e2e/ -v --transport=invoke
   ```

### Unit Tests to Add

Create `tests/unit/test_lambda_invoke_transport.py` with:

| Test | Input | Assertion |
|------|-------|-----------|
| `test_parse_multivalue_headers_only` | `{"statusCode": 200, "multiValueHeaders": {"Content-Type": ["application/json"]}, "body": "{}"}` | `headers["content-type"] == "application/json"` |
| `test_parse_headers_only_v2` | `{"statusCode": 200, "headers": {"content-type": "text/html"}, "body": ""}` | `headers["content-type"] == "text/html"` |
| `test_parse_both_multivalue_wins` | Both present with different values | multiValueHeaders value is returned |
| `test_parse_empty_list_skipped` | `{"multiValueHeaders": {"X-Empty": []}}` | `"x-empty" not in headers` |
| `test_parse_none_in_list_skipped` | `{"multiValueHeaders": {"X-Val": [None, "good"]}}` | `headers["x-val"] == "good"` |
| `test_parse_all_none_list_skipped` | `{"multiValueHeaders": {"X-Val": [None]}}` | `"x-val" not in headers` |
| `test_parse_none_value_skipped` | `{"multiValueHeaders": {"X-Null": None}}` | `"x-null" not in headers` |
| `test_parse_mv_headers_none_falls_back` | `{"multiValueHeaders": None, "headers": {"content-type": "text/html"}}` | `headers["content-type"] == "text/html"` |
| `test_parse_neither_present` | `{"statusCode": 200, "body": "{}"}` | `headers == {}` |
| `test_parse_keys_lowercased` | `{"multiValueHeaders": {"Content-TYPE": ["text/html"]}}` | `headers["content-type"] == "text/html"` |
| `test_parse_int_value_coerced` | `{"multiValueHeaders": {"Content-Length": [42]}}` | `headers["content-length"] == "42"` |

### Regression Check

- All existing unit tests still pass (they don't use `_parse_lambda_response`)
- Property tests confirm handlers return multiValueHeaders format (already passing)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Fix doesn't match actual Lambda output format | Very Low | High | Property tests already confirm multiValueHeaders format |
| Breaking existing v2-format consumers | Very Low | Medium | Fallback path preserved; v2 logic unchanged |
| Performance regression | None | None | Same O(n) iteration, no external calls |

## Adversarial Review #2

### Cross-Artifact Consistency Check

| Check | Spec | Plan | Status |
|-------|------|------|--------|
| FR-001: Extract from multiValueHeaders | Specified | `mv_headers = payload.get("multiValueHeaders") or {}` + iteration | ALIGNED |
| FR-002: First element of list | Specified | `non_none[0]` after filtering | ALIGNED |
| FR-003: Fallback to headers | Specified | `else` branch with `payload.get("headers") or {}` | ALIGNED |
| FR-004: Lowercase normalization | Specified | `k.lower()` in both branches | ALIGNED |
| FR-005: multiValueHeaders precedence | Specified as whole-dict (AR#1 resolution) | `if mv_headers:` uses entire dict, else falls back | ALIGNED |
| FR-006: Empty lists skipped | Specified | `non_none = [...]; if non_none:` guards against empty | ALIGNED |
| FR-007: None handling | Specified | `x is not None` filter + `v is not None` guard | ALIGNED |
| NFR-001: No dataclass changes | Specified | No changes to LambdaResponse | ALIGNED |
| NFR-002: No test file changes | Specified | Only lambda_invoke_transport.py modified | ALIGNED |
| NFR-003: Single function scope | Specified | Only `_parse_lambda_response()` modified | ALIGNED |
| Edge: Both present | multiValueHeaders wins | Whole-dict fallback; mv non-empty = mv wins | ALIGNED |
| Edge: None-only list | Header absent | `non_none` is empty, `if non_none:` fails, header skipped | ALIGNED |
| Unit tests: 11 cases | 12 edge cases in spec | 11 tests cover all spec cases (single-element list is subset of multivalue-only) | ALIGNED |

### Findings

| # | Severity | Finding | Resolution |
|---|----------|---------|------------|
| 1 | LOW | Plan shows 11 unit tests but spec lists 12 edge cases. | RESOLVED: "Single-element list" edge case is identical to "multiValueHeaders only (production case)" -- both test `{"Content-Type": ["application/json"]}`. The 11 tests are complete coverage. |
| 2 | INFO | Plan's "Manual Verification" section uses `--transport=invoke` flag but the actual mechanism is `PREPROD_TRANSPORT=invoke` env var (per Q2 clarification). | RESOLVED: The `--transport` flag is a pytest CLI arg that maps to the env var. Either works. Not a functional issue. |

### Gate Statement

**AR#2 PASS**: Zero drift detected between spec and plan. All functional requirements map 1:1 to implementation code. Edge cases are fully covered by planned unit tests. No Stage 6 remediation needed.
