# Research: OHLC & Sentiment History E2E Test Suite

**Feature**: 012-ohlc-sentiment-e2e-tests
**Date**: 2025-12-01
**Status**: Complete

## Research Questions

### RQ-001: How to inject failures into existing mock adapters?

**Decision**: Composition with FailureInjector class

**Research Findings**:
- Existing `MockTiingoAdapter` and `MockFinnhubAdapter` already support `fail_mode=True` for simple failures
- They track calls via `get_ohlc_calls`, `get_news_calls`, `get_sentiment_calls` lists
- They use synthetic data generators from `tests/fixtures/synthetic/`

**Solution**:
```python
class FailureInjector:
    """Configurable failure injection for mock adapters."""

    def __init__(self):
        self.http_error: int | None = None  # 400, 401, 404, 429, 500, etc.
        self.connection_error: str | None = None  # "timeout", "refused", "dns"
        self.malformed_response: str | None = None  # "invalid_json", "empty", "truncated"
        self.missing_fields: list[str] = []  # ["open", "close", "date"]
        self.invalid_values: dict[str, Any] = {}  # {"open": None, "close": float("nan")}
        self.latency_ms: int = 0
        self.call_count_threshold: int | None = None  # Fail after N calls

    def should_fail(self, call_count: int) -> bool:
        if self.call_count_threshold and call_count >= self.call_count_threshold:
            return True
        return any([
            self.http_error,
            self.connection_error,
            self.malformed_response,
        ])
```

**Rationale**:
- Composition allows fine-grained control without modifying existing mock classes
- Call count threshold supports fallback testing (Tiingo fails, Finnhub succeeds)
- Latency simulation supports timeout testing

**Alternatives Rejected**:
- Subclassing: Creates explosion of classes for each failure combination
- Inline test logic: High duplication, harder to maintain
- Monkey patching: Fragile, hard to debug

### RQ-002: What patterns exist for test oracle implementation?

**Decision**: Compute expected values from same synthetic seed

**Research Findings**:
- Constitution Section 7 requires: "assertions MUST compute expected outcomes from the same synthetic data"
- Existing `tests/fixtures/synthetic/` uses seeded random: `random.seed(hash(ticker))`
- Sentiment history endpoint already uses `random.seed(hash(ticker))` for deterministic output

**Solution**:
```python
class TestOracle:
    """Computes expected responses for test assertions."""

    def __init__(self, seed: int):
        self.seed = seed

    def expected_ohlc_response(
        self,
        ticker: str,
        start_date: date,
        end_date: date
    ) -> dict:
        """Compute expected OHLC response without calling endpoint."""
        # Use same generation logic as synthetic generators
        candles = generate_ohlc_data(
            seed=self.seed + hash(ticker),
            ticker=ticker,
            days=(end_date - start_date).days,
        )
        return {
            "ticker": ticker.upper(),
            "candles": [candle_to_dict(c) for c in candles],
            "count": len(candles),
            "start_date": str(candles[0].date),
            "end_date": str(candles[-1].date),
        }

    def expected_sentiment_response(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        source: str = "aggregated",
    ) -> dict:
        """Compute expected sentiment history response."""
        # Mirror the endpoint's deterministic generation
        random.seed(hash(ticker))
        # ... generate same way as endpoint
```

**Rationale**:
- Deterministic: Same inputs always produce same outputs
- Decoupled: Oracle doesn't depend on endpoint being correct
- Verifiable: Can manually check oracle outputs independently

### RQ-003: How to structure tests for 157 acceptance scenarios?

**Decision**: Parameterized tests grouped by user story

**Research Findings**:
- pytest supports `@pytest.mark.parametrize` for data-driven tests
- Existing tests in `tests/contract/` use parameterized tests effectively
- 157 scenarios across 7 user stories need organized structure

**Solution**:
```python
# tests/integration/ohlc/test_happy_path.py

@pytest.mark.parametrize("time_range,expected_days", [
    (TimeRange.ONE_WEEK, (5, 7)),
    (TimeRange.ONE_MONTH, (20, 23)),
    (TimeRange.THREE_MONTHS, (60, 66)),
    (TimeRange.SIX_MONTHS, (120, 132)),
    (TimeRange.ONE_YEAR, (250, 260)),
])
@pytest.mark.integration
@pytest.mark.ohlc
async def test_ohlc_time_ranges(
    client: TestClient,
    time_range: TimeRange,
    expected_days: tuple[int, int],
):
    """US1 Scenarios 2-6: Verify time range produces expected trading days."""
    response = client.get(
        "/api/v2/tickers/AAPL/ohlc",
        headers={"X-User-ID": "test-user"},
        params={"range": time_range.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert expected_days[0] <= data["count"] <= expected_days[1]
```

**File Organization**:
```
tests/integration/ohlc/
├── __init__.py
├── test_happy_path.py          # US1: 14 scenarios
├── test_error_resilience.py    # US3: 30 scenarios (OHLC portion)
├── test_boundary_values.py     # US4: 37 scenarios (OHLC portion)
├── test_data_consistency.py    # US5: 19 scenarios
└── test_authentication.py      # US6: 12 scenarios

tests/integration/sentiment_history/
├── __init__.py
├── test_happy_path.py          # US2: 16 scenarios
├── test_source_filtering.py    # US2 source scenarios
├── test_boundary_values.py     # US4: 15 scenarios (sentiment portion)
└── test_authentication.py      # US6: (shared with OHLC)

tests/e2e/
└── test_ohlc_sentiment_preprod.py  # US7: 14 scenarios
```

### RQ-004: How to handle E2E tests against preprod?

**Decision**: pytest marker with environment-based skip

**Research Findings**:
- Constitution Section 7: PREPROD runs E2E tests only, no AWS mocks
- Existing pattern in `tests/integration/test_*_preprod.py` files
- `pytest.ini` has `preprod` marker defined

**Solution**:
```python
# tests/e2e/test_ohlc_sentiment_preprod.py

import os
import pytest

PREPROD_BASE_URL = os.environ.get("PREPROD_API_URL")

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.preprod,
    pytest.mark.skipif(
        not PREPROD_BASE_URL,
        reason="PREPROD_API_URL not set - skipping preprod tests"
    ),
]

@pytest.fixture
def preprod_client():
    """HTTP client configured for preprod API."""
    return httpx.Client(
        base_url=PREPROD_BASE_URL,
        timeout=30.0,
    )

async def test_ohlc_real_data(preprod_client):
    """US7 Scenario 1: Real Tiingo/Finnhub data within 5 seconds."""
    start = time.monotonic()
    response = preprod_client.get(
        "/api/v2/tickers/AAPL/ohlc",
        headers={"X-User-ID": "e2e-test-user"},
    )
    elapsed = time.monotonic() - start

    assert response.status_code == 200
    assert elapsed < 5.0, f"Response took {elapsed:.2f}s, expected < 5s"
    data = response.json()
    assert len(data["candles"]) > 0
```

**Rationale**:
- Marker-based selection allows `pytest -m "not preprod"` for local runs
- Environment variable skip prevents failures when preprod not configured
- Separate file keeps preprod tests isolated

### RQ-005: What edge cases require special handling in OHLC data?

**Decision**: Implement validators with comprehensive edge case detection

**Research Findings**:
- OHLC constraint: high >= max(open, close) and low <= min(open, close)
- Real-world edge cases: doji candles (O=H=L=C), penny stocks ($0.0001), BRK.A ($600k+)
- Volume can be 0 (low liquidity) but not negative
- Dates must be trading days (exclude weekends/holidays for OHLC, include for sentiment)

**Solution**:
```python
class OHLCValidator:
    """Validates OHLC candle data against business rules."""

    @staticmethod
    def validate_candle(candle: dict) -> list[str]:
        """Return list of validation errors (empty if valid)."""
        errors = []

        # Required fields
        for field in ["date", "open", "high", "low", "close"]:
            if field not in candle:
                errors.append(f"Missing required field: {field}")

        if errors:
            return errors  # Can't validate further without required fields

        o, h, l, c = candle["open"], candle["high"], candle["low"], candle["close"]

        # Price relationships
        if h < l:
            errors.append(f"high ({h}) < low ({l})")
        if o > h or o < l:
            errors.append(f"open ({o}) outside high-low range ({l}-{h})")
        if c > h or c < l:
            errors.append(f"close ({c}) outside high-low range ({l}-{h})")

        # Price bounds
        if any(p <= 0 for p in [o, h, l, c]):
            errors.append("Prices must be positive")
        if any(math.isnan(p) or math.isinf(p) for p in [o, h, l, c]):
            errors.append("Prices cannot be NaN or Infinity")

        # Volume
        if "volume" in candle and candle["volume"] is not None:
            if candle["volume"] < 0:
                errors.append("Volume cannot be negative")

        return errors
```

## Summary

All research questions resolved. Ready for Phase 1 implementation:

| Question | Decision | Confidence |
|----------|----------|------------|
| RQ-001: Failure injection | FailureInjector composition | High |
| RQ-002: Test oracle | Compute from same seed | High |
| RQ-003: Test structure | Parameterized by user story | High |
| RQ-004: E2E preprod | Marker + env skip | High |
| RQ-005: Edge cases | OHLCValidator class | High |
