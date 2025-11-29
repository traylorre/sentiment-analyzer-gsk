# E2E Test Fixtures
#
# Synthetic data generators for external APIs (Tiingo, Finnhub, SendGrid)
# and data models for test data.
#
# These fixtures generate deterministic, reproducible test data based on seeds
# to enable the "test oracle" pattern where expected outputs can be computed
# from inputs.

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SyntheticTicker:
    """Represents a synthetic ticker for testing."""

    symbol: str
    company_name: str
    exchange: str = "NYSE"
    is_valid: bool = True
    is_delisted: bool = False
    successor_ticker: str | None = None


@dataclass
class SyntheticSentiment:
    """Represents synthetic sentiment data for testing."""

    ticker: str
    sentiment_score: float  # -1.0 to 1.0
    source: str  # "tiingo" or "finnhub"
    timestamp: datetime
    article_count: int = 1


@dataclass
class SyntheticUser:
    """Represents a synthetic user for testing."""

    user_id: str
    email: str
    is_anonymous: bool = True
    auth_provider: str | None = None


@dataclass
class SyntheticNewsArticle:
    """Represents a synthetic news article for testing."""

    article_id: str
    ticker: str
    title: str
    description: str
    published_at: datetime
    source: str
    sentiment_score: float


@dataclass
class SyntheticOHLC:
    """Represents synthetic OHLC price data for ATR testing."""

    ticker: str
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class SyntheticEmailEvent:
    """Represents a synthetic email delivery event for testing."""

    message_id: str
    email: str
    status: str  # "delivered", "opened", "clicked", "bounced"
    timestamp: datetime
    subject: str


__all__ = [
    "SyntheticTicker",
    "SyntheticSentiment",
    "SyntheticUser",
    "SyntheticNewsArticle",
    "SyntheticOHLC",
    "SyntheticEmailEvent",
]
