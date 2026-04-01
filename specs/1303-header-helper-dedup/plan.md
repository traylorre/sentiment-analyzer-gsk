# Feature 1303: Implementation Plan

## Change

In `tests/integration/ohlc/test_happy_path.py`:
1. Remove `_get_header()` function (lines 32-42)
2. Add `from tests.conftest import get_response_header` to imports
3. Replace `_get_header(response, "name")` calls with `get_response_header(response, "name")`
4. Fix any `is not None` assertions to `!= ""` (since `get_response_header` returns `""` not `None`)

## Adversarial Review #2

No drift. Single-file change. Gate: PASS.
