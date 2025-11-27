"""Tiingo API adapter for news and OHLC data."""

import logging
from datetime import datetime, timedelta
from typing import Literal

import httpx

from src.lambdas.shared.adapters.base import (
    AdapterError,
    BaseAdapter,
    NewsArticle,
    OHLCCandle,
    RateLimitError,
    SentimentData,
)

logger = logging.getLogger(__name__)


class TiingoAdapter(BaseAdapter):
    """Adapter for Tiingo Financial API.

    Tiingo provides:
    - Financial news with ticker associations
    - OHLC daily price data
    - No built-in sentiment scores (we calculate our own)

    Rate limits (free tier):
    - 500 symbol lookups/month
    - Aggressive caching recommended
    """

    BASE_URL = "https://api.tiingo.com"
    TIMEOUT = 30.0

    def __init__(self, api_key: str):
        """Initialize Tiingo adapter.

        Args:
            api_key: Tiingo API token
        """
        super().__init__(api_key)
        self._client: httpx.Client | None = None

    @property
    def source_name(self) -> Literal["tiingo", "finnhub"]:
        """Return the source name."""
        return "tiingo"

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client with authentication."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Token {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.TIMEOUT,
            )
        return self._client

    def _handle_response(self, response: httpx.Response) -> dict | list:
        """Handle API response and raise appropriate errors.

        Args:
            response: HTTP response

        Returns:
            Parsed JSON response

        Raises:
            RateLimitError: On 429 status
            AdapterError: On other errors
        """
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Tiingo rate limit exceeded",
                retry_after=int(retry_after) if retry_after else 60,
            )

        if response.status_code == 401:
            raise AdapterError("Tiingo authentication failed: Invalid API key")

        if response.status_code == 404:
            return []

        if not response.is_success:
            raise AdapterError(
                f"Tiingo API error: {response.status_code} - {response.text}"
            )

        return response.json()

    def get_news(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Fetch news articles for given tickers.

        Args:
            tickers: List of stock symbols (max 10 per request)
            start_date: Start date for news (default: 7 days ago)
            end_date: End date for news (default: now)
            limit: Maximum articles to return

        Returns:
            List of normalized NewsArticle objects
        """
        if not tickers:
            return []

        # Default date range
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=7)

        # Tiingo accepts comma-separated tickers
        tickers_param = ",".join(tickers[:10])  # Max 10 per request

        try:
            response = self.client.get(
                "/tiingo/news",
                params={
                    "tickers": tickers_param,
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "limit": limit,
                },
            )
            data = self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Tiingo request failed: {e}")
            raise AdapterError(f"Tiingo request failed: {e}") from e

        # Parse response
        articles = []
        for item in data:
            try:
                published_at = datetime.fromisoformat(
                    item["publishedDate"].replace("Z", "+00:00")
                )
                articles.append(
                    NewsArticle(
                        article_id=str(item.get("id", hash(item["title"]))),
                        source="tiingo",
                        title=item["title"],
                        description=item.get("description"),
                        url=item.get("url"),
                        published_at=published_at,
                        tickers=item.get("tickers", []),
                        tags=item.get("tags", []),
                        source_name=item.get("source"),
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse Tiingo article: {e}")
                continue

        return articles

    def get_sentiment(self, ticker: str) -> SentimentData | None:
        """Tiingo doesn't provide built-in sentiment scores.

        This method returns None. Use our own sentiment model for Tiingo news.

        Args:
            ticker: Stock symbol

        Returns:
            None (Tiingo has no sentiment endpoint)
        """
        return None

    def get_ohlc(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[OHLCCandle]:
        """Fetch daily OHLC price data.

        Args:
            ticker: Stock symbol
            start_date: Start date (default: 30 days ago)
            end_date: End date (default: now)

        Returns:
            List of OHLCCandle objects
        """
        # Default date range
        if end_date is None:
            end_date = datetime.utcnow()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        try:
            response = self.client.get(
                f"/tiingo/daily/{ticker}/prices",
                params={
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                },
            )
            data = self._handle_response(response)
        except httpx.RequestError as e:
            logger.error(f"Tiingo OHLC request failed: {e}")
            raise AdapterError(f"Tiingo OHLC request failed: {e}") from e

        # Parse response
        candles = []
        for item in data:
            try:
                date = datetime.fromisoformat(item["date"].replace("Z", "+00:00"))
                candles.append(
                    OHLCCandle(
                        date=date,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=float(item["close"]),
                        volume=int(item["volume"]) if item.get("volume") else None,
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse Tiingo candle: {e}")
                continue

        return candles

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "TiingoAdapter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
