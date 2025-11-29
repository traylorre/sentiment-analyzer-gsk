# Quickstart: E2E Test Oracle Validation

**Feature**: 009-e2e-test-oracle-validation
**Date**: 2025-11-29

## Prerequisites

- Python 3.13
- pytest, pytest-asyncio
- AWS credentials configured for preprod (E2E tests only)

## Running Tests

### Unit Tests (Local)

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run oracle unit tests specifically
pytest tests/unit/fixtures/test_oracle_unit.py -v

# Run with coverage
pytest tests/unit/ --cov=tests/fixtures/synthetic --cov-report=term-missing
```

### E2E Tests (Preprod only)

```bash
# E2E tests run ONLY in CI pipeline
# They require real AWS resources

# To run manually (requires AWS credentials):
E2E_TEST_SEED=42 pytest tests/e2e/ -v -m preprod

# Run specific test file
pytest tests/e2e/test_sentiment.py -v -m preprod

# Run with specific seed for reproducibility
E2E_TEST_SEED=12345 pytest tests/e2e/test_sentiment.py -v -m preprod
```

## Using the Test Oracle

### Basic Oracle Usage

```python
from tests.fixtures.synthetic.test_oracle import create_test_oracle

# Create oracle with seed
oracle = create_test_oracle(seed=42)

# Compute expected sentiment
expected_sentiment = oracle.compute_expected_avg_sentiment(
    ticker="AAPL",
    days=30,
)
print(f"Expected sentiment: {expected_sentiment}")

# Generate complete test scenario
scenario = oracle.generate_test_scenario(
    ticker="AAPL",
    days=30,
    news_count=15,
)
print(f"Expected ATR: {scenario.expected_atr}")
print(f"Expected volatility: {scenario.expected_volatility_level}")
```

### Oracle Comparison Pattern

```python
import pytest
from tests.fixtures.synthetic.test_oracle import create_test_oracle

@pytest.fixture
def test_oracle(synthetic_seed: int):
    return create_test_oracle(seed=synthetic_seed)

@pytest.mark.preprod
async def test_sentiment_matches_oracle(
    api_client,
    test_oracle,
    synthetic_config,
):
    """Verify API sentiment matches oracle expectation."""
    # Get expected value from oracle
    expected = test_oracle.compute_expected_api_sentiment(synthetic_config)

    # Call API
    response = await api_client.get_sentiment(synthetic_config.config_id)

    # Compare with tolerance
    actual = response.json()["sentiment_score"]
    assert abs(actual - expected.sentiment_score) <= 0.01, (
        f"Sentiment {actual} differs from oracle {expected.sentiment_score}"
    )
```

## Using Synthetic Data Generators

### Configuration Generator

```python
from tests.fixtures.synthetic.config_generator import create_config_generator

# Create generator with seed
gen = create_config_generator(seed=42)

# Generate synthetic configuration
config = gen.generate_config(
    test_run_id="e2e-abc12345",
    ticker_count=3,
)

print(f"Config name: {config.name}")
print(f"Tickers: {[t.symbol for t in config.tickers]}")
print(f"User ID: {config.user_id}")
```

### Deterministic Data

```python
# Same seed = same data
gen1 = create_config_generator(seed=12345)
gen2 = create_config_generator(seed=12345)

config1 = gen1.generate_config("test-run")
config2 = gen2.generate_config("test-run")

assert config1.name == config2.name  # Deterministic!
```

## Converting Dual-Outcome Tests

### Before (Anti-pattern)

```python
def test_rate_limiting():
    """Bad: passes regardless of rate limiting behavior."""
    results = make_requests(100)
    rate_limited = count_rate_limited(results)
    successes = count_successes(results)

    # This always passes!
    assert rate_limited > 0 or successes == len(results)
```

### After (Correct Pattern)

```python
@pytest.mark.preprod
def test_rate_limit_triggers_after_threshold():
    """Good: tests specific behavior."""
    results = make_requests(threshold + 10)
    rate_limited = count_rate_limited(results)

    if rate_limited == 0:
        pytest.skip(
            "SKIPPED: Rate limit not triggered\n"
            "Reason: Preprod threshold higher than test limit\n"
            "To run: Set RATE_LIMIT_THRESHOLD=10"
        )

    assert rate_limited >= 10, "Expected at least 10 rate-limited requests"


@pytest.mark.preprod
def test_requests_succeed_under_threshold():
    """Good: tests complementary behavior."""
    results = make_requests(threshold - 1)
    successes = count_successes(results)

    assert successes == threshold - 1, "All requests should succeed under threshold"
```

## Failure Injection Testing

### Using Fail Mode Context Managers

```python
from tests.e2e.conftest import fail_mode_tiingo, fail_mode_finnhub

@pytest.mark.preprod
async def test_tiingo_failure_fallback(mock_tiingo, api_client, config_id):
    """Test graceful degradation when Tiingo fails."""
    with fail_mode_tiingo(mock_tiingo):
        response = await api_client.get_sentiment(config_id)

    # Should fallback to cache or return service unavailable
    assert response.status_code in [200, 503]

    if response.status_code == 200:
        data = response.json()
        assert data.get("source") == "cache", "Expected cached fallback"
```

### Circuit Breaker Testing

```python
@pytest.mark.preprod
async def test_circuit_breaker_opens_on_failures(
    mock_tiingo,
    api_client,
    dynamodb_table,
):
    """Test circuit breaker transitions to open state."""
    # Inject 5 consecutive failures
    with fail_mode_tiingo(mock_tiingo):
        for _ in range(5):
            await api_client.get_sentiment(config_id)

    # Check circuit breaker state in DynamoDB
    cb_state = dynamodb_table.get_item(
        Key={"pk": "CB#tiingo", "sk": "STATE"}
    )
    assert cb_state["Item"]["state"] == "open"
```

## Skip Message Format

```python
# Standard skip message format
skip_info = {
    "condition": "Rate limit threshold not reached",
    "reason": "Preprod rate limit is 1000, test expects 100",
    "remediation": "Set RATE_LIMIT_THRESHOLD=100 or run in mock environment",
}

pytest.skip(
    f"SKIPPED: {skip_info['condition']}\n"
    f"Reason: {skip_info['reason']}\n"
    f"To run: {skip_info['remediation']}"
)
```

## Measuring Test Quality

### Skip Rate Check

```bash
# Run tests and check skip rate
pytest tests/e2e/ -v --tb=no | grep -E "(PASSED|FAILED|SKIPPED)"

# Count results
pytest tests/e2e/ -v --tb=no 2>&1 | grep -c SKIPPED
pytest tests/e2e/ -v --tb=no 2>&1 | grep -c PASSED
```

### Oracle Coverage Check

```bash
# Find tests using oracle validation
grep -r "test_oracle\|oracle\." tests/e2e/ --include="*.py" | wc -l

# Find tests with dual-outcome assertions
grep -rn "assert.*or.*==" tests/e2e/ --include="*.py"
```

## Common Issues

### "Oracle computation differs from API"

The oracle uses the same algorithms as production. If values differ:

1. Check that synthetic data seed matches
2. Verify oracle uses same weighted averaging formula
3. Check tolerance (default ±0.01)

### "Test skips in preprod"

Check the skip message for remediation steps. Common causes:

- Rate limit thresholds differ from test expectations
- Resources not available in preprod
- Authentication required

### "Determinism failure"

Ensure:
- Same seed used throughout test
- Generator reset between tests
- No external random sources

## Next Steps

After implementation:

1. Run `/speckit.tasks` to generate implementation tasks
2. Implement oracle extensions
3. Convert dual-outcome tests
4. Add failure injection tests
5. Measure and verify skip rate <15%
