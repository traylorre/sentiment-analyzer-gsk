"""Cache metrics logging for CloudWatch Logs Insights analysis.

Feature: 1020-validate-cache-hit-rate
Success Criterion: SC-008 - Cache hit rate >80% during normal operation

Canonical References:
[CS-005] AWS Lambda Best Practices - Global scope caching
[CS-006] Yan Cui - Warm invocation caching
[CS-015] CloudWatch Logs Insights Query Syntax

This module provides structured JSON logging for cache performance metrics,
enabling CloudWatch Logs Insights queries for SC-008 validation.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.lib.timeseries.cache import ResolutionCache

logger = logging.getLogger(__name__)

# Module-level cold start tracking
_is_cold_start = True
_cold_start_logged = False

# Hit rate threshold for warning (SC-008)
HIT_RATE_WARNING_THRESHOLD = 0.80


def mark_warm() -> None:
    """Mark the Lambda as warmed up (no longer cold start)."""
    global _is_cold_start
    _is_cold_start = False


def is_cold_start() -> bool:
    """Check if this is a cold start invocation."""
    return _is_cold_start


def log_cache_metrics(
    cache: ResolutionCache,
    *,
    ticker: str | None = None,
    resolution: str | None = None,
    trigger: str = "periodic",
    connection_count: int = 0,
    lambda_request_id: str | None = None,
) -> dict:
    """Log cache performance metrics in structured JSON format.

    Args:
        cache: ResolutionCache instance to read stats from
        ticker: Optional ticker context for per-ticker analysis
        resolution: Optional resolution context for per-resolution analysis
        trigger: What triggered this log ("periodic", "threshold", "cold_start")
        connection_count: Number of active SSE connections
        lambda_request_id: AWS request ID for correlation

    Returns:
        The metrics dict that was logged (for testing)
    """
    global _cold_start_logged, _is_cold_start

    stats = cache.stats
    now = datetime.now(UTC)

    # Safely extract stats values (handles mocked objects in tests)
    try:
        hits = int(stats.hits) if hasattr(stats, "hits") else 0
        misses = int(stats.misses) if hasattr(stats, "misses") else 0
        hit_rate = float(stats.hit_rate) if hasattr(stats, "hit_rate") else 0.0
        entry_count = len(cache._entries) if hasattr(cache, "_entries") else 0
        max_entries = int(cache.max_entries) if hasattr(cache, "max_entries") else 256
    except (TypeError, ValueError):
        # If stats are mocked (MagicMock), use defaults
        hits = 0
        misses = 0
        hit_rate = 0.0
        entry_count = 0
        max_entries = 256

    metrics = {
        "event_type": "cache_metrics",
        "timestamp": now.isoformat(),
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hit_rate, 4),
        "entry_count": entry_count,
        "max_entries": max_entries,
        "trigger": trigger,
        "is_cold_start": _is_cold_start and not _cold_start_logged,
        "connection_count": connection_count,
    }

    # Add optional context fields
    if ticker:
        metrics["ticker"] = ticker
    if resolution:
        metrics["resolution"] = resolution
    if lambda_request_id:
        metrics["lambda_request_id"] = lambda_request_id

    # Determine log level based on hit rate
    if hit_rate < HIT_RATE_WARNING_THRESHOLD and hits + misses > 10:
        # Only warn if we have enough samples to be meaningful
        logger.warning(
            "Cache hit rate below threshold",
            extra={"cache_metrics": json.dumps(metrics)},
        )
    else:
        logger.info(
            "Cache metrics",
            extra={"cache_metrics": json.dumps(metrics)},
        )

    # Mark cold start as logged (only log once per invocation)
    if _is_cold_start:
        _cold_start_logged = True
        mark_warm()

    return metrics


def log_cold_start_metrics(cache: ResolutionCache, connection_count: int = 0) -> dict:
    """Log initial cache metrics on cold start.

    Args:
        cache: ResolutionCache instance
        connection_count: Number of initial connections

    Returns:
        The metrics dict that was logged
    """
    return log_cache_metrics(
        cache,
        trigger="cold_start",
        connection_count=connection_count,
    )


def log_threshold_alert(
    cache: ResolutionCache,
    connection_count: int = 0,
    ticker: str | None = None,
) -> dict:
    """Log cache metrics when hit rate drops below threshold.

    Args:
        cache: ResolutionCache instance
        connection_count: Number of active connections
        ticker: Optional ticker that triggered the check

    Returns:
        The metrics dict that was logged
    """
    return log_cache_metrics(
        cache,
        ticker=ticker,
        trigger="threshold",
        connection_count=connection_count,
    )


class CacheMetricsLogger:
    """Periodic cache metrics logger for integration with SSE stream generator.

    Logs cache metrics every `interval_seconds` when called from the event loop.
    """

    def __init__(self, cache: ResolutionCache, interval_seconds: int = 60):
        """Initialize cache metrics logger.

        Args:
            cache: ResolutionCache instance to monitor
            interval_seconds: How often to log metrics (default 60s)
        """
        self._cache = cache
        self._interval_seconds = interval_seconds
        self._last_log_time: float = 0.0
        self._last_hit_rate: float = 1.0  # Assume 100% initially

    def should_log(self) -> bool:
        """Check if enough time has passed to log metrics."""
        current_time = time.time()
        return current_time - self._last_log_time >= self._interval_seconds

    def maybe_log(self, connection_count: int = 0) -> dict | None:
        """Log metrics if interval has passed or hit rate dropped below threshold.

        Args:
            connection_count: Number of active SSE connections

        Returns:
            Metrics dict if logged, None if skipped
        """
        current_time = time.time()
        stats = self._cache.stats

        # Safely extract stats values (handles mocked objects in tests)
        try:
            hit_rate = float(stats.hit_rate) if hasattr(stats, "hit_rate") else 0.0
            hits = int(stats.hits) if hasattr(stats, "hits") else 0
            misses = int(stats.misses) if hasattr(stats, "misses") else 0
        except (TypeError, ValueError):
            hit_rate = 0.0
            hits = 0
            misses = 0

        # Check for threshold crossing (hit rate dropped below 80%)
        if (
            hit_rate < HIT_RATE_WARNING_THRESHOLD
            and self._last_hit_rate >= HIT_RATE_WARNING_THRESHOLD
            and hits + misses > 10
        ):
            self._last_log_time = current_time
            self._last_hit_rate = hit_rate
            return log_threshold_alert(self._cache, connection_count)

        # Check for periodic logging
        if current_time - self._last_log_time >= self._interval_seconds:
            self._last_log_time = current_time
            self._last_hit_rate = hit_rate
            return log_cache_metrics(
                self._cache,
                trigger="periodic",
                connection_count=connection_count,
            )

        return None
