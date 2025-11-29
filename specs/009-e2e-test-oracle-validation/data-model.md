# Data Model: E2E Test Oracle Validation

**Feature**: 009-e2e-test-oracle-validation
**Date**: 2025-11-29
**Status**: Complete

## Overview

This feature enhances the test infrastructure, not the production data model. The data model describes the structures used by test fixtures, synthetic data generators, and the test oracle for computing expected values.

## Test Data Structures

### Extended TestScenario

Extends the existing `TestScenario` dataclass with sentiment oracle values:

```python
@dataclass
class TestScenario:
    """A complete test scenario with all generated data."""

    # Existing fields
    ticker: str
    seed: int
    candles: list[OHLCCandle]
    sentiment_series: list[SentimentData]
    news_articles: list[NewsArticle]
    expected_atr: float | None
    expected_atr_result: ATRResult | None
    expected_volatility_level: Literal["low", "medium", "high"] | None

    # NEW: Sentiment oracle values
    expected_sentiment_score: float  # Computed from production algorithm
    expected_sentiment_label: Literal["positive", "neutral", "negative"]
    expected_confidence: float  # 0.0-1.0
```

### SyntheticConfiguration

New dataclass for generated test configurations:

```python
@dataclass
class SyntheticConfiguration:
    """Generated test configuration for API tests."""

    config_id: str  # UUID prefixed with test_run_id
    name: str  # Generated name like "Test-Config-{seed_hash}"
    tickers: list[SyntheticTicker]
    created_at: datetime
    user_id: str  # Prefixed with test_run_id for isolation

@dataclass
class SyntheticTicker:
    """Generated ticker for test configuration."""

    symbol: str  # From realistic pool: AAPL, MSFT, GOOGL, etc.
    weight: float  # 0.1-1.0, normalized
```

### OracleExpectation

New dataclass for holding oracle-computed expected values:

```python
@dataclass
class OracleExpectation:
    """Expected values computed by the test oracle."""

    sentiment_score: float  # -1.0 to 1.0
    sentiment_label: Literal["positive", "neutral", "negative"]
    confidence: float  # 0.0 to 1.0
    volatility_level: Literal["low", "medium", "high"] | None
    atr_value: float | None

    def matches(
        self,
        actual_score: float,
        actual_label: str,
        tolerance: float = 0.01,
    ) -> bool:
        """Check if actual values match expected within tolerance."""
        return (
            abs(actual_score - self.sentiment_score) <= tolerance
            and actual_label == self.sentiment_label
        )
```

### FailureInjectionConfig

Configuration for failure mode testing:

```python
@dataclass
class FailureInjectionConfig:
    """Configuration for injecting failures in tests."""

    tiingo_fail_mode: bool = False
    finnhub_fail_mode: bool = False
    sendgrid_rate_limit: bool = False
    dynamodb_throttle: bool = False

    # Specific failure scenarios
    malformed_response: bool = False  # Return invalid JSON
    timeout_seconds: float | None = None  # Simulate timeout
    error_code: int | None = None  # Return specific HTTP error
```

### TestMetrics

For tracking test quality metrics:

```python
@dataclass
class TestMetrics:
    """Metrics collected during test suite execution."""

    total_tests: int
    passed: int
    failed: int
    skipped: int
    skip_rate: float  # skipped / total
    oracle_comparisons: int  # Tests using oracle validation
    synthetic_data_usage: int  # Tests using synthetic data
    failure_injection_tests: int  # Tests exercising error paths

    @property
    def passes_quality_gate(self) -> bool:
        """Check if metrics meet quality criteria."""
        return self.skip_rate < 0.15  # <15% skip rate
```

## Generator Extensions

### ConfigGenerator (New)

```python
class ConfigGenerator:
    """Generates synthetic configurations for testing."""

    TICKER_POOL = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]

    def __init__(self, seed: int):
        self._random = random.Random(seed)

    def generate_config(
        self,
        test_run_id: str,
        ticker_count: int = 3,
    ) -> SyntheticConfiguration:
        """Generate a synthetic configuration."""
        ...

    def generate_name(self) -> str:
        """Generate a unique config name."""
        ...

    def generate_tickers(self, count: int) -> list[SyntheticTicker]:
        """Generate ticker list with weights."""
        ...
```

### SentimentOracleExtension

Extension to existing TestOracle for API sentiment comparison:

```python
class SentimentOracleExtension:
    """Extensions to TestOracle for API sentiment validation."""

    def compute_api_sentiment(
        self,
        news_articles: list[NewsArticle],
        weights: dict[str, float] | None = None,
    ) -> OracleExpectation:
        """Compute expected sentiment score using production algorithm.

        This method mirrors the production sentiment calculation to
        provide expected values for oracle comparison tests.
        """
        ...

    def validate_response(
        self,
        actual_response: dict,
        expected: OracleExpectation,
        tolerance: float = 0.01,
    ) -> tuple[bool, str]:
        """Validate API response against oracle expectation.

        Returns:
            (is_valid, error_message)
        """
        ...
```

## Skip Message Format

Standardized format for actionable skip messages:

```python
@dataclass
class SkipInfo:
    """Information for test skip messages."""

    condition: str  # What caused the skip
    reason: str  # Why it cannot run
    remediation: str  # How to make it run

    def format_message(self) -> str:
        """Format as pytest skip message."""
        return (
            f"SKIPPED: {self.condition}\n"
            f"Reason: {self.reason}\n"
            f"To run: {self.remediation}"
        )

# Example usage:
skip_info = SkipInfo(
    condition="Rate limit threshold not reached after 100 requests",
    reason="Preprod rate limit is higher than test threshold",
    remediation="Set RATE_LIMIT_THRESHOLD=10 or use mock environment",
)
pytest.skip(skip_info.format_message())
```

## Relationships

```
TestScenario
├── OracleExpectation (computed from synthetic data)
├── SyntheticConfiguration (for API tests)
└── FailureInjectionConfig (for error path tests)

ConfigGenerator
├── generates → SyntheticConfiguration
└── uses → TICKER_POOL

SentimentOracleExtension
├── extends → SyntheticTestOracle
└── produces → OracleExpectation

TestMetrics
├── aggregates → test results
└── validates → quality gates
```

## Constraints

| Constraint | Value | Rationale |
|------------|-------|-----------|
| Sentiment score range | -1.0 to 1.0 | Normalized score |
| Confidence range | 0.0 to 1.0 | Probability |
| Oracle tolerance | ±0.01 | Floating point comparison |
| Skip rate threshold | <15% | Quality gate |
| Max tickers per config | 5 | API limit |
| Test run ID format | `e2e-{hex8}` | Isolation |

## Migration Notes

No production data migration required. This feature only affects test infrastructure:

1. **Existing tests**: Will be refactored to use oracle validation
2. **Test fixtures**: Extended with new dataclasses
3. **Generator imports**: May need to update imports in test files
4. **Backward compatibility**: Legacy fixtures remain available
