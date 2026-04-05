# Feature 1313: Tasks

## Tasks

- [x] T1: Add `pytest_asyncio`, `AsyncGenerator`, and `PreprodAPIClient` imports to `tests/integration/conftest.py`
- [x] T2: Add `api_client` async fixture to `tests/integration/conftest.py`
- [x] T3: Verify fixture resolution with `pytest --collect-only`

## Dependencies

```
T1 → T2 → T3
```
