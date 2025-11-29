# Synthetic Finnhub API Handlers
#
# Generates deterministic test data for Finnhub API endpoints.
# See contracts/synthetic-finnhub.md for response format specification.

import random
import time
from dataclasses import dataclass


@dataclass
class FinnhubSentiment:
    """Represents synthetic Finnhub sentiment data."""

    symbol: str
    bullish_percent: float
    bearish_percent: float
    company_news_score: float
    sector_average_bullish: float
    sector_average_news_score: float
    articles_in_last_week: int
    weekly_average: float
    buzz: float

    def to_dict(self) -> dict:
        """Convert to Finnhub API response format."""
        return {
            "buzz": {
                "articlesInLastWeek": self.articles_in_last_week,
                "weeklyAverage": self.weekly_average,
                "buzz": self.buzz,
            },
            "companyNewsScore": self.company_news_score,
            "sectorAverageBullishPercent": self.sector_average_bullish,
            "sectorAverageNewsScore": self.sector_average_news_score,
            "sentiment": {
                "bearishPercent": self.bearish_percent,
                "bullishPercent": self.bullish_percent,
            },
            "symbol": self.symbol,
        }


@dataclass
class FinnhubQuote:
    """Represents synthetic Finnhub quote data."""

    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    previous_close: float
    timestamp: int

    def to_dict(self) -> dict:
        """Convert to Finnhub API response format."""
        return {
            "c": self.current,
            "d": self.change,
            "dp": self.percent_change,
            "h": self.high,
            "l": self.low,
            "o": self.open,
            "pc": self.previous_close,
            "t": self.timestamp,
        }


@dataclass
class FinnhubMarketStatus:
    """Represents synthetic Finnhub market status."""

    exchange: str
    holiday: str | None
    is_open: bool
    session: str
    timestamp: int
    timezone: str

    def to_dict(self) -> dict:
        """Convert to Finnhub API response format."""
        return {
            "exchange": self.exchange,
            "holiday": self.holiday,
            "isOpen": self.is_open,
            "session": self.session,
            "t": self.timestamp,
            "timezone": self.timezone,
        }


def generate_finnhub_sentiment(seed: int, symbol: str) -> dict:
    """Generate synthetic sentiment data for a symbol.

    Args:
        seed: Random seed for deterministic generation
        symbol: Stock symbol

    Returns:
        Sentiment data in Finnhub API format
    """
    rng = random.Random(seed + hash(symbol))

    # bullishPercent: 0.5 + (seed % 50) / 100 (range: 0.5-1.0)
    bullish_percent = 0.5 + (seed % 50) / 100
    bearish_percent = 1.0 - bullish_percent

    articles_in_last_week = 10 + (seed % 20)

    sentiment = FinnhubSentiment(
        symbol=symbol,
        bullish_percent=round(bullish_percent, 2),
        bearish_percent=round(bearish_percent, 2),
        company_news_score=round((bullish_percent + (1 - bearish_percent)) / 2, 2),
        sector_average_bullish=round(0.55 + rng.random() * 0.1, 2),
        sector_average_news_score=round(0.45 + rng.random() * 0.1, 2),
        articles_in_last_week=articles_in_last_week,
        weekly_average=round(articles_in_last_week * 0.8, 1),
        buzz=round(articles_in_last_week / (articles_in_last_week * 0.8), 1),
    )

    return sentiment.to_dict()


def generate_finnhub_quote(seed: int, symbol: str) -> dict:
    """Generate synthetic quote data for a symbol.

    Args:
        seed: Random seed for deterministic generation
        symbol: Stock symbol

    Returns:
        Quote data in Finnhub API format
    """
    rng = random.Random(seed + hash(symbol))

    # Base price varies by seed
    base_price = 100 + (seed % 100)
    previous_close = base_price
    change = rng.random() * 4 - 2  # ±2%
    current = round(previous_close + change, 2)

    quote = FinnhubQuote(
        current=current,
        change=round(change, 2),
        percent_change=round(change / previous_close * 100, 2),
        high=round(max(current, previous_close) + rng.random() * 2, 2),
        low=round(min(current, previous_close) - rng.random() * 2, 2),
        open=round(previous_close + rng.random() - 0.5, 2),
        previous_close=round(previous_close, 2),
        timestamp=int(time.time()),
    )

    return quote.to_dict()


class SyntheticFinnhubHandler:
    """Handler for synthetic Finnhub API responses.

    Supports configurable market status and error modes.
    """

    def __init__(self, seed: int = 12345):
        self.seed = seed
        self.market_status = "open"  # "open", "closed", "holiday"
        self.holiday_name: str | None = None
        self.rate_limit_mode = False
        self._request_count = 0

    def set_market_status(self, status: str, holiday: str | None = None) -> None:
        """Configure market status for testing.

        Args:
            status: One of "open", "closed", "holiday"
            holiday: Holiday name if status is "holiday"
        """
        self.market_status = status
        self.holiday_name = holiday

    def set_rate_limit_mode(self, enabled: bool) -> None:
        """Configure handler to return 429 rate limits."""
        self.rate_limit_mode = enabled

    def reset(self) -> None:
        """Reset handler state."""
        self.market_status = "open"
        self.holiday_name = None
        self.rate_limit_mode = False
        self._request_count = 0

    def get_sentiment_response(self, symbol: str) -> tuple[int, dict]:
        """Generate sentiment response for a symbol.

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        if self.rate_limit_mode:
            return (429, {"error": "API limit reached. Please try again later."})

        # Invalid symbols return 200 with null sentiment (Finnhub behavior)
        if symbol.startswith("INVALID"):
            return (
                200,
                {
                    "buzz": None,
                    "companyNewsScore": None,
                    "sentiment": None,
                    "symbol": symbol,
                },
            )

        sentiment = generate_finnhub_sentiment(self.seed, symbol)
        return (200, sentiment)

    def get_quote_response(self, symbol: str) -> tuple[int, dict]:
        """Generate quote response for a symbol.

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        if self.rate_limit_mode:
            return (429, {"error": "API limit reached. Please try again later."})

        quote = generate_finnhub_quote(self.seed, symbol)
        return (200, quote)

    def get_market_status_response(self) -> tuple[int, dict]:
        """Generate market status response.

        Returns:
            Tuple of (status_code, response_body)
        """
        self._request_count += 1

        status = FinnhubMarketStatus(
            exchange="US",
            holiday=self.holiday_name,
            is_open=self.market_status == "open",
            session="regular" if self.market_status == "open" else "closed",
            timestamp=int(time.time()),
            timezone="America/New_York",
        )

        return (200, status.to_dict())

    @property
    def request_count(self) -> int:
        """Number of requests handled."""
        return self._request_count
