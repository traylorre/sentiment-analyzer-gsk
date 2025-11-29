# Synthetic Tiingo API Handlers
#
# Generates deterministic test data for Tiingo API endpoints.
# See contracts/synthetic-tiingo.md for response format specification.

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class TiingoNewsArticle:
    """Represents a synthetic Tiingo news article."""

    id: str
    title: str
    description: str
    published_date: datetime
    crawl_date: datetime
    source: str
    url: str
    tickers: list[str]
    tags: list[str]
    expected_sentiment: float  # Test oracle value

    def to_dict(self) -> dict:
        """Convert to Tiingo API response format."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "publishedDate": self.published_date.isoformat().replace("+00:00", "Z"),
            "crawlDate": self.crawl_date.isoformat().replace("+00:00", "Z"),
            "source": self.source,
            "url": self.url,
            "tickers": self.tickers,
            "tags": self.tags,
            "_synthetic": True,
            "_expected_sentiment": self.expected_sentiment,
        }


@dataclass
class TiingoOHLCData:
    """Represents a synthetic Tiingo OHLC price data point."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    div_cash: float = 0.0
    split_factor: float = 1.0

    def to_dict(self) -> dict:
        """Convert to Tiingo API response format."""
        return {
            "date": self.date.isoformat().replace("+00:00", "Z"),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "adjOpen": self.open,
            "adjHigh": self.high,
            "adjLow": self.low,
            "adjClose": self.close,
            "adjVolume": self.volume,
            "divCash": self.div_cash,
            "splitFactor": self.split_factor,
        }


def generate_tiingo_news(
    seed: int,
    ticker: str,
    count: int = 5,
    start_time: datetime | None = None,
) -> list[dict]:
    """Generate synthetic news articles for a ticker.

    Args:
        seed: Random seed for deterministic generation
        ticker: Stock ticker symbol
        count: Number of articles to generate
        start_time: Base time for article timestamps (default: now)

    Returns:
        List of articles in Tiingo API format
    """
    rng = random.Random(seed)
    base_time = start_time or datetime.now(UTC)

    articles = []
    for i in range(count):
        # Generate deterministic sentiment based on seed and ticker
        sentiment = rng.random() * 2 - 1  # Range: -1.0 to 1.0

        published = base_time - timedelta(hours=i)
        crawled = published + timedelta(minutes=5)

        article = TiingoNewsArticle(
            id=f"test-{seed}-{ticker}-{i}",
            title=f"Test article about {ticker} #{i}",
            description=f"Synthetic news article for E2E testing. Generated with seed {seed}.",
            published_date=published,
            crawl_date=crawled,
            source="test-source",
            url=f"https://test.example.com/articles/test-{seed}-{ticker}-{i}",
            tickers=[ticker],
            tags=["test", "synthetic"],
            expected_sentiment=round(sentiment, 2),
        )
        articles.append(article.to_dict())

    return articles


def generate_tiingo_ohlc(
    seed: int,
    ticker: str,
    days: int = 14,
    start_date: datetime | None = None,
) -> list[dict]:
    """Generate synthetic OHLC price data for ATR calculation.

    Args:
        seed: Random seed for deterministic generation
        ticker: Stock ticker symbol (used for base price variation)
        days: Number of days of data (default: 14 for ATR-14)
        start_date: Most recent date (default: today)

    Returns:
        List of OHLC data in Tiingo API format, newest first
    """
    rng = random.Random(seed)
    base_date = start_date or datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Base price varies by seed
    base_price = 100 + (seed % 100)
    current_price = base_price

    data = []
    for i in range(days):
        date = base_date - timedelta(days=i)

        # Daily volatility: ±2%
        daily_change = current_price * (rng.random() * 0.04 - 0.02)
        open_price = current_price
        close_price = current_price + daily_change

        # High/low based on volatility
        intraday_range = abs(daily_change) + current_price * rng.random() * 0.01
        high = max(open_price, close_price) + intraday_range / 2
        low = min(open_price, close_price) - intraday_range / 2

        volume = 1000000 + (seed * 1000) + rng.randint(0, 100000)

        ohlc = TiingoOHLCData(
            date=date,
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close_price, 2),
            volume=volume,
        )
        data.append(ohlc.to_dict())

        # Next day starts at previous close
        current_price = close_price

    return data


class SyntheticTiingoHandler:
    """Handler for synthetic Tiingo API responses.

    Supports configurable error modes for testing circuit breaker
    and rate limiting behaviors.
    """

    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.error_mode = False
        self.rate_limit_mode = False
        self._request_count = 0

    def set_error_mode(self, enabled: bool) -> None:
        """Configure handler to return 503 errors."""
        self.error_mode = enabled

    def set_rate_limit_mode(self, enabled: bool) -> None:
        """Configure handler to return 429 rate limits."""
        self.rate_limit_mode = enabled

    def reset(self) -> None:
        """Reset handler state."""
        self.error_mode = False
        self.rate_limit_mode = False
        self._request_count = 0

    def get_news_response(self, ticker: str, count: int = 5) -> tuple[int, dict | list]:
        """Generate news response for a ticker.

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        if self.error_mode:
            return (503, {"error": "Service temporarily unavailable"})

        if self.rate_limit_mode:
            return (429, {"error": "Rate limit exceeded", "retryAfter": 60})

        if ticker.startswith("INVALID"):
            return (400, {"error": f"Unknown ticker: {ticker}"})

        articles = generate_tiingo_news(self.seed, ticker, count)
        return (200, articles)

    def get_ohlc_response(self, ticker: str, days: int = 14) -> tuple[int, dict | list]:
        """Generate OHLC response for a ticker.

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        if self.error_mode:
            return (503, {"error": "Service temporarily unavailable"})

        if self.rate_limit_mode:
            return (429, {"error": "Rate limit exceeded", "retryAfter": 60})

        if ticker.startswith("INVALID"):
            return (400, {"error": f"Unknown ticker: {ticker}"})

        ohlc_data = generate_tiingo_ohlc(self.seed, ticker, days)
        return (200, ohlc_data)

    @property
    def request_count(self) -> int:
        """Number of requests handled."""
        return self._request_count
