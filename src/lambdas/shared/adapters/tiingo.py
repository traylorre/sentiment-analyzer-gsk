"""Tiingo API adapter for news and OHLC data."""

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Literal

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

# =============================================================================
# DFA-004 FIX: API Response Cache
# =============================================================================
# Cache TTL in seconds (default 30 minutes for news, 1 hour for OHLC)
API_CACHE_TTL_NEWS_SECONDS = int(os.environ.get("API_CACHE_TTL_NEWS_SECONDS", "1800"))
API_CACHE_TTL_OHLC_SECONDS = int(os.environ.get("API_CACHE_TTL_OHLC_SECONDS", "3600"))

# In-memory cache (survives Lambda warm invocations)
_tiingo_cache: dict[str, tuple[float, Any]] = {}
_MAX_CACHE_ENTRIES = 100  # Prevent unbounded memory growth


def _get_cache_key(endpoint: str, params: dict) -> str:
    """Generate cache key from endpoint and params."""
    param_str = json.dumps(params, sort_keys=True)
    # MD5 used for cache key (not security) - S324 is a false positive
    return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()  # noqa: S324


def _get_from_cache(key: str, ttl: int) -> Any | None:
    """Get value from cache if not expired."""
    if key in _tiingo_cache:
        timestamp, value = _tiingo_cache[key]
        if time.time() - timestamp < ttl:
            return value
        # Expired - remove from cache
        del _tiingo_cache[key]
    return None


def _put_in_cache(key: str, value: Any) -> None:
    """Put value in cache with current timestamp."""
    global _tiingo_cache
    # Evict oldest entries if cache is full
    if len(_tiingo_cache) >= _MAX_CACHE_ENTRIES:
        oldest_key = min(_tiingo_cache.keys(), key=lambda k: _tiingo_cache[k][0])
        del _tiingo_cache[oldest_key]
    _tiingo_cache[key] = (time.time(), value)


def clear_cache() -> None:
    """Clear the API response cache. Used in tests."""
    global _tiingo_cache
    _tiingo_cache = {}


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

        DFA-004 optimization: Results cached for 30 minutes to reduce API calls
        and preserve rate limits (500 symbol lookups/month on free tier).

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

        # DFA-004: Check cache first
        cache_params = {
            "tickers": tickers_param,
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "limit": limit,
        }
        cache_key = _get_cache_key("/tiingo/news", cache_params)
        cached_data = _get_from_cache(cache_key, API_CACHE_TTL_NEWS_SECONDS)
        if cached_data is not None:
            logger.debug(f"Tiingo news cache hit for {tickers_param}")
            data = cached_data
        else:
            try:
                response = self.client.get(
                    "/tiingo/news",
                    params=cache_params,
                )
                data = self._handle_response(response)
                # Cache the raw response
                _put_in_cache(cache_key, data)
                logger.debug(f"Tiingo news cache miss for {tickers_param}, cached")
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

        DFA-004 optimization: Results cached for 1 hour. OHLC data changes
        infrequently (daily), so longer TTL is safe.

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

        # DFA-004: Check cache first
        endpoint = f"/tiingo/daily/{ticker}/prices"
        cache_params = {
            "ticker": ticker,
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
        }
        cache_key = _get_cache_key(endpoint, cache_params)
        cached_data = _get_from_cache(cache_key, API_CACHE_TTL_OHLC_SECONDS)
        if cached_data is not None:
            logger.debug(f"Tiingo OHLC cache hit for {ticker}")
            data = cached_data
        else:
            try:
                response = self.client.get(
                    endpoint,
                    params={
                        "startDate": start_date.strftime("%Y-%m-%d"),
                        "endDate": end_date.strftime("%Y-%m-%d"),
                    },
                )
                data = self._handle_response(response)
                # Cache the raw response
                _put_in_cache(cache_key, data)
                logger.debug(f"Tiingo OHLC cache miss for {ticker}, cached")
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
