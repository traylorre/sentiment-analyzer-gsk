# Data Model: OHLC & Sentiment History E2E Test Suite

**Feature**: 012-ohlc-sentiment-e2e-tests
**Date**: 2025-12-01

## Overview

This document defines the test infrastructure entities used to implement the comprehensive test suite. These are NOT production entities - they are test-specific classes that facilitate failure injection, test data generation, and validation.

## Test Infrastructure Entities

### FailureInjector

Configures mock adapters with specific failure modes for error resilience testing.

```python
@dataclass
class FailureInjector:
    """Configurable failure injection for mock adapters.

    Attributes:
        http_error: HTTP status code to return (400, 401, 404, 429, 500, 502, 503, 504)
        connection_error: Type of connection error ("timeout", "refused", "dns")
        malformed_response: Type of malformed response ("invalid_json", "empty", "truncated", "html")
        missing_fields: List of field names to omit from response
        invalid_values: Dict mapping field names to invalid values (None, NaN, Infinity, negative)
        latency_ms: Simulated response latency in milliseconds
        call_count_threshold: Fail after N successful calls (for fallback testing)
        retry_after_seconds: Value for Retry-After header when http_error=429

    Usage:
        injector = FailureInjector(http_error=500)
        mock_tiingo = MockTiingoAdapter(failure_injector=injector)
    """

    http_error: int | None = None
    connection_error: str | None = None
    malformed_response: str | None = None
    missing_fields: list[str] = field(default_factory=list)
    invalid_values: dict[str, Any] = field(default_factory=dict)
    latency_ms: int = 0
    call_count_threshold: int | None = None
    retry_after_seconds: int = 60
```

**Validation Rules**:
- `http_error` must be a valid HTTP status code (400-599)
- `connection_error` must be one of: "timeout", "refused", "dns"
- `malformed_response` must be one of: "invalid_json", "empty", "truncated", "html", "extra_fields"
- `latency_ms` must be non-negative
- `call_count_threshold` must be positive if set

**State Transitions**: None (immutable configuration)

### TestOracle

Computes expected responses from synthetic input for assertion comparison.

```python
class TestOracle:
    """Computes expected API responses for test assertions.

    The oracle uses the same deterministic algorithms as the synthetic
    data generators to predict what responses should look like.

    Attributes:
        seed: Base random seed for deterministic generation
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def expected_ohlc_response(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        source: str = "tiingo",
    ) -> OHLCResponse:
        """Compute expected OHLC response."""

    def expected_sentiment_response(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        source: str = "aggregated",
    ) -> SentimentHistoryResponse:
        """Compute expected sentiment history response."""

    def expected_trading_days(
        self,
        start_date: date,
        end_date: date,
    ) -> int:
        """Compute expected number of trading days in range."""
```

**Relationships**:
- Uses `ticker_generator.py` for OHLC data generation
- Uses `sentiment_generator.py` for sentiment data generation
- Mirrors endpoint logic for deterministic comparison

### OHLCValidator

Validates OHLC response structure and business rule compliance.

```python
@dataclass
class ValidationError:
    """Single validation error with context."""
    field: str
    message: str
    value: Any = None

class OHLCValidator:
    """Validates OHLC candle data against business rules.

    Rules enforced:
    - Required fields present: date, open, high, low, close
    - Price relationships: high >= max(open, close), low <= min(open, close)
    - Price bounds: all prices > 0, no NaN/Infinity
    - Volume bounds: volume >= 0 if present
    - Date ordering: candles sorted by date ascending
    - Count consistency: count field matches array length
    """

    def validate_candle(self, candle: dict) -> list[ValidationError]:
        """Validate single candle, return list of errors."""

    def validate_response(self, response: dict) -> list[ValidationError]:
        """Validate full OHLC response, return list of errors."""

    def assert_valid(self, response: dict) -> None:
        """Assert response is valid, raise AssertionError with details if not."""
```

**Validation Rules**:
| Rule | Field | Condition |
|------|-------|-----------|
| OHLC-001 | high | high >= low |
| OHLC-002 | open | low <= open <= high |
| OHLC-003 | close | low <= close <= high |
| OHLC-004 | prices | All prices > 0 |
| OHLC-005 | prices | No NaN or Infinity |
| OHLC-006 | volume | volume >= 0 (if present) |
| OHLC-007 | date | Valid ISO date format |
| OHLC-008 | candles | Sorted by date ascending |
| OHLC-009 | count | count == len(candles) |
| OHLC-010 | start_date | start_date == candles[0].date |
| OHLC-011 | end_date | end_date == candles[-1].date |

### SentimentValidator

Validates sentiment history response structure and business rule compliance.

```python
class SentimentValidator:
    """Validates sentiment history data against business rules.

    Rules enforced:
    - Required fields present: date, score, source
    - Score bounds: -1.0 <= score <= 1.0
    - Confidence bounds: 0.0 <= confidence <= 1.0 (if present)
    - Label consistency: label matches score thresholds
    - Date ordering: history sorted by date ascending
    - Count consistency: count field matches array length
    """

    LABEL_THRESHOLDS = {
        "positive": (0.33, 1.0),
        "neutral": (-0.33, 0.33),
        "negative": (-1.0, -0.33),
    }

    def validate_point(self, point: dict) -> list[ValidationError]:
        """Validate single sentiment point, return list of errors."""

    def validate_response(self, response: dict) -> list[ValidationError]:
        """Validate full sentiment response, return list of errors."""

    def assert_valid(self, response: dict) -> None:
        """Assert response is valid, raise AssertionError with details if not."""
```

**Validation Rules**:
| Rule | Field | Condition |
|------|-------|-----------|
| SENT-001 | score | -1.0 <= score <= 1.0 |
| SENT-002 | confidence | 0.0 <= confidence <= 1.0 |
| SENT-003 | label | "positive" if score >= 0.33 |
| SENT-004 | label | "negative" if score <= -0.33 |
| SENT-005 | label | "neutral" if -0.33 < score < 0.33 |
| SENT-006 | history | Sorted by date ascending |
| SENT-007 | count | count == len(history) |
| SENT-008 | source | source matches requested source |

### EdgeCaseGenerator

Generates specific edge case test data for boundary testing.

```python
class EdgeCaseGenerator:
    """Generates edge case test data for boundary testing.

    Categories:
    - Date boundaries: single day, adjacent days, far past, far future
    - Ticker boundaries: 1 char, 5 chars, 6 chars, invalid chars
    - Price boundaries: doji, penny stock, large cap, zero, negative
    - Score boundaries: exactly -1, 0, 1, threshold boundaries (±0.33)
    """

    def ohlc_doji(self, price: float = 100.0) -> dict:
        """Generate doji candle (O=H=L=C)."""

    def ohlc_penny_stock(self) -> dict:
        """Generate penny stock candle ($0.0001)."""

    def ohlc_large_cap(self) -> dict:
        """Generate large cap candle ($600,000+)."""

    def ohlc_invalid_relationship(self, issue: str) -> dict:
        """Generate candle with invalid O/H/L/C relationship."""

    def sentiment_at_threshold(self, threshold: float) -> dict:
        """Generate sentiment point at exact threshold."""

    def sentiment_near_threshold(self, threshold: float, delta: float) -> dict:
        """Generate sentiment point near threshold."""
```

## Entity Relationships

```
┌─────────────────┐
│ FailureInjector │
└────────┬────────┘
         │ configures
         ▼
┌─────────────────┐     ┌─────────────────┐
│ MockTiingoAdapter│     │MockFinnhubAdapter│
└────────┬────────┘     └────────┬────────┘
         │ generates              │ generates
         ▼                        ▼
┌─────────────────┐     ┌─────────────────┐
│   Test Data     │     │   Test Data     │
└────────┬────────┘     └────────┬────────┘
         │                        │
         └──────────┬─────────────┘
                    │ validated by
                    ▼
         ┌─────────────────┐
         │  TestOracle     │
         │  OHLCValidator  │
         │SentimentValidator│
         └─────────────────┘
```

## Fixture Composition

```python
# conftest.py additions

@pytest.fixture
def failure_injector():
    """Default (no failure) injector."""
    return FailureInjector()

@pytest.fixture
def tiingo_500_error():
    """Tiingo returns HTTP 500."""
    return FailureInjector(http_error=500)

@pytest.fixture
def tiingo_timeout():
    """Tiingo connection timeout."""
    return FailureInjector(connection_error="timeout")

@pytest.fixture
def tiingo_malformed_json():
    """Tiingo returns invalid JSON."""
    return FailureInjector(malformed_response="invalid_json")

@pytest.fixture
def mock_tiingo(failure_injector):
    """Mock Tiingo adapter with optional failure injection."""
    return MockTiingoAdapter(failure_injector=failure_injector)

@pytest.fixture
def mock_finnhub(failure_injector):
    """Mock Finnhub adapter with optional failure injection."""
    return MockFinnhubAdapter(failure_injector=failure_injector)

@pytest.fixture
def test_oracle():
    """Test oracle for computing expected responses."""
    return TestOracle(seed=42)

@pytest.fixture
def ohlc_validator():
    """OHLC response validator."""
    return OHLCValidator()

@pytest.fixture
def sentiment_validator():
    """Sentiment response validator."""
    return SentimentValidator()
```
