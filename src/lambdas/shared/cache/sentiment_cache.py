"""Sentiment History In-Memory Cache (Feature 1227).

2-tier cache for sentiment history: in-memory (Tier 1) → DynamoDB (Tier 2).
No live API tier — sentiment data is populated by background ingestion,
not fetched on-demand.

Follows the CacheStats pattern from Feature 1224 (cache audit).
"""

import logging
import time

from src.lib.cache_utils import CacheStats, get_global_emitter, jittered_ttl

logger = logging.getLogger(__name__)

# Base TTL: 5 minutes with ±10% jitter
_BASE_TTL_SECONDS = 300

# Module-level CacheStats instance
_sentiment_stats = CacheStats(name="sentiment_history")
get_global_emitter().register(_sentiment_stats)

# In-memory cache: key → (response_data, cached_at_epoch, ttl_seconds)
_cache: dict[str, tuple[dict, float, float]] = {}


def _make_key(ticker: str, source: str, start_date: str, end_date: str) -> str:
    """Build a cache key from query parameters."""
    return f"{ticker}:{source}:{start_date}:{end_date}"


def get_cached_history(
    ticker: str, source: str, start_date: str, end_date: str
) -> dict | None:
    """Check in-memory cache for sentiment history.

    Returns cached response dict if found and not expired, else None.
    Records hit/miss in CacheStats.
    """
    key = _make_key(ticker, source, start_date, end_date)
    entry = _cache.get(key)

    if entry is None:
        _sentiment_stats.record_miss()
        return None

    data, cached_at, ttl = entry
    elapsed = time.monotonic() - cached_at

    if elapsed > ttl:
        # Expired — remove and record miss
        del _cache[key]
        _sentiment_stats.record_miss()
        return None

    _sentiment_stats.record_hit()
    return data


def cache_history(
    ticker: str,
    source: str,
    start_date: str,
    end_date: str,
    response_data: dict,
) -> None:
    """Store sentiment history response in the in-memory cache."""
    key = _make_key(ticker, source, start_date, end_date)
    ttl = jittered_ttl(_BASE_TTL_SECONDS)
    _cache[key] = (response_data, time.monotonic(), ttl)


def clear_cache() -> None:
    """Clear all cached entries. Used by tests."""
    _cache.clear()


def get_sentiment_cache_stats() -> CacheStats:
    """Return the CacheStats instance for external inspection."""
    return _sentiment_stats
