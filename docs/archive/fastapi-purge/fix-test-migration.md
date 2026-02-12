# Fix: Update Test Suite (TestClient -> Mock Event)

**Parent:** [HL-fastapi-purge-checklist.md](./HL-fastapi-purge-checklist.md)
**Priority:** P8
**Status:** [ ] TODO
**Depends On:** All code migration tasks (P2-P6)

---

## Problem Statement

The existing test suite uses `fastapi.testclient.TestClient` to send HTTP requests to the FastAPI app. After removing FastAPI, tests must invoke the handler directly with mock event dictionaries.

---

## Pattern Replacement

### FastAPI Test Pattern (Current)

```python
from fastapi.testclient import TestClient
from src.lambdas.dashboard.main import app

client = TestClient(app)

def test_get_ohlc():
    response = client.get("/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D")
    assert response.status_code == 200
    data = response.json()
    assert "candles" in data
```

### Native Handler Test Pattern (Target)

```python
import json
from src.lambdas.dashboard.ohlc import lambda_handler

def _make_event(path="/api/v2/tickers/AAPL/ohlc", method="GET",
                query_params=None, path_params=None):
    """Build mock API Gateway proxy event."""
    return {
        "resource": path,
        "path": path,
        "httpMethod": method,
        "queryStringParameters": query_params,
        "pathParameters": path_params,
        "headers": {"Content-Type": "application/json"},
        "requestContext": {"authorizer": {}},
        "body": None,
        "isBase64Encoded": False,
    }

def _make_context(timeout_ms=30000):
    """Build mock Lambda context."""
    class MockContext:
        function_name = "test-dashboard"
        memory_limit_in_mb = 1024
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
        def get_remaining_time_in_millis(self):
            return timeout_ms
    return MockContext()

def test_get_ohlc():
    event = _make_event(
        path="/api/v2/tickers/{ticker}/ohlc",
        query_params={"range": "1M", "resolution": "D"},
        path_params={"ticker": "AAPL"},
    )
    result = lambda_handler(event, _make_context())
    assert result["statusCode"] == 200
    data = json.loads(result["body"])
    assert "candles" in data
```

---

## Test Helper Fixture (conftest.py)

```python
# tests/unit/dashboard/conftest.py
import pytest

@pytest.fixture
def make_api_event():
    """Factory fixture for API Gateway proxy events."""
    def _make(path, method="GET", query_params=None, path_params=None, body=None):
        return {
            "resource": path,
            "path": path,
            "httpMethod": method,
            "queryStringParameters": query_params,
            "pathParameters": path_params,
            "headers": {"Content-Type": "application/json"},
            "requestContext": {"authorizer": {}},
            "body": json.dumps(body) if body else None,
            "isBase64Encoded": False,
        }
    return _make

@pytest.fixture
def mock_context():
    """Mock Lambda context with 30s timeout."""
    class MockContext:
        function_name = "test-dashboard"
        memory_limit_in_mb = 1024
        invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"
        def get_remaining_time_in_millis(self):
            return 30000
    return MockContext()
```

---

## Migration Checklist

- [ ] Catalog all TestClient test files from audit
- [ ] Create `make_api_event` and `mock_context` fixtures in conftest.py
- [ ] Convert each `client.get(url)` to `lambda_handler(event, context)`
- [ ] Convert each `response.json()` to `json.loads(result["body"])`
- [ ] Convert each `response.status_code` to `result["statusCode"]`
- [ ] Convert each `response.headers[key]` to `result["headers"][key]`
- [ ] Remove all `from fastapi.testclient import TestClient`
- [ ] Remove all `TestClient(app)` instantiations
- [ ] Verify test count is identical before/after migration

---

## Mock Event Fidelity

Real API Gateway events have many more fields. Only include fields the handler actually reads. Document which fields are used:

```python
# Fields our handler reads:
# - event["resource"]                  -> routing
# - event["httpMethod"]                -> routing
# - event["queryStringParameters"]     -> input parsing
# - event["pathParameters"]            -> input parsing
# - event["requestContext"]["authorizer"] -> auth (if applicable)
# - event["body"]                      -> POST body (if applicable)
```

---

## Playwright Tests (No Change Expected)

Playwright tests hit the deployed API Gateway URL, not the handler directly. They should be transparent to this change. Verify:

- [ ] Playwright tests still pass after deployment
- [ ] No FastAPI-specific response headers that tests assert on

---

## Files to Modify

| File | Change |
|------|--------|
| `tests/unit/dashboard/test_ohlc.py` | Replace TestClient with handler calls |
| `tests/unit/dashboard/conftest.py` | Add mock event/context fixtures |
| `tests/integration/test_dashboard.py` | Update if uses TestClient |

---

## Related

- [audit-fastapi-surface.md](./audit-fastapi-surface.md) - Lists all TestClient usages
- [fix-validation-smoketest.md](./fix-validation-smoketest.md) - End-to-end verification
