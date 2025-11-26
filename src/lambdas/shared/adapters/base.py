"""Base adapter class for financial APIs."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AdapterError(Exception):
    """Base exception for adapter errors."""

    pass


class RateLimitError(AdapterError):
    """Raised when API rate limit is exceeded."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class NewsArticle(BaseModel):
    """Normalized news article from any source."""

    article_id: str
    source: Literal["tiingo", "finnhub"]
    title: str
    description: str | None = None
    url: str | None = None
    published_at: datetime
    tickers: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_name: str | None = None  # e.g., "bloomberg", "reuters"

    # Sentiment (if provided by source)
    sentiment_score: float | None = None  # -1 to +1
    sentiment_label: Literal["positive", "negative", "neutral"] | None = None


class SentimentData(BaseModel):
    """Normalized sentiment data from any source."""

    ticker: str
    source: Literal["tiingo", "finnhub"]
    fetched_at: datetime

    # Overall sentiment
    sentiment_score: float | None = None  # -1 to +1
    bullish_percent: float | None = None  # 0 to 1
    bearish_percent: float | None = None  # 0 to 1

    # News volume
    articles_count: int | None = None
    buzz_score: float | None = None  # 0 to 1

    # Comparison
    sector_average_score: float | None = None


class OHLCCandle(BaseModel):
    """OHLC price data for volatility calculation."""

    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int | None = None


class BaseAdapter(ABC):
    """Base class for financial API adapters."""

    def __init__(self, api_key: str):
        """Initialize adapter with API key.

        Args:
            api_key: API key for authentication
        """
        self.api_key = api_key

    @property
    @abstractmethod
    def source_name(self) -> Literal["tiingo", "finnhub"]:
        """Return the source name for this adapter."""
        pass

    @abstractmethod
    def get_news(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Fetch news articles for given tickers.

        Args:
            tickers: List of stock symbols
            start_date: Start date for news (default: 7 days ago)
            end_date: End date for news (default: now)
            limit: Maximum articles to return

        Returns:
            List of normalized NewsArticle objects

        Raises:
            AdapterError: On API errors
            RateLimitError: When rate limit exceeded
        """
        pass

    @abstractmethod
    def get_sentiment(self, ticker: str) -> SentimentData | None:
        """Fetch sentiment data for a single ticker.

        Args:
            ticker: Stock symbol

        Returns:
            SentimentData or None if not available

        Raises:
            AdapterError: On API errors
            RateLimitError: When rate limit exceeded
        """
        pass

    @abstractmethod
    def get_ohlc(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[OHLCCandle]:
        """Fetch OHLC price data for volatility calculation.

        Args:
            ticker: Stock symbol
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            List of OHLCCandle objects

        Raises:
            AdapterError: On API errors
            RateLimitError: When rate limit exceeded
        """
        pass
