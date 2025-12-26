"""Tiingo API adapter for news and OHLC data."""

import hashlib
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
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
from src.lambdas.shared.logging_utils import sanitize_for_log

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
    return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()  # nosec B324


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
            end_date = datetime.now(UTC)
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
            end_date = datetime.now(UTC)
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
            logger.debug("Tiingo OHLC cache hit for %s", sanitize_for_log(ticker))
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
                logger.debug(
                    "Tiingo OHLC cache miss for %s, cached", sanitize_for_log(ticker)
                )
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

    def get_intraday_ohlc(
        self,
        ticker: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        resolution: str = "5",
    ) -> list[OHLCCandle]:
        """Fetch intraday OHLC price data from Tiingo IEX endpoint.

        Feature 1055: Enables intraday resolutions (1m, 5m, 15m, 30m, 1h) using
        Tiingo IEX endpoint instead of Finnhub (which requires Premium subscription).

        Args:
            ticker: Stock symbol
            start_date: Start date (default: 7 days ago for intraday)
            end_date: End date (default: now)
            resolution: Candle resolution - '1', '5', '15', '30', or '60' minutes

        Returns:
            List of OHLCCandle objects
        """
        # Map resolution to Tiingo resampleFreq format
        resolution_map = {
            "1": "1min",
            "5": "5min",
            "15": "15min",
            "30": "30min",
            "60": "1hour",
        }
        resample_freq = resolution_map.get(resolution, "5min")

        # Default date range (shorter for intraday due to data limits)
        if end_date is None:
            end_date = datetime.now(UTC)
        if start_date is None:
            # Use shorter default for intraday (7 days for 1min, longer for others)
            days_back = 7 if resolution == "1" else 30
            start_date = end_date - timedelta(days=days_back)

        # Use 5-minute cache TTL for intraday (more frequent updates)
        cache_ttl = 300  # 5 minutes

        # Check cache first
        endpoint = f"/iex/{ticker}/prices"
        cache_params = {
            "ticker": ticker,
            "startDate": start_date.strftime("%Y-%m-%d"),
            "resampleFreq": resample_freq,
        }
        cache_key = _get_cache_key(endpoint, cache_params)
        cached_data = _get_from_cache(cache_key, cache_ttl)
        if cached_data is not None:
            logger.debug(
                "Tiingo IEX intraday cache hit for %s (%s)",
                sanitize_for_log(ticker),
                resample_freq,
            )
            data = cached_data
        else:
            try:
                response = self.client.get(
                    endpoint,
                    params={
                        "startDate": start_date.strftime("%Y-%m-%d"),
                        "resampleFreq": resample_freq,
                    },
                )
                data = self._handle_response(response)
                # Cache the raw response
                _put_in_cache(cache_key, data)
                logger.debug(
                    "Tiingo IEX intraday cache miss for %s (%s), cached",
                    sanitize_for_log(ticker),
                    resample_freq,
                )
            except httpx.RequestError as e:
                logger.error(f"Tiingo IEX intraday request failed: {e}")
                raise AdapterError(f"Tiingo IEX intraday request failed: {e}") from e

        # Parse response (IEX format is slightly different from daily)
        candles = []
        for item in data:
            try:
                # IEX uses 'date' field with ISO format
                date_str = item["date"]
                # Handle both Z and +00:00 formats
                if date_str.endswith("Z"):
                    date_str = date_str[:-1] + "+00:00"
                date = datetime.fromisoformat(date_str)

                candles.append(
                    OHLCCandle(
                        date=date,
                        open=float(item["open"]),
                        high=float(item["high"]),
                        low=float(item["low"]),
                        close=float(item["close"]),
                        volume=None,  # IEX doesn't include volume in resampled data
                    )
                )
            except (KeyError, ValueError) as e:
                logger.warning(f"Failed to parse Tiingo IEX candle: {e}")
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
