"""Finnhub API adapter for news sentiment and OHLC data."""

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
# Cache TTL in seconds (default 30 minutes for news/sentiment, 1 hour for OHLC)
API_CACHE_TTL_NEWS_SECONDS = int(os.environ.get("API_CACHE_TTL_NEWS_SECONDS", "1800"))
API_CACHE_TTL_SENTIMENT_SECONDS = int(
    os.environ.get("API_CACHE_TTL_SENTIMENT_SECONDS", "1800")
)
API_CACHE_TTL_OHLC_SECONDS = int(os.environ.get("API_CACHE_TTL_OHLC_SECONDS", "3600"))

# In-memory cache (survives Lambda warm invocations)
_finnhub_cache: dict[str, tuple[float, Any]] = {}
_MAX_CACHE_ENTRIES = 100  # Prevent unbounded memory growth


def _get_cache_key(endpoint: str, params: dict) -> str:
    """Generate cache key from endpoint and params."""
    param_str = json.dumps(params, sort_keys=True)
    # MD5 used for cache key (not security) - S324 is a false positive
    return hashlib.md5(  # noqa: S324
        f"finnhub:{endpoint}:{param_str}".encode()
    ).hexdigest()


def _get_from_cache(key: str, ttl: int) -> Any | None:
    """Get value from cache if not expired."""
    if key in _finnhub_cache:
        timestamp, value = _finnhub_cache[key]
        if time.time() - timestamp < ttl:
            return value
        # Expired - remove from cache
        del _finnhub_cache[key]
    return None


def _put_in_cache(key: str, value: Any) -> None:
    """Put value in cache with current timestamp."""
    global _finnhub_cache
    # Evict oldest entries if cache is full
    if len(_finnhub_cache) >= _MAX_CACHE_ENTRIES:
        oldest_key = min(_finnhub_cache.keys(), key=lambda k: _finnhub_cache[k][0])
        del _finnhub_cache[oldest_key]
    _finnhub_cache[key] = (time.time(), value)


def clear_cache() -> None:
    """Clear the API response cache. Used in tests."""
    global _finnhub_cache
    _finnhub_cache = {}


class FinnhubAdapter(BaseAdapter):
    """Adapter for Finnhub Financial API.

    Finnhub provides:
    - Company news with headlines
    - Built-in sentiment scores per ticker
    - Stock candle (OHLC) data

    Rate limits (free tier):
    - 60 calls/minute
    - Implement caching and circuit breaker
    """

    BASE_URL = "https://finnhub.io/api/v1"
    TIMEOUT = 30.0

    def __init__(self, api_key: str):
        """Initialize Finnhub adapter.

        Args:
            api_key: Finnhub API token
        """
        super().__init__(api_key)
        self._client: httpx.Client | None = None

    @property
    def source_name(self) -> Literal["tiingo", "finnhub"]:
        """Return the source name."""
        return "finnhub"

    @property
    def client(self) -> httpx.Client:
        """Get or create HTTP client with authentication."""
        if self._client is None:
            self._client = httpx.Client(
                base_url=self.BASE_URL,
                params={"token": self.api_key},
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
                "Finnhub rate limit exceeded",
                retry_after=int(retry_after) if retry_after else 60,
            )

        if response.status_code == 401:
            raise AdapterError("Finnhub authentication failed: Invalid API key")

        if response.status_code == 403:
            raise AdapterError("Finnhub access denied: Check API key permissions")

        if not response.is_success:
            raise AdapterError(
                f"Finnhub API error: {response.status_code} - {response.text}"
            )

        return response.json()

    def get_news(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[NewsArticle]:
        """Fetch company news for given tickers.

        DFA-004 optimization: Results cached for 30 minutes per ticker.
        Note: Finnhub requires one API call per ticker.

        Args:
            tickers: List of stock symbols
            start_date: Start date for news (default: 7 days ago)
            end_date: End date for news (default: now)
            limit: Maximum articles per ticker

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

        articles = []
        for ticker in tickers:
            # DFA-004: Check cache first for each ticker
            cache_params = {
                "symbol": ticker,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
            }
            cache_key = _get_cache_key("/company-news", cache_params)
            cached_data = _get_from_cache(cache_key, API_CACHE_TTL_NEWS_SECONDS)

            if cached_data is not None:
                logger.debug(f"Finnhub news cache hit for {ticker}")
                data = cached_data
            else:
                try:
                    response = self.client.get(
                        "/company-news",
                        params=cache_params,
                    )
                    data = self._handle_response(response)
                    # Cache the raw response
                    _put_in_cache(cache_key, data)
                    logger.debug(f"Finnhub news cache miss for {ticker}, cached")
                except httpx.RequestError as e:
                    logger.error(f"Finnhub news request failed for {ticker}: {e}")
                    continue  # Continue with other tickers

            # Parse response - Finnhub returns array of news
            for item in data[:limit]:
                try:
                    # Finnhub uses Unix timestamp
                    published_at = datetime.fromtimestamp(item["datetime"])
                    articles.append(
                        NewsArticle(
                            article_id=str(item.get("id", hash(item["headline"]))),
                            source="finnhub",
                            title=item["headline"],
                            description=item.get("summary"),
                            url=item.get("url"),
                            published_at=published_at,
                            tickers=[ticker],  # Finnhub is per-ticker
                            tags=item.get("category", "").split(","),
                            source_name=item.get("source"),
                        )
                    )
                except (KeyError, ValueError) as e:
                    logger.warning(f"Failed to parse Finnhub article: {e}")
                    continue

        return articles

    def get_sentiment(self, ticker: str) -> SentimentData | None:
        """Fetch sentiment data for a single ticker.

        DFA-004 optimization: Results cached for 30 minutes.
        Finnhub provides built-in sentiment scores based on news analysis.

        Args:
            ticker: Stock symbol

        Returns:
            SentimentData or None if not available
        """
        # DFA-004: Check cache first
        cache_params = {"symbol": ticker}
        cache_key = _get_cache_key("/news-sentiment", cache_params)
        cached_data = _get_from_cache(cache_key, API_CACHE_TTL_SENTIMENT_SECONDS)

        if cached_data is not None:
            logger.debug(f"Finnhub sentiment cache hit for {ticker}")
            data = cached_data
        else:
            try:
                response = self.client.get(
                    "/news-sentiment",
                    params=cache_params,
                )
                data = self._handle_response(response)
                # Cache the raw response
                _put_in_cache(cache_key, data)
                logger.debug(f"Finnhub sentiment cache miss for {ticker}, cached")
            except httpx.RequestError as e:
                logger.error(f"Finnhub sentiment request failed: {e}")
                raise AdapterError(f"Finnhub sentiment request failed: {e}") from e

        # Check if data is valid
        if not data or not data.get("sentiment"):
            return None

        sentiment = data.get("sentiment", {})
        buzz = data.get("buzz", {})

        # Normalize score to -1 to +1
        # Finnhub bullish/bearish are percentages (0-1)
        bullish = sentiment.get("bullishPercent", 0)
        bearish = sentiment.get("bearishPercent", 0)
        score = bullish - bearish  # Range: -1 to +1

        return SentimentData(
            ticker=ticker,
            source="finnhub",
            fetched_at=datetime.utcnow(),
            sentiment_score=score,
            bullish_percent=bullish,
            bearish_percent=bearish,
            articles_count=buzz.get("articlesInLastWeek"),
            buzz_score=buzz.get("buzz"),
            sector_average_score=data.get("sectorAverageNewsScore"),
        )

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

        # Convert to Unix timestamps
        from_ts = int(start_date.timestamp())
        to_ts = int(end_date.timestamp())

        # DFA-004: Check cache first
        cache_params = {
            "symbol": ticker,
            "resolution": "D",
            "from": from_ts,
            "to": to_ts,
        }
        cache_key = _get_cache_key("/stock/candle", cache_params)
        cached_data = _get_from_cache(cache_key, API_CACHE_TTL_OHLC_SECONDS)

        if cached_data is not None:
            logger.debug(f"Finnhub OHLC cache hit for {ticker}")
            data = cached_data
        else:
            try:
                response = self.client.get(
                    "/stock/candle",
                    params=cache_params,
                )
                data = self._handle_response(response)
                # Cache the raw response
                _put_in_cache(cache_key, data)
                logger.debug(f"Finnhub OHLC cache miss for {ticker}, cached")
            except httpx.RequestError as e:
                logger.error(f"Finnhub OHLC request failed: {e}")
                raise AdapterError(f"Finnhub OHLC request failed: {e}") from e

        # Check for no data
        if data.get("s") == "no_data":
            return []

        # Parse response - Finnhub returns parallel arrays
        candles = []
        timestamps = data.get("t", [])
        opens = data.get("o", [])
        highs = data.get("h", [])
        lows = data.get("l", [])
        closes = data.get("c", [])
        volumes = data.get("v", [])

        for i in range(len(timestamps)):
            try:
                candles.append(
                    OHLCCandle(
                        date=datetime.fromtimestamp(timestamps[i]),
                        open=float(opens[i]),
                        high=float(highs[i]),
                        low=float(lows[i]),
                        close=float(closes[i]),
                        volume=int(volumes[i]) if i < len(volumes) else None,
                    )
                )
            except (IndexError, ValueError) as e:
                logger.warning(f"Failed to parse Finnhub candle at index {i}: {e}")
                continue

        return candles

    def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "FinnhubAdapter":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
