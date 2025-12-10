"""News article collection with automatic failover.

Provides a high-level interface for fetching news from multiple sources
with automatic failover per FR-002.

Architecture:
    fetch_news() --> FailoverOrchestrator --> TiingoAdapter (primary)
                                          --> FinnhubAdapter (secondary)
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from src.lambdas.shared.adapters.base import BaseAdapter, NewsArticle
from src.lambdas.shared.circuit_breaker import CircuitBreakerManager
from src.lambdas.shared.failover import FailoverOrchestrator
from src.lambdas.shared.models.collection_event import CollectionEvent

logger = logging.getLogger(__name__)

# Default lookback period for news fetching (7 days)
DEFAULT_LOOKBACK_DAYS = 7

# Default article limit per fetch
DEFAULT_ARTICLE_LIMIT = 50


@dataclass
class FetchResult:
    """Result of news fetch operation.

    Attributes:
        articles: List of fetched articles
        source_used: Which source provided the articles
        is_failover: True if secondary source was used
        duration_ms: Fetch duration in milliseconds
        error: Error message if fetch failed (both sources)
    """

    articles: list[NewsArticle]
    source_used: Literal["tiingo", "finnhub"] | None
    is_failover: bool
    duration_ms: int
    error: str | None = None


def fetch_news(
    orchestrator: FailoverOrchestrator,
    tickers: list[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    limit: int = DEFAULT_ARTICLE_LIMIT,
) -> FetchResult:
    """Fetch news articles with automatic failover.

    Uses the FailoverOrchestrator to attempt primary source first,
    automatically failing over to secondary if primary fails or times out.

    Args:
        orchestrator: Configured FailoverOrchestrator instance
        tickers: List of stock symbols to fetch news for
        lookback_days: Number of days to look back (default: 7)
        limit: Maximum articles per source (default: 50)

    Returns:
        FetchResult with articles and source attribution

    Example:
        >>> orchestrator = FailoverOrchestrator(tiingo, finnhub, cb_manager)
        >>> result = fetch_news(orchestrator, ["AAPL", "TSLA"])
        >>> if result.is_failover:
        ...     logger.warning(f"Used failover source: {result.source_used}")
    """
    end_date = datetime.now(UTC)
    start_date = end_date - timedelta(days=lookback_days)

    try:
        failover_result = orchestrator.get_news_with_failover(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

        return FetchResult(
            articles=failover_result.data,
            source_used=failover_result.source_used,
            is_failover=failover_result.is_failover,
            duration_ms=failover_result.duration_ms,
        )

    except Exception as e:
        logger.exception(
            "Both sources failed",
            extra={"tickers": tickers, "error": str(e)},
        )
        return FetchResult(
            articles=[],
            source_used=None,
            is_failover=False,
            duration_ms=0,
            error=str(e),
        )


def create_orchestrator(
    primary: BaseAdapter,
    secondary: BaseAdapter,
    circuit_breaker: CircuitBreakerManager,
    timeout_seconds: float = 10.0,
) -> FailoverOrchestrator:
    """Create a configured FailoverOrchestrator.

    Factory function that creates an orchestrator with the given adapters
    and circuit breaker.

    Args:
        primary: Primary data source (e.g., TiingoAdapter)
        secondary: Secondary data source (e.g., FinnhubAdapter)
        circuit_breaker: Circuit breaker manager for state tracking
        timeout_seconds: Timeout before failover (default: 10s per FR-002)

    Returns:
        Configured FailoverOrchestrator instance
    """
    return FailoverOrchestrator(
        primary=primary,
        secondary=secondary,
        circuit_breaker=circuit_breaker,
        timeout_seconds=timeout_seconds,
    )


def create_collection_event(
    event_id: str,
    source_used: Literal["tiingo", "finnhub"] | None,
    is_failover: bool,
) -> CollectionEvent:
    """Create a CollectionEvent for audit tracking.

    Args:
        event_id: Unique identifier for this collection event
        source_used: Which source provided the data
        is_failover: Whether failover occurred

    Returns:
        CollectionEvent for tracking and audit
    """
    return CollectionEvent(
        event_id=event_id,
        triggered_at=datetime.now(UTC),
        status="in_progress",
        source_used=source_used or "tiingo",  # Default to primary
        is_failover=is_failover,
    )
