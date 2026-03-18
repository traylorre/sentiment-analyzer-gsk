"""Shared cache utilities for TTL jitter, statistics tracking, and metric emission.

Provides lightweight helpers used across all 12 caches in the application.
Each cache retains its own interface — these utilities standardize the
common patterns (jitter, stats, metrics) without imposing a base class.
"""

import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

CACHE_JITTER_PCT = float(os.environ.get("CACHE_JITTER_PCT", "0.1"))
CACHE_METRICS_FLUSH_INTERVAL = int(os.environ.get("CACHE_METRICS_FLUSH_INTERVAL", "60"))


def jittered_ttl(base_ttl: float, jitter_pct: float | None = None) -> float:
    """Return TTL with uniform random jitter applied.

    Spreads cache expiry times across instances to prevent thundering herd.
    For a base_ttl of 60s with 10% jitter, returns a value in [54, 66].

    Args:
        base_ttl: Base TTL in seconds (must be > 0).
        jitter_pct: Jitter percentage as a decimal (0.1 = ±10%).
            Defaults to CACHE_JITTER_PCT env var (0.1).

    Returns:
        Jittered TTL in seconds.
    """
    if base_ttl <= 0:
        return base_ttl
    if jitter_pct is None:
        jitter_pct = CACHE_JITTER_PCT
    return base_ttl * random.uniform(1.0 - jitter_pct, 1.0 + jitter_pct)  # noqa: S311


def validate_non_empty(data: object, cache_name: str) -> None:
    """Validate that cache data is non-empty before accepting a refresh.

    Rejects None, empty dicts, empty lists, and empty strings.
    Prevents replacing valid cached data with empty/corrupted upstream responses.

    Args:
        data: The data to validate.
        cache_name: Name of the cache (for error messages).

    Raises:
        ValueError: If data is empty or None.
    """
    if data is None:
        raise ValueError(f"Cache '{cache_name}': received None data, rejecting refresh")
    if isinstance(data, dict | list | str) and len(data) == 0:
        raise ValueError(
            f"Cache '{cache_name}': received empty {type(data).__name__}, "
            "rejecting refresh"
        )


@dataclass
class CacheStats:
    """Thread-safe hit/miss/eviction counter for a single named cache."""

    name: str
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    refresh_failures: int = 0
    last_flush_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_hit(self) -> None:
        with self._lock:
            self.hits += 1

    def record_miss(self) -> None:
        with self._lock:
            self.misses += 1

    def record_eviction(self) -> None:
        with self._lock:
            self.evictions += 1

    def record_refresh_failure(self) -> None:
        with self._lock:
            self.refresh_failures += 1

    def flush(self) -> dict[str, int]:
        """Return current counts and reset to zero. Thread-safe."""
        with self._lock:
            snapshot = {
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "refresh_failures": self.refresh_failures,
            }
            self.hits = 0
            self.misses = 0
            self.evictions = 0
            self.refresh_failures = 0
            self.last_flush_at = time.time()
            return snapshot

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate (0.0-1.0). Returns 0.0 if no accesses."""
        with self._lock:
            total = self.hits + self.misses
            if total == 0:
                return 0.0
            return self.hits / total


class CacheMetricEmitter:
    """Accumulates CacheStats and flushes to CloudWatch periodically.

    Designed to batch metrics from all caches into a single CloudWatch
    API call, keeping costs low (~$3.60/month for 12 caches).
    """

    def __init__(self, flush_interval: int | None = None) -> None:
        self._stats: dict[str, CacheStats] = {}
        self._lock = threading.Lock()
        self._flush_interval = (
            flush_interval
            if flush_interval is not None
            else CACHE_METRICS_FLUSH_INTERVAL
        )
        self._last_flush = time.time()

    def register(self, stats: CacheStats) -> None:
        """Register a CacheStats instance for periodic flushing."""
        with self._lock:
            self._stats[stats.name] = stats

    def get_stats(self, name: str) -> CacheStats | None:
        """Get a registered CacheStats by name."""
        with self._lock:
            return self._stats.get(name)

    def should_flush(self) -> bool:
        """Check if enough time has elapsed since last flush."""
        return (time.time() - self._last_flush) >= self._flush_interval

    def flush(self) -> list[dict]:
        """Flush all registered stats to a list of metric dicts.

        Returns a list compatible with emit_metrics_batch().
        Resets all counters after flushing.
        """
        metrics: list[dict] = []
        with self._lock:
            for name, stats in self._stats.items():
                snapshot = stats.flush()
                for metric_name, value in snapshot.items():
                    if value > 0:
                        metrics.append(
                            {
                                "name": f"Cache/{metric_name.replace('_', '').title()}",
                                "value": float(value),
                                "unit": "Count",
                                "dimensions": {"Cache": name},
                            }
                        )
            self._last_flush = time.time()
        return metrics

    def flush_to_cloudwatch(self) -> None:
        """Flush metrics to CloudWatch if interval has elapsed.

        Imports emit_metrics_batch lazily to avoid circular imports.
        Silently handles emission failures (metrics should never break requests).
        """
        if not self.should_flush():
            return
        metrics = self.flush()
        if not metrics:
            return
        try:
            from src.lib.metrics import emit_metrics_batch

            emit_metrics_batch(metrics)
        except Exception:
            logger.debug("Failed to emit cache metrics to CloudWatch", exc_info=True)


# Global emitter singleton
_global_emitter: CacheMetricEmitter | None = None
_emitter_lock = threading.Lock()


def get_global_emitter() -> CacheMetricEmitter:
    """Get or create the global CacheMetricEmitter singleton."""
    global _global_emitter
    if _global_emitter is None:
        with _emitter_lock:
            if _global_emitter is None:
                _global_emitter = CacheMetricEmitter()
    return _global_emitter


def reset_global_emitter() -> None:
    """Reset the global emitter (for testing)."""
    global _global_emitter
    with _emitter_lock:
        _global_emitter = None
