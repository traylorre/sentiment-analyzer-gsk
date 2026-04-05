# Feature 1313: Implementation Plan

## Change Set

### Modified: `tests/integration/conftest.py`

**Location**: After existing imports (line 21), add:
- `import pytest_asyncio`
- `from collections.abc import AsyncGenerator`
- `from tests.e2e.helpers.api_client import PreprodAPIClient`

**Location**: After the `clear_all_caches` fixture (end of file, ~line 198), add:
- New section header for preprod fixtures
- `api_client` async fixture yielding `PreprodAPIClient`

### No other files modified

The test file (`test_canary_preprod.py`) already imports `PreprodAPIClient` for
type annotations and uses `api_client` as a fixture parameter. No changes needed.

## Dependency Order

1. Add imports to `tests/integration/conftest.py`
2. Add fixture definition to `tests/integration/conftest.py`
3. Verify with `--collect-only`

## Risk Assessment

- **Regression risk**: None. No existing code is modified.
- **Import risk**: Low. The import path already works (test file uses it).
- **Scope creep**: None. Single fixture addition.
