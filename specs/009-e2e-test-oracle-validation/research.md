# Research: E2E Test Oracle Validation

**Feature**: 009-e2e-test-oracle-validation
**Date**: 2025-11-29
**Status**: Complete

## Executive Summary

This research documents the current state of E2E test infrastructure, identifies gaps from the audit findings, and evaluates implementation approaches for fixing test oracle validation, eliminating dual-outcome assertions, extending synthetic data coverage, and adding failure mode tests.

## Audit Findings Summary

The E2E test audit conducted 2025-11-29 identified the following issues:

| Category | Finding | Severity | Files Affected |
|----------|---------|----------|----------------|
| Oracle Validation | `test_sentiment_with_synthetic_oracle` validates structure only, not values | High | test_sentiment.py |
| Dual-Outcome Assertions | 8+ tests use `assert A or B` patterns | High | test_rate_limiting.py, test_auth.py, others |
| Synthetic Data Coverage | Only 2/20 test files use synthetic data generators | Medium | 18 test files |
| Failure Mode Testing | Processing layer error paths untested | Medium | All pipeline tests |
| Skip Rate | High skip rate (~25%) with poor skip messages | Low | Multiple files |

## Current Test Infrastructure Analysis

### Existing Test Oracle (`tests/fixtures/synthetic/test_oracle.py`)

The `SyntheticTestOracle` class provides:

1. **ATR Computation** - `compute_expected_atr()`, `compute_expected_atr_result()`, `compute_expected_volatility_level()`
2. **Sentiment Computation** - `compute_expected_avg_sentiment()`, `compute_expected_sentiment_trend()`
3. **News Distribution** - `compute_expected_news_sentiment_distribution()`
4. **Scenario Generation** - `generate_test_scenario()` creates complete `TestScenario` objects

**Gap Identified**: The oracle computes expected values but `test_sentiment.py` does NOT use these computed values for assertions. Instead, it only validates response structure.

### Synthetic Data Generators

Located in `tests/fixtures/synthetic/`:

| Generator | Purpose | Seed Support |
|-----------|---------|--------------|
| `ticker_generator.py` | OHLC candle data | Yes |
| `news_generator.py` | News articles with sentiment | Yes |
| `sentiment_generator.py` | Sentiment time series | Yes |

All generators support seeded random (`random.Random(seed)`) for deterministic replay.

### E2E Fixtures (`tests/e2e/conftest.py`)

Two fixture sets exist:

1. **Legacy fixtures** (mock_tiingo, mock_finnhub, mock_sendgrid) - For local mocked tests
2. **Preprod fixtures** (api_client, tiingo_handler, finnhub_handler) - For real AWS E2E tests

Key fixtures:
- `test_run_id`: UUID-based session identifier (`f"e2e-{uuid.uuid4().hex[:8]}"`)
- `synthetic_seed`: Derived from test_run_id for determinism
- `e2e_context`: Bundles all test fixtures into `E2ETestContext`

### Dual-Outcome Assertion Patterns Found

```python
# Pattern 1: Rate limiting (test_rate_limiting.py)
assert rate_limited > 0 or successes == len(status_codes)

# Pattern 2: Auth fallback (test_auth.py)
assert response.status == 200 or response.status == 201

# Pattern 3: Quota tracking
assert quota_remaining > 0 or quota_exhausted
```

**Problem**: These assertions pass regardless of which branch executes, making it impossible to detect regressions in the specific behavior under test.

### Mock Adapter Fail Mode Support

`conftest.py` provides context managers for failure injection:

```python
@contextmanager
def fail_mode_tiingo(mock: MockTiingoAdapter):
    mock.fail_mode = True
    yield mock
    mock.fail_mode = original

@contextmanager
def fail_mode_finnhub(mock: MockFinnhubAdapter):
    # Similar pattern

@contextmanager
def rate_limit_sendgrid(mock: MockSendGrid):
    # Similar pattern
```

**Gap**: These are defined but not used in existing E2E tests.

## Implementation Approach Evaluation

### Approach 1: Oracle Comparison Pattern

**Constitution Alignment**: Section 7.214-216 mandates test oracle computing expected values.

```python
# Proposed pattern (from constitution example)
synthetic_data = generate_synthetic_ticker_data(seed=12345)
mock_tiingo.configure(synthetic_data)

response = dashboard_api.get_sentiment(config_id)

expected = compute_expected_sentiment(synthetic_data)
assert abs(response.sentiment - expected) <= 0.01  # Tolerance-based
```

**Recommendation**: Extend `SyntheticTestOracle` with `compute_expected_api_sentiment()` that mirrors the production calculation pipeline.

### Approach 2: Split Dual-Outcome Tests

**Strategy**: Convert each `assert A or B` into two separate tests:

| Original | Split Into |
|----------|------------|
| `test_rate_limit()` | `test_rate_limit_triggers_after_threshold()` + `test_no_rate_limit_under_threshold()` |
| `test_auth_status()` | `test_auth_new_session_returns_201()` + `test_auth_existing_session_returns_200()` |

**Skip Handling**: When a test cannot trigger its target condition in preprod, use explicit skip with actionable message:

```python
@pytest.mark.skipif(
    os.environ.get("RATE_LIMIT_THRESHOLD", "1000") == "1000",
    reason="Rate limit threshold too high to test in preprod. Set RATE_LIMIT_THRESHOLD=10 for testing."
)
def test_rate_limit_triggers_after_threshold():
    ...
```

### Approach 3: Extend Synthetic Data to All Tests

**Current State**: 2/20 test files use synthetic data
**Target**: 20/20 test files

**Migration Pattern**:

```python
# Before (hardcoded)
config = {"name": "Test Config", "tickers": [{"symbol": "AAPL"}]}

# After (synthetic)
@pytest.fixture
def test_config(synthetic_seed):
    gen = create_config_generator(seed=synthetic_seed)
    return gen.generate_config()
```

**New Generator Needed**: `config_generator.py` for synthetic configuration names and ticker combinations.

### Approach 4: Failure Injection Tests

**Target Error Paths**:

1. **Malformed API response** - Test graceful degradation when Tiingo/Finnhub returns invalid JSON
2. **Timeout handling** - Verify retry/fallback when external API times out
3. **Circuit breaker state** - Inject failures to trigger circuit breaker transitions
4. **DynamoDB throttling** - Simulate ConditionalCheckFailed and ProvisionedThroughputExceededException

**Implementation Using Existing Infrastructure**:

```python
def test_tiingo_failure_graceful_degradation(mock_tiingo, api_client):
    with fail_mode_tiingo(mock_tiingo):
        response = await api_client.get_sentiment(config_id)

    assert response.status_code in [200, 503]  # Graceful fallback or service unavailable
    if response.status_code == 200:
        assert response.json()["source"] == "cache"  # Fell back to cached data
```

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Oracle computation differs from production | Medium | High | Use same algorithms; add unit tests for oracle |
| Synthetic data edge cases break tests | Low | Medium | Generate within realistic bounds; test generators |
| Preprod rate limits prevent testing | High | Medium | Use explicit skips with actionable messages |
| Refactoring breaks existing passing tests | Low | High | Run full suite after each change; incremental commits |

## Dependencies

| Dependency | Type | Status |
|------------|------|--------|
| `tests/fixtures/synthetic/test_oracle.py` | Internal | Exists, needs extension |
| `tests/e2e/conftest.py` | Internal | Exists, has fixtures |
| Production sentiment algorithms | Internal | Must be accessible for oracle |
| pytest-asyncio | External | Already installed |
| httpx | External | Already installed |

## Recommendations

1. **Phase 1**: Fix `test_sentiment_with_synthetic_oracle` to compare actual vs oracle values (P1)
2. **Phase 2**: Split all dual-outcome assertions into separate tests (P1)
3. **Phase 3**: Create `config_generator.py` and migrate remaining tests to synthetic data (P2)
4. **Phase 4**: Add failure injection tests using existing `fail_mode_*` context managers (P2)
5. **Phase 5**: Audit skip messages and reduce skip rate below 15% (P3)

## References

- Constitution Section 7: Testing & Validation (lines 179-319)
- E2E Audit Report: 2025-11-29 (conversation context)
- Existing oracle: `tests/fixtures/synthetic/test_oracle.py`
- Existing fixtures: `tests/e2e/conftest.py`
