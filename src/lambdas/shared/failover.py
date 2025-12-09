"""Failover orchestrator for multi-source data collection.

Provides automatic failover from primary to secondary data sources with:
- 10-second timeout for failover trigger (FR-002)
- Integration with existing CircuitBreakerManager
- Source attribution tracking

Architecture:
    FailoverOrchestrator --> TiingoAdapter (primary, priority 1)
                        --> FinnhubAdapter (secondary, priority 2)
                        --> CircuitBreakerManager (state tracking)
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, TypeVar

from src.lambdas.shared.adapters.base import AdapterError, BaseAdapter
from src.lambdas.shared.circuit_breaker import CircuitBreakerManager
from src.lambdas.shared.models.data_source import DataSourceConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Default timeout before failover (10 seconds per FR-002)
DEFAULT_FAILOVER_TIMEOUT_SECONDS = 10


@dataclass
class FailoverResult:
    """Result of a failover-protected operation.

    Attributes:
        data: The result data (e.g., list of NewsArticle)
        source_used: Which source provided the data
        is_failover: True if secondary source was used due to primary failure
        duration_ms: Total operation duration in milliseconds
        primary_error: Error from primary source if failover occurred
    """

    data: Any
    source_used: Literal["tiingo", "finnhub"]
    is_failover: bool
    duration_ms: int
    primary_error: str | None = None


class FailoverOrchestrator:
    """Orchestrates failover between primary and secondary data sources.

    Implements FR-002: Automatic failover from Tiingo to Finnhub within 10 seconds.

    Usage:
        orchestrator = FailoverOrchestrator(
            primary=tiingo_adapter,
            secondary=finnhub_adapter,
            circuit_breaker=CircuitBreakerManager(table)
        )

        result = orchestrator.get_news_with_failover(
            tickers=["AAPL", "TSLA"],
            limit=50
        )

        if result.is_failover:
            logger.warning(f"Used {result.source_used} due to: {result.primary_error}")
    """

    def __init__(
        self,
        primary: BaseAdapter,
        secondary: BaseAdapter,
        circuit_breaker: CircuitBreakerManager,
        timeout_seconds: float = DEFAULT_FAILOVER_TIMEOUT_SECONDS,
    ):
        """Initialize failover orchestrator.

        Args:
            primary: Primary data source adapter (e.g., TiingoAdapter)
            secondary: Secondary data source adapter (e.g., FinnhubAdapter)
            circuit_breaker: Circuit breaker manager for state tracking
            timeout_seconds: Timeout before triggering failover (default: 10s)
        """
        self._primary = primary
        self._secondary = secondary
        self._circuit_breaker = circuit_breaker
        self._timeout_seconds = timeout_seconds

        # Track source configs
        self._primary_config = DataSourceConfig.tiingo_default()
        self._secondary_config = DataSourceConfig.finnhub_default()

    def get_news_with_failover(
        self,
        tickers: list[str],
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> FailoverResult:
        """Fetch news with automatic failover on primary failure.

        Attempts primary source first. If it fails or times out within
        timeout_seconds, automatically fails over to secondary source.

        Args:
            tickers: List of stock symbols
            start_date: Start date for news
            end_date: End date for news
            limit: Maximum articles to return

        Returns:
            FailoverResult with data and source attribution

        Raises:
            AdapterError: If both sources fail
        """
        start_time = time.time()
        primary_source: Literal["tiingo", "finnhub"] = self._primary.source_name
        secondary_source: Literal["tiingo", "finnhub"] = self._secondary.source_name

        # Check if primary circuit is open
        if not self._circuit_breaker.can_execute(primary_source):
            logger.info(
                "Primary source circuit open, using secondary",
                extra={"primary": primary_source, "secondary": secondary_source},
            )
            return self._fetch_from_secondary(
                tickers,
                start_date,
                end_date,
                limit,
                start_time,
                primary_error="Circuit breaker open",
            )

        # Try primary source
        try:
            articles = self._fetch_with_timeout(
                lambda: self._primary.get_news(tickers, start_date, end_date, limit),
                self._timeout_seconds,
            )
            duration_ms = int((time.time() - start_time) * 1000)

            # Record success
            self._circuit_breaker.record_success(primary_source)
            self._primary_config = self._primary_config.record_success(
                datetime.now(UTC)
            )

            logger.debug(
                "Primary source succeeded",
                extra={
                    "source": primary_source,
                    "articles": len(articles),
                    "duration_ms": duration_ms,
                },
            )

            return FailoverResult(
                data=articles,
                source_used=primary_source,
                is_failover=False,
                duration_ms=duration_ms,
            )

        except TimeoutError:
            error_msg = f"Primary source timed out after {self._timeout_seconds}s"
            logger.warning(
                error_msg,
                extra={"source": primary_source, "tickers": tickers},
            )
            self._circuit_breaker.record_failure(primary_source)
            self._primary_config = self._primary_config.record_failure(
                datetime.now(UTC)
            )
            return self._fetch_from_secondary(
                tickers,
                start_date,
                end_date,
                limit,
                start_time,
                primary_error=error_msg,
            )

        except AdapterError as e:
            error_msg = f"Primary source error: {e}"
            logger.warning(
                error_msg,
                extra={"source": primary_source, "error": str(e)},
            )
            self._circuit_breaker.record_failure(primary_source)
            self._primary_config = self._primary_config.record_failure(
                datetime.now(UTC)
            )
            return self._fetch_from_secondary(
                tickers,
                start_date,
                end_date,
                limit,
                start_time,
                primary_error=error_msg,
            )

        except Exception as e:
            error_msg = f"Primary source unexpected error: {e}"
            logger.exception(
                error_msg,
                extra={"source": primary_source},
            )
            self._circuit_breaker.record_failure(primary_source)
            self._primary_config = self._primary_config.record_failure(
                datetime.now(UTC)
            )
            return self._fetch_from_secondary(
                tickers,
                start_date,
                end_date,
                limit,
                start_time,
                primary_error=error_msg,
            )

    def _fetch_from_secondary(
        self,
        tickers: list[str],
        start_date: datetime | None,
        end_date: datetime | None,
        limit: int,
        start_time: float,
        primary_error: str,
    ) -> FailoverResult:
        """Fetch from secondary source after primary failure.

        Args:
            tickers: List of stock symbols
            start_date: Start date
            end_date: End date
            limit: Max articles
            start_time: Operation start timestamp
            primary_error: Error message from primary source

        Returns:
            FailoverResult with secondary source attribution

        Raises:
            AdapterError: If secondary source also fails
        """
        secondary_source: Literal["tiingo", "finnhub"] = self._secondary.source_name

        # Check secondary circuit
        if not self._circuit_breaker.can_execute(secondary_source):
            raise AdapterError(
                f"Both sources unavailable. Primary: {primary_error}, "
                f"Secondary: Circuit breaker open"
            )

        try:
            articles = self._secondary.get_news(tickers, start_date, end_date, limit)
            duration_ms = int((time.time() - start_time) * 1000)

            # Record success
            self._circuit_breaker.record_success(secondary_source)
            self._secondary_config = self._secondary_config.record_success(
                datetime.now(UTC)
            )

            logger.info(
                "Failover to secondary succeeded",
                extra={
                    "source": secondary_source,
                    "articles": len(articles),
                    "duration_ms": duration_ms,
                    "primary_error": primary_error,
                },
            )

            return FailoverResult(
                data=articles,
                source_used=secondary_source,
                is_failover=True,
                duration_ms=duration_ms,
                primary_error=primary_error,
            )

        except AdapterError as e:
            self._circuit_breaker.record_failure(secondary_source)
            self._secondary_config = self._secondary_config.record_failure(
                datetime.now(UTC)
            )
            raise AdapterError(
                f"Both sources failed. Primary: {primary_error}, "
                f"Secondary: {secondary_source} error: {e}"
            ) from e

    def _fetch_with_timeout(
        self, fetch_fn: Callable[[], T], timeout_seconds: float
    ) -> T:
        """Execute fetch function with timeout.

        Note: This is a simplified timeout implementation.
        For production, consider using concurrent.futures.ThreadPoolExecutor
        with timeout, or asyncio with timeout.

        Args:
            fetch_fn: Function to execute
            timeout_seconds: Maximum execution time

        Returns:
            Result from fetch_fn

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        # Note: In a Lambda context with synchronous adapters,
        # we rely on the adapter's internal timeout (requests timeout).
        # This provides an additional check on overall operation time.
        start = time.time()
        result = fetch_fn()
        elapsed = time.time() - start

        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Operation took {elapsed:.1f}s, exceeded {timeout_seconds}s"
            )

        return result

    @property
    def primary_config(self) -> DataSourceConfig:
        """Get primary source configuration."""
        return self._primary_config

    @property
    def secondary_config(self) -> DataSourceConfig:
        """Get secondary source configuration."""
        return self._secondary_config
