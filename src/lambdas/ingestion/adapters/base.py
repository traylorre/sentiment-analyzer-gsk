"""
Base Adapter Interface
======================

Abstract base class for data source adapters.

For On-Call Engineers:
    All adapters implement this interface. If adding a new source,
    check that it follows the same pattern as Tiingo/Finnhub adapters.

For Developers:
    - Implement fetch_items() to return list of article dicts
    - Each adapter handles its own authentication and rate limiting
    - Return standardized article format (url, title, publishedAt, etc.)

Security Notes:
    - API keys retrieved via Secrets Manager (never hardcoded)
    - All external calls use HTTPS
    - Rate limiting prevents API abuse
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseAdapter(ABC):
    """
    Abstract base class for data source adapters.

    All data source adapters must implement this interface.
    Currently implemented:
    - TiingoAdapter (tiingo.py) - Primary financial news source
    - FinnhubAdapter (finnhub.py) - Secondary financial news source

    Future adapters:
    - RSSAdapter
    """

    @abstractmethod
    def fetch_items(self, tag: str, **kwargs) -> list[dict[str, Any]]:
        """
        Fetch items from the data source for a given tag.

        Args:
            tag: Search tag/keyword to fetch items for
            **kwargs: Additional source-specific parameters

        Returns:
            List of article dicts with standardized fields:
            - url: Article URL
            - title: Article title
            - publishedAt: ISO8601 timestamp
            - description: Article description/snippet
            - source: Source metadata
            - author: Author name (optional)

        Raises:
            RateLimitError: If rate limited by the source
            AdapterError: For other adapter-specific errors
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """
        Get the name of this data source.

        Returns:
            Source name (e.g., "tiingo", "finnhub")
        """
        pass


class AdapterError(Exception):
    """Base exception for adapter errors."""

    pass


class RateLimitError(AdapterError):
    """Raised when rate limited by the data source."""

    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(AdapterError):
    """Raised when authentication fails."""

    pass


class ConnectionError(AdapterError):
    """Raised when connection to data source fails."""

    pass
