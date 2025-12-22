"""Parallel source fetching for concurrent ingestion.

Uses ThreadPoolExecutor to fetch from Tiingo and Finnhub simultaneously,
reducing total ingestion latency.

Feature 1010: Parallel Ingestion with Cross-Source Deduplication
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from typing import Any

from src.lambdas.shared.adapters.base import NewsArticle
from src.lib.threading_utils import ThreadSafeDict

logger = logging.getLogger(__name__)

# Maximum workers for parallel fetching (2 sources = 2 workers minimum)
MAX_WORKERS = 4


class ParallelFetcher:
    """Fetches articles from multiple sources concurrently.

    Uses ThreadPoolExecutor to run Tiingo and Finnhub API calls in parallel,
    reducing total fetch time from (latency_tiingo + latency_finnhub) to
    max(latency_tiingo, latency_finnhub).

    Thread-safety:
    - Results collected via ThreadSafeQueue
    - Errors collected via ThreadSafeQueue
    - Metrics tracked via ThreadSafeDict

    Usage:
        fetcher = ParallelFetcher(
            tiingo_adapter=tiingo,
            finnhub_adapter=finnhub,
            tiingo_breaker=tiingo_cb,
            finnhub_breaker=finnhub_cb,
            quota_tracker=quota,
        )

        results = fetcher.fetch_all_sources(["AAPL", "TSLA"])
        # results = {"tiingo": [...], "finnhub": [...]}

        metrics = fetcher.get_metrics()
        errors = fetcher.get_errors()
    """

    def __init__(
        self,
        tiingo_adapter: Any,
        finnhub_adapter: Any,
        tiingo_breaker: Any,
        finnhub_breaker: Any,
        quota_tracker: Any,
    ):
        """Initialize ParallelFetcher.

        Args:
            tiingo_adapter: Tiingo API adapter
            finnhub_adapter: Finnhub API adapter
            tiingo_breaker: Circuit breaker for Tiingo
            finnhub_breaker: Circuit breaker for Finnhub
            quota_tracker: Quota tracker for rate limiting
        """
        self._tiingo_adapter = tiingo_adapter
        self._finnhub_adapter = finnhub_adapter
        self._tiingo_breaker = tiingo_breaker
        self._finnhub_breaker = finnhub_breaker
        self._quota_tracker = quota_tracker

        # Thread-safe collections for results and errors
        self._results: dict[str, list[NewsArticle]] = {}
        self._errors: list[dict[str, Any]] = []
        self._metrics = ThreadSafeDict()

        # Track execution duration
        self._start_time: float | None = None
        self._end_time: float | None = None

    def fetch_all_sources(self, tickers: list[str]) -> dict[str, list[NewsArticle]]:
        """Fetch articles from all sources in parallel.

        Args:
            tickers: List of ticker symbols to fetch

        Returns:
            Dict mapping source name to list of articles:
            {"tiingo": [...], "finnhub": [...]}
        """
        self._start_time = time.time()
        self._results = {"tiingo": [], "finnhub": []}
        self._errors = []
        self._metrics = ThreadSafeDict()

        # Use ThreadPoolExecutor for parallel execution
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}

            # Submit Tiingo fetch if allowed
            if self._can_fetch_tiingo():
                future = executor.submit(
                    self._fetch_source, "tiingo", self._tiingo_adapter, tickers
                )
                futures[future] = "tiingo"
            else:
                logger.debug("Skipping Tiingo fetch (quota or circuit breaker)")

            # Submit Finnhub fetch if allowed
            if self._can_fetch_finnhub():
                future = executor.submit(
                    self._fetch_source, "finnhub", self._finnhub_adapter, tickers
                )
                futures[future] = "finnhub"
            else:
                logger.debug("Skipping Finnhub fetch (quota or circuit breaker)")

            # Collect results as they complete
            for future in as_completed(futures):
                source = futures[future]
                try:
                    articles = future.result()
                    self._results[source] = articles
                    self._metrics.set(f"{source}_count", len(articles))
                    self._record_success(source)
                    logger.debug(
                        "Parallel fetch completed",
                        extra={"source": source, "count": len(articles)},
                    )
                except Exception as e:
                    self._results[source] = []
                    self._metrics.set(f"{source}_count", 0)
                    self._record_failure(source, str(e))
                    self._errors.append(
                        {
                            "source": source,
                            "error": str(e),
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    logger.warning(
                        "Parallel fetch failed",
                        extra={"source": source, "error": str(e)},
                    )

        self._end_time = time.time()

        # Calculate total metrics
        total = sum(len(articles) for articles in self._results.values())
        self._metrics.set("total_count", total)
        self._metrics.set("duration_ms", self._get_duration_ms())

        return self._results

    def _can_fetch_tiingo(self) -> bool:
        """Check if Tiingo fetch is allowed."""
        if not self._tiingo_breaker.can_execute():
            return False
        if not self._quota_tracker.can_call("tiingo"):
            return False
        return True

    def _can_fetch_finnhub(self) -> bool:
        """Check if Finnhub fetch is allowed."""
        if not self._finnhub_breaker.can_execute():
            return False
        if not self._quota_tracker.can_call("finnhub"):
            return False
        return True

    def _fetch_source(
        self, source: str, adapter: Any, tickers: list[str]
    ) -> list[NewsArticle]:
        """Fetch articles from a single source.

        Args:
            source: Source name (tiingo or finnhub)
            adapter: API adapter
            tickers: List of ticker symbols

        Returns:
            List of NewsArticle objects
        """
        # Record quota usage before fetch
        self._quota_tracker.record_call(source, count=1)

        # Fetch news for last 7 days
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)

        articles = adapter.get_news(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            limit=50,
        )

        return articles

    def _record_success(self, source: str) -> None:
        """Record successful fetch to circuit breaker."""
        if source == "tiingo":
            self._tiingo_breaker.record_success()
        elif source == "finnhub":
            self._finnhub_breaker.record_success()

    def _record_failure(self, source: str, error: str) -> None:
        """Record failed fetch to circuit breaker."""
        if source == "tiingo":
            self._tiingo_breaker.record_failure()
        elif source == "finnhub":
            self._finnhub_breaker.record_failure()

    def _get_duration_ms(self) -> float:
        """Get execution duration in milliseconds."""
        if self._start_time is None or self._end_time is None:
            return 0.0
        return (self._end_time - self._start_time) * 1000

    def get_metrics(self) -> dict[str, Any]:
        """Get metrics from the last fetch operation.

        Returns:
            Dict with metrics:
            - tiingo_count: Number of Tiingo articles
            - finnhub_count: Number of Finnhub articles
            - total_count: Total articles fetched
            - duration_ms: Total fetch duration in milliseconds
        """
        return self._metrics.get_all()

    def get_errors(self) -> list[dict[str, Any]]:
        """Get errors from the last fetch operation.

        Returns:
            List of error dicts with source, error message, timestamp
        """
        return list(self._errors)

    def get_results(self) -> dict[str, list[NewsArticle]]:
        """Get results from the last fetch operation.

        Returns:
            Dict mapping source name to list of articles
        """
        return dict(self._results)
