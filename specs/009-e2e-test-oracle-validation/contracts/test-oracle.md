# Contract: Test Oracle Interface

**Feature**: 009-e2e-test-oracle-validation
**Date**: 2025-11-29
**Status**: Draft

## Overview

This contract defines the interface for the Test Oracle component that computes expected values from synthetic data for E2E test assertions.

## Interface Definition

### SyntheticTestOracle

```python
class SyntheticTestOracle:
    """Computes expected outcomes from synthetic data."""

    def __init__(self, seed: int = 42) -> None:
        """Initialize oracle with random seed."""

    # ATR/Volatility Methods (Existing)
    def compute_expected_atr(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> float | None:
        """Compute expected ATR value."""

    def compute_expected_atr_result(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> ATRResult | None:
        """Compute expected ATRResult with volatility level."""

    def compute_expected_volatility_level(
        self,
        ticker: str,
        days: int = 30,
        period: int = 14,
        end_date: datetime | None = None,
    ) -> Literal["low", "medium", "high"] | None:
        """Compute expected volatility classification."""

    # Sentiment Methods (Existing)
    def compute_expected_avg_sentiment(
        self,
        ticker: str,
        days: int = 30,
        end_date: datetime | None = None,
    ) -> float:
        """Compute expected average sentiment score."""

    def compute_expected_sentiment_trend(
        self,
        ticker: str,
        days: int = 14,
        end_date: datetime | None = None,
    ) -> Literal["improving", "declining", "stable"]:
        """Compute expected sentiment trend classification."""

    # NEW: API Sentiment Methods
    def compute_expected_api_sentiment(
        self,
        config: SyntheticConfiguration,
        news_articles: list[NewsArticle],
    ) -> OracleExpectation:
        """Compute expected sentiment as returned by API.

        Uses the same weighted averaging algorithm as the production
        sentiment calculation pipeline.

        Args:
            config: Configuration with ticker weights
            news_articles: News articles to compute sentiment from

        Returns:
            OracleExpectation with score, label, and confidence
        """

    def validate_api_response(
        self,
        response: dict,
        expected: OracleExpectation,
        tolerance: float = 0.01,
    ) -> ValidationResult:
        """Validate API response against oracle expectation.

        Args:
            response: Parsed JSON response from API
            expected: Oracle-computed expectation
            tolerance: Maximum allowed difference for sentiment score

        Returns:
            ValidationResult with is_valid and error details
        """

    # Scenario Generation (Existing, Extended)
    def generate_test_scenario(
        self,
        ticker: str,
        days: int = 30,
        news_count: int = 15,
        end_date: datetime | None = None,
    ) -> TestScenario:
        """Generate complete test scenario with all expected values."""
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    """Result of oracle validation."""

    is_valid: bool
    expected_score: float
    actual_score: float | None
    expected_label: str
    actual_label: str | None
    error_message: str | None = None

    def raise_if_invalid(self) -> None:
        """Raise AssertionError if validation failed."""
        if not self.is_valid:
            raise AssertionError(self.error_message)
```

## Usage Contract

### Pre-conditions

1. Oracle MUST be initialized with the same seed as synthetic data generators
2. Synthetic data MUST be generated before calling oracle computation methods
3. News articles MUST contain valid sentiment scores in range [-1.0, 1.0]

### Post-conditions

1. `compute_expected_api_sentiment` returns a fully populated `OracleExpectation`
2. `validate_api_response` returns `is_valid=True` if actual matches expected within tolerance
3. Sentiment scores are always in range [-1.0, 1.0]
4. Confidence scores are always in range [0.0, 1.0]

### Invariants

1. Same seed + same inputs = same outputs (deterministic)
2. Oracle uses production-equivalent algorithms
3. Tolerance of ±0.01 accounts for floating point precision

## Test Patterns

### Oracle Comparison Test

```python
@pytest.mark.preprod
async def test_sentiment_oracle_comparison(
    api_client: PreprodAPIClient,
    test_oracle: SyntheticTestOracle,
    synthetic_seed: int,
):
    """Verify API sentiment matches oracle-computed expectation."""
    # Generate synthetic data
    config = generate_synthetic_config(synthetic_seed)
    news = generate_synthetic_news(synthetic_seed)

    # Compute oracle expectation
    expected = test_oracle.compute_expected_api_sentiment(config, news)

    # Call API
    response = await api_client.get_sentiment(config.config_id)

    # Validate against oracle
    result = test_oracle.validate_api_response(response.json(), expected)
    result.raise_if_invalid()
```

### Tolerance-Based Assertion

```python
def test_sentiment_within_tolerance(actual: float, expected: float):
    """Assert sentiment score within ±0.01 tolerance."""
    assert abs(actual - expected) <= 0.01, (
        f"Sentiment {actual} differs from oracle {expected} by "
        f"{abs(actual - expected):.4f} (tolerance: 0.01)"
    )
```

## Error Handling

| Scenario | Expected Behavior |
|----------|-------------------|
| Oracle computation fails | Raise `OracleComputationError` |
| API response missing sentiment | `ValidationResult.is_valid=False`, error_message set |
| Sentiment outside range | `ValidationResult.is_valid=False`, error_message set |
| Tolerance exceeded | `ValidationResult.is_valid=False`, shows actual vs expected |

## Versioning

This contract is versioned with the feature specification. Changes require:

1. Update this contract document
2. Update implementation
3. Update all tests using oracle
4. Document in changelog
