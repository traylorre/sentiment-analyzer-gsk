"""
NewsAPI Adapter
===============

Fetches articles from NewsAPI.org /everything endpoint.

For On-Call Engineers:
    Common issues:
    - 429 Rate Limited: Wait for hourly reset (100 requests/day on free tier)
    - 401 Unauthorized: Check API key in Secrets Manager
    - Empty results: Verify tag has recent news articles

    See SC-03 and SC-07 in ON_CALL_SOP.md.

    Check API key:
    aws secretsmanager get-secret-value \
      --secret-id dev/sentiment-analyzer/newsapi \
      --query 'SecretString' --output text | jq -r '.api_key' | head -c 8

For Developers:
    - Uses exponential backoff on rate limits
    - Circuit breaker after 3 consecutive failures
    - Max 100 articles per request (NewsAPI limit)
    - Articles older than 24h are filtered out

Security Notes:
    - API key retrieved from Secrets Manager
    - Never log the full API key
    - HTTPS enforced for all requests
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import (
    AdapterError,
    AuthenticationError,
    BaseAdapter,
    ConnectionError,
    RateLimitError,
)

# Structured logging
logger = logging.getLogger(__name__)

# NewsAPI configuration
NEWSAPI_BASE_URL = "https://newsapi.org/v2/everything"
DEFAULT_PAGE_SIZE = 100  # Max allowed by NewsAPI
DEFAULT_LOOKBACK_HOURS = 24

# Retry configuration
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 30

# Circuit breaker
CIRCUIT_BREAKER_THRESHOLD = 3
CIRCUIT_BREAKER_RESET_SECONDS = 300  # 5 minutes


class NewsAPIAdapter(BaseAdapter):
    """
    Adapter for fetching articles from NewsAPI.org.

    Features:
    - Exponential backoff on rate limits
    - Circuit breaker for consecutive failures
    - Filters articles to last 24 hours
    - Returns up to 100 articles per tag

    On-Call Note:
        Free tier: 100 requests/day, 100 articles/request
        Developer tier: 500 requests/day
        See https://newsapi.org/pricing for limits.
    """

    def __init__(self, api_key: str):
        """
        Initialize the NewsAPI adapter.

        Args:
            api_key: NewsAPI API key from Secrets Manager
        """
        self.api_key = api_key
        self._consecutive_failures = 0
        self._circuit_open_until: float | None = None

    def get_source_name(self) -> str:
        """Return the source name."""
        return "newsapi"

    def fetch_items(
        self,
        tag: str,
        page_size: int = DEFAULT_PAGE_SIZE,
        lookback_hours: int = DEFAULT_LOOKBACK_HOURS,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Fetch articles from NewsAPI for a given tag.

        Args:
            tag: Search keyword/tag
            page_size: Number of articles to fetch (max 100)
            lookback_hours: How far back to search (default 24h)
            **kwargs: Additional parameters

        Returns:
            List of article dicts

        Raises:
            RateLimitError: If rate limited (429)
            AuthenticationError: If API key invalid (401)
            AdapterError: For other errors
        """
        # Check circuit breaker
        if self._is_circuit_open():
            raise AdapterError(
                "Circuit breaker open - too many consecutive failures"
            )

        # Build request parameters
        params = self._build_params(tag, page_size, lookback_hours)

        # Make request with retries
        try:
            response = self._make_request(params)
            self._reset_circuit_breaker()
            return self._parse_response(response)

        except Exception as e:
            self._record_failure()
            raise

    def _build_params(
        self,
        tag: str,
        page_size: int,
        lookback_hours: int,
    ) -> dict[str, Any]:
        """
        Build NewsAPI request parameters.

        Args:
            tag: Search keyword
            page_size: Number of results
            lookback_hours: Time window

        Returns:
            Dict of request parameters
        """
        # Calculate time window
        now = datetime.now(timezone.utc)
        from_date = now - timedelta(hours=lookback_hours)

        return {
            "q": tag,
            "from": from_date.isoformat(),
            "to": now.isoformat(),
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": min(page_size, DEFAULT_PAGE_SIZE),
        }

    def _make_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Make HTTP request to NewsAPI with retries.

        Args:
            params: Request parameters

        Returns:
            Parsed JSON response

        Raises:
            RateLimitError: On 429 response
            AuthenticationError: On 401 response
            AdapterError: On other errors
        """
        headers = {
            "X-Api-Key": self.api_key,
            "User-Agent": "SentimentAnalyzer/1.0",
        }

        backoff = INITIAL_BACKOFF_SECONDS

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(
                    f"NewsAPI request attempt {attempt + 1}",
                    extra={"params": {k: v for k, v in params.items() if k != "apiKey"}},
                )

                response = requests.get(
                    NEWSAPI_BASE_URL,
                    params=params,
                    headers=headers,
                    timeout=30,
                )

                # Handle response status
                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 401:
                    logger.error(
                        "NewsAPI authentication failed",
                        extra={"status_code": 401},
                    )
                    raise AuthenticationError("Invalid NewsAPI key")

                elif response.status_code == 429:
                    # Rate limited - get retry-after if available
                    retry_after = response.headers.get("Retry-After")
                    retry_seconds = int(retry_after) if retry_after else 3600

                    logger.warning(
                        "NewsAPI rate limited",
                        extra={
                            "status_code": 429,
                            "retry_after": retry_seconds,
                        },
                    )
                    raise RateLimitError(
                        "NewsAPI rate limit exceeded",
                        retry_after=retry_seconds,
                    )

                elif response.status_code >= 500:
                    # Server error - retry with backoff
                    logger.warning(
                        f"NewsAPI server error, retrying",
                        extra={
                            "status_code": response.status_code,
                            "attempt": attempt + 1,
                            "backoff": backoff,
                        },
                    )

                    if attempt < MAX_RETRIES - 1:
                        time.sleep(backoff)
                        backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                        continue

                    raise AdapterError(
                        f"NewsAPI server error: {response.status_code}"
                    )

                else:
                    # Other error
                    error_body = response.text[:200]
                    raise AdapterError(
                        f"NewsAPI error {response.status_code}: {error_body}"
                    )

            except requests.exceptions.Timeout:
                logger.warning(
                    "NewsAPI request timeout",
                    extra={"attempt": attempt + 1},
                )

                if attempt < MAX_RETRIES - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                    continue

                raise ConnectionError("NewsAPI request timed out")

            except requests.exceptions.RequestException as e:
                logger.error(
                    f"NewsAPI connection error: {e}",
                    extra={"attempt": attempt + 1},
                )

                if attempt < MAX_RETRIES - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                    continue

                raise ConnectionError(f"Failed to connect to NewsAPI: {e}")

        # Should not reach here
        raise AdapterError("Max retries exceeded")

    def _parse_response(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parse NewsAPI response into article list.

        Args:
            response: NewsAPI JSON response

        Returns:
            List of article dicts

        Raises:
            AdapterError: If response format is invalid
        """
        if response.get("status") != "ok":
            error_message = response.get("message", "Unknown error")
            raise AdapterError(f"NewsAPI error: {error_message}")

        articles = response.get("articles", [])

        logger.info(
            f"Fetched {len(articles)} articles from NewsAPI",
            extra={"total_results": response.get("totalResults", 0)},
        )

        # Validate and normalize articles
        normalized = []
        for article in articles:
            if self._is_valid_article(article):
                normalized.append(self._normalize_article(article))

        logger.debug(
            f"Normalized {len(normalized)} valid articles",
            extra={"skipped": len(articles) - len(normalized)},
        )

        return normalized

    def _is_valid_article(self, article: dict[str, Any]) -> bool:
        """
        Check if article has required fields.

        Args:
            article: NewsAPI article dict

        Returns:
            True if valid, False otherwise
        """
        # Must have URL or (title + publishedAt) for deduplication
        has_url = bool(article.get("url"))
        has_title_and_date = bool(
            article.get("title") and article.get("publishedAt")
        )

        return has_url or has_title_and_date

    def _normalize_article(self, article: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize article to standard format.

        Args:
            article: NewsAPI article dict

        Returns:
            Normalized article dict
        """
        return {
            "url": article.get("url", ""),
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "publishedAt": article.get("publishedAt", ""),
            "author": article.get("author"),
            "source": article.get("source", {}),
            "content": article.get("content", ""),
            "urlToImage": article.get("urlToImage"),
        }

    def _is_circuit_open(self) -> bool:
        """
        Check if circuit breaker is open.

        Returns:
            True if circuit is open (blocking requests)
        """
        if self._circuit_open_until is None:
            return False

        if time.time() > self._circuit_open_until:
            # Circuit has reset
            self._circuit_open_until = None
            self._consecutive_failures = 0
            return False

        return True

    def _record_failure(self) -> None:
        """
        Record a failure and potentially open circuit breaker.

        On-Call Note:
            Circuit breaker opens after 3 consecutive failures.
            Wait 5 minutes for automatic reset.
        """
        self._consecutive_failures += 1

        if self._consecutive_failures >= CIRCUIT_BREAKER_THRESHOLD:
            self._circuit_open_until = time.time() + CIRCUIT_BREAKER_RESET_SECONDS
            logger.error(
                "Circuit breaker opened - too many consecutive failures",
                extra={
                    "failures": self._consecutive_failures,
                    "reset_after_seconds": CIRCUIT_BREAKER_RESET_SECONDS,
                },
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset circuit breaker on successful request."""
        self._consecutive_failures = 0
        self._circuit_open_until = None
