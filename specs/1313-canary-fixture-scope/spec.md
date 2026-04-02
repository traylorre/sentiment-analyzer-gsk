# Feature 1313: Canary Fixture Scope Fix

## Problem Statement

6 tests in `tests/integration/test_canary_preprod.py` fail with:
```
fixture 'api_client' not found
```

The `api_client` fixture is defined in `tests/e2e/conftest.py:463-471`. However,
`test_canary_preprod.py` lives in `tests/integration/`. pytest conftest fixtures
only scope downward in the directory tree -- `tests/e2e/conftest.py` is invisible
to `tests/integration/`.

## Root Cause

pytest fixture resolution walks UP from the test file to the root, collecting
fixtures from each `conftest.py` along the way. It does NOT walk sideways into
sibling directories. Since `tests/e2e/` and `tests/integration/` are siblings,
the `api_client` fixture defined in `tests/e2e/conftest.py` is unreachable.

## Affected Tests

All 6 async test methods in `TestCanaryPreprod`:
1. `test_health_endpoint_structure`
2. `test_health_endpoint_performance`
3. `test_health_endpoint_public_access`
4. `test_health_endpoint_idempotency`
5. `test_health_endpoint_concurrent_requests`
6. `test_health_endpoint_error_messages`

## Solution

Add an `api_client` fixture to `tests/integration/conftest.py` that mirrors the
definition in `tests/e2e/conftest.py:463-471`:

```python
import pytest_asyncio
from collections.abc import AsyncGenerator
from tests.e2e.helpers.api_client import PreprodAPIClient

@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[PreprodAPIClient]:
    """Preprod API client for canary tests (mirrored from e2e/conftest.py)."""
    async with PreprodAPIClient() as client:
        yield client
```

## Alternatives Considered

### Move to `tests/conftest.py` (root) -- REJECTED

Moving `api_client` to the root conftest would make it available everywhere, but:
- Pollutes unit test namespace with preprod infrastructure fixtures
- `PreprodAPIClient` import would fail in unit test environments without httpx/boto3
- Violates separation of concerns (unit tests should not see preprod fixtures)

### Plugin-based fixture sharing -- REJECTED

A pytest plugin could share fixtures across directories, but:
- Over-engineered for a single fixture
- Adds maintenance burden
- Not the pattern used elsewhere in this project

## Verification

```bash
# Before fix: 6 failures
pytest tests/integration/test_canary_preprod.py --collect-only 2>&1 | grep "fixture 'api_client' not found"

# After fix: 6 tests collected
pytest tests/integration/test_canary_preprod.py --collect-only 2>&1 | grep "test session starts"
```

## Scope

- Files modified: 1 (`tests/integration/conftest.py`)
- Lines added: ~10
- Risk: Minimal -- additive change, no existing behavior altered
