# Quickstart: OHLC & Sentiment History Test Suite

**Feature**: 012-ohlc-sentiment-e2e-tests
**Date**: 2025-12-01

## Prerequisites

- Python 3.13+
- Virtual environment activated
- Dependencies installed: `pip install -e ".[dev]"`

## Running Tests

### All Integration Tests

```bash
# Run all OHLC and sentiment history integration tests
pytest tests/integration/ohlc/ tests/integration/sentiment_history/ -v
```

### By User Story

```bash
# US1: OHLC Happy Path (14 scenarios)
pytest tests/integration/ohlc/test_happy_path.py -v

# US2: Sentiment History Happy Path (16 scenarios)
pytest tests/integration/sentiment_history/test_happy_path.py -v

# US3: Error Resilience (30 scenarios)
pytest tests/integration/ohlc/test_error_resilience.py -v

# US4: Boundary Testing (52 scenarios)
pytest -m boundary -v

# US5: Data Consistency (19 scenarios)
pytest tests/integration/ohlc/test_data_consistency.py -v

# US6: Authentication (12 scenarios)
pytest tests/integration/ohlc/test_authentication.py -v

# US7: E2E Preprod (14 scenarios) - requires PREPROD_API_URL
PREPROD_API_URL=https://api.preprod.example.com pytest -m preprod -v
```

### By Test Category

```bash
# OHLC endpoint tests only
pytest -m ohlc -v

# Sentiment history tests only
pytest -m sentiment_history -v

# Error resilience tests only
pytest -m error_resilience -v

# Boundary value tests only
pytest -m boundary -v

# Authentication tests only
pytest -m auth -v
```

### Excluding Preprod Tests (Local Development)

```bash
# Run all tests except preprod (default for local development)
pytest -m "not preprod" -v
```

### Performance Constraints

```bash
# Integration tests should complete in < 5 minutes
pytest tests/integration/ -v --timeout=300

# E2E tests should complete in < 10 minutes
PREPROD_API_URL=... pytest -m preprod -v --timeout=600
```

## Test Markers

| Marker | Description | Usage |
|--------|-------------|-------|
| `integration` | Integration tests with mock adapters | `pytest -m integration` |
| `e2e` | End-to-end tests | `pytest -m e2e` |
| `preprod` | Preprod-only tests | `pytest -m preprod` |
| `ohlc` | OHLC endpoint tests | `pytest -m ohlc` |
| `sentiment_history` | Sentiment history tests | `pytest -m sentiment_history` |
| `error_resilience` | Error injection tests | `pytest -m error_resilience` |
| `boundary` | Boundary value tests | `pytest -m boundary` |
| `auth` | Authentication tests | `pytest -m auth` |

## Fixture Usage

### Mock Adapters

```python
def test_ohlc_with_mock(mock_tiingo, mock_finnhub, test_client):
    """Test using default mock adapters."""
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    assert response.status_code == 200
```

### Failure Injection

```python
def test_tiingo_failure_fallback(tiingo_500_error, mock_finnhub, test_client):
    """Test fallback when Tiingo returns HTTP 500."""
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    assert response.status_code == 200
    assert response.json()["source"] == "finnhub"
```

### Test Oracle

```python
def test_deterministic_response(test_oracle, test_client):
    """Test response matches oracle prediction."""
    expected = test_oracle.expected_ohlc_response("AAPL", start, end)
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    assert response.json()["count"] == expected["count"]
```

### Validators

```python
def test_ohlc_validity(ohlc_validator, test_client):
    """Test response passes all validation rules."""
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    ohlc_validator.assert_valid(response.json())
```

## Writing New Tests

### Adding a Happy Path Test

```python
# tests/integration/ohlc/test_happy_path.py

@pytest.mark.integration
@pytest.mark.ohlc
async def test_ohlc_valid_ticker(test_client):
    """US1 Scenario 1: Valid ticker returns OHLC data."""
    response = test_client.get(
        "/api/v2/tickers/AAPL/ohlc",
        headers={"X-User-ID": "test-user"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "AAPL"
    assert len(data["candles"]) > 0
```

### Adding an Error Resilience Test

```python
# tests/integration/ohlc/test_error_resilience.py

@pytest.mark.integration
@pytest.mark.ohlc
@pytest.mark.error_resilience
async def test_tiingo_502_fallback(test_client, tiingo_502_error):
    """US3 Scenario 2: Tiingo 502 triggers Finnhub fallback."""
    response = test_client.get(
        "/api/v2/tickers/AAPL/ohlc",
        headers={"X-User-ID": "test-user"},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "finnhub"
```

### Adding a Boundary Test

```python
# tests/integration/ohlc/test_boundary_values.py

@pytest.mark.integration
@pytest.mark.ohlc
@pytest.mark.boundary
@pytest.mark.parametrize("ticker,expected_status", [
    ("A", 200),      # 1 char - valid
    ("GOOGL", 200),  # 5 chars - valid
    ("GOOGLE", 400), # 6 chars - invalid
    ("", 400),       # empty - invalid
])
async def test_ticker_length_boundaries(test_client, ticker, expected_status):
    """US4 Scenarios 12-15: Ticker length boundary testing."""
    response = test_client.get(
        f"/api/v2/tickers/{ticker}/ohlc",
        headers={"X-User-ID": "test-user"},
    )
    assert response.status_code == expected_status
```

## Debugging Failed Tests

### Verbose Output

```bash
pytest tests/integration/ohlc/test_happy_path.py -v --tb=long
```

### Show Adapter Calls

```python
def test_with_call_tracking(mock_tiingo, test_client):
    """Track which adapter methods were called."""
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    print(f"Tiingo get_ohlc calls: {mock_tiingo.get_ohlc_calls}")
```

### Validation Details

```python
def test_with_validation_details(ohlc_validator, test_client):
    """Get detailed validation errors."""
    response = test_client.get("/api/v2/tickers/AAPL/ohlc")
    errors = ohlc_validator.validate_response(response.json())
    for error in errors:
        print(f"{error.field}: {error.message} (value={error.value})")
```

## CI/CD Integration

```yaml
# .github/workflows/test.yml
jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install -e ".[dev]"
      - run: pytest -m "not preprod" --timeout=300 -v

  e2e-tests:
    runs-on: ubuntu-latest
    environment: preprod
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.13'
      - run: pip install -e ".[dev]"
      - run: pytest -m preprod --timeout=600 -v
        env:
          PREPROD_API_URL: ${{ secrets.PREPROD_API_URL }}
```
