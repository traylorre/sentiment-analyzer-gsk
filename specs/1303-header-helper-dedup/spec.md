# Feature 1303: Consolidate _get_header() Duplication

## Problem Statement

`_get_header()` is defined in two files:
- `tests/integration/ohlc/test_happy_path.py:32-42` — full 10-line implementation handling both `multiValueHeaders` and `headers`
- `tests/unit/dashboard/test_ohlc.py:263-270` — thin wrapper delegating to `conftest.get_response_header()`

The integration version should use the conftest helper to eliminate duplication.

## Requirements

### FR-001: Replace integration _get_header with conftest import
In `tests/integration/ohlc/test_happy_path.py`:
1. Remove the local `_get_header()` function (lines 32-42)
2. Add `from tests.conftest import get_response_header` to imports
3. Replace all calls to `_get_header(response, "name")` with `get_response_header(response, "name")`

Note: `get_response_header()` returns `""` as default while `_get_header()` returns `None`. Check all assertions for `is not None` vs `!= ""` compatibility.

## Success Criteria

1. No `_get_header` function definition in `test_happy_path.py`
2. All OHLC integration tests pass
3. Single source of truth for response header extraction

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| MEDIUM | `_get_header()` returns `None` when header missing. `get_response_header()` returns `""`. Tests that assert `_get_header(...) is not None` would pass with `get_response_header(...) != ""` but tests asserting `_get_header(...) == "0"` work identically since both return strings when found. | **Resolved:** Check all assertions in test_happy_path.py. Replace `is not None` with `!= ""` where needed. |
| LOW | The unit test version already delegates to conftest. Only the integration version is duplicated. | Confirmed — exactly one duplication to fix. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** Proceeding to Stage 3.

## Clarifications

No ambiguities. Single file change with clear before/after.
