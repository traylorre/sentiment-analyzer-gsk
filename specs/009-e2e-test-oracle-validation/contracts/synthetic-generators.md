# Contract: Synthetic Data Generators

**Feature**: 009-e2e-test-oracle-validation
**Date**: 2025-11-29
**Status**: Draft

## Overview

This contract defines the interface for synthetic data generators used in E2E tests to produce deterministic, reproducible test data.

## Existing Generators

### TickerGenerator

Located: `tests/fixtures/synthetic/ticker_generator.py`

```python
class TickerGenerator:
    """Generates synthetic OHLC candle data."""

    def __init__(self, seed: int = 42) -> None: ...

    def reset(self, seed: int) -> None:
        """Reset generator with new seed."""

    def generate_candles(
        self,
        ticker: str,
        days: int,
        end_date: datetime | None = None,
    ) -> list[OHLCCandle]:
        """Generate OHLC candle data for ticker."""
```

### SentimentGenerator

Located: `tests/fixtures/synthetic/sentiment_generator.py`

```python
class SentimentGenerator:
    """Generates synthetic sentiment time series."""

    def __init__(self, seed: int = 42) -> None: ...

    def reset(self, seed: int) -> None:
        """Reset generator with new seed."""

    def generate_sentiment_series(
        self,
        ticker: str,
        days: int,
        end_date: datetime | None = None,
    ) -> list[SentimentData]:
        """Generate sentiment data series for ticker."""
```

### NewsGenerator

Located: `tests/fixtures/synthetic/news_generator.py`

```python
class NewsGenerator:
    """Generates synthetic news articles."""

    def __init__(self, seed: int = 42) -> None: ...

    def reset(self, seed: int) -> None:
        """Reset generator with new seed."""

    def generate_articles(
        self,
        tickers: list[str],
        count: int,
        days_back: int = 7,
    ) -> list[NewsArticle]:
        """Generate news articles for tickers."""

    def _select_sentiment(self) -> Literal["positive", "negative", "neutral"]:
        """Internal: Select sentiment category."""
```

## New Generator: ConfigGenerator

Located: `tests/fixtures/synthetic/config_generator.py` (to be created)

```python
class ConfigGenerator:
    """Generates synthetic configurations for API tests."""

    TICKER_POOL: ClassVar[list[str]] = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        "JPM", "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS",
    ]

    def __init__(self, seed: int = 42) -> None:
        """Initialize with random seed."""

    def reset(self, seed: int) -> None:
        """Reset generator with new seed."""

    def generate_config(
        self,
        test_run_id: str,
        ticker_count: int = 3,
    ) -> SyntheticConfiguration:
        """Generate a synthetic configuration.

        Args:
            test_run_id: Unique test run identifier for isolation
            ticker_count: Number of tickers (1-5)

        Returns:
            SyntheticConfiguration with unique name and tickers
        """

    def generate_name(self, prefix: str = "Test-Config") -> str:
        """Generate unique configuration name.

        Format: {prefix}-{random_hex}
        Example: "Test-Config-a1b2c3d4"
        """

    def generate_tickers(self, count: int) -> list[SyntheticTicker]:
        """Generate list of tickers with weights.

        Weights are normalized to sum to 1.0.
        Tickers are sampled without replacement from TICKER_POOL.
        """

    def generate_user_id(self, test_run_id: str) -> str:
        """Generate test user ID.

        Format: {test_run_id}-user-{random_hex}
        """
```

### SyntheticConfiguration

```python
@dataclass
class SyntheticConfiguration:
    """Generated test configuration."""

    config_id: str
    name: str
    tickers: list[SyntheticTicker]
    created_at: datetime
    user_id: str

    def to_api_payload(self) -> dict:
        """Convert to API request payload."""
        return {
            "name": self.name,
            "tickers": [t.to_dict() for t in self.tickers],
        }

@dataclass
class SyntheticTicker:
    """Generated ticker with weight."""

    symbol: str
    weight: float

    def to_dict(self) -> dict:
        """Convert to dict for API payload."""
        return {"symbol": self.symbol, "weight": self.weight}
```

## Factory Functions

All generators have factory functions for consistent instantiation:

```python
def create_ticker_generator(seed: int = 42) -> TickerGenerator:
    """Create ticker generator with seed."""

def create_sentiment_generator(seed: int = 42) -> SentimentGenerator:
    """Create sentiment generator with seed."""

def create_news_generator(seed: int = 42) -> NewsGenerator:
    """Create news generator with seed."""

def create_config_generator(seed: int = 42) -> ConfigGenerator:
    """Create config generator with seed."""
```

## Determinism Contract

### Requirements

1. **Same seed = Same output**: Given identical seeds and parameters, generators MUST produce identical output
2. **Independent seeds**: Different seeds MUST produce different output
3. **Isolation**: Generator state MUST NOT leak between tests
4. **Reset capability**: `reset(seed)` MUST restore generator to initial state for that seed

### Verification Test

```python
def test_generator_determinism():
    """Verify generator produces identical output for same seed."""
    gen1 = create_config_generator(seed=12345)
    gen2 = create_config_generator(seed=12345)

    config1 = gen1.generate_config("test-run-1")
    config2 = gen2.generate_config("test-run-1")

    assert config1.name == config2.name
    assert config1.tickers == config2.tickers
```

## Integration with Test Fixtures

### conftest.py Pattern

```python
@pytest.fixture
def config_generator(synthetic_seed: int) -> ConfigGenerator:
    """Provide config generator seeded from test run."""
    return create_config_generator(seed=synthetic_seed)

@pytest.fixture
def synthetic_config(
    config_generator: ConfigGenerator,
    test_run_id: str,
) -> SyntheticConfiguration:
    """Provide synthetic configuration for test."""
    return config_generator.generate_config(test_run_id)
```

## Data Ranges

| Generator | Field | Range | Distribution |
|-----------|-------|-------|--------------|
| TickerGenerator | open/high/low/close | 10.0-500.0 | Log-normal |
| TickerGenerator | volume | 1M-100M | Log-normal |
| SentimentGenerator | sentiment_score | -1.0 to 1.0 | Normal |
| NewsGenerator | sentiment | pos/neg/neutral | 40%/30%/30% |
| ConfigGenerator | ticker_count | 1-5 | Uniform |
| ConfigGenerator | weight | 0.1-1.0 | Uniform, normalized |

## Error Handling

| Scenario | Behavior |
|----------|----------|
| ticker_count > 5 | Raise `ValueError("max 5 tickers")` |
| ticker_count < 1 | Raise `ValueError("min 1 ticker")` |
| empty ticker pool | Raise `ValueError("ticker pool exhausted")` |
| invalid seed type | Raise `TypeError` |
