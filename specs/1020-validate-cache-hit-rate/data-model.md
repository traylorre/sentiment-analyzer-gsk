# Data Model: Cache Metrics Logging

**Feature**: 1020-validate-cache-hit-rate
**Date**: 2025-12-22

---

## Cache Metric Log Entry

Structured JSON log entry for cache performance metrics.

### Schema

```json
{
  "event_type": "cache_metrics",
  "timestamp": "2024-01-15T10:30:00.123456Z",
  "hits": 145,
  "misses": 23,
  "hit_rate": 0.863,
  "entry_count": 42,
  "max_entries": 256,
  "ticker": "AAPL",
  "resolution": "5m",
  "trigger": "periodic",
  "is_cold_start": false,
  "connection_count": 5,
  "lambda_request_id": "abc123-def456"
}
```

### Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `event_type` | string | Yes | Always "cache_metrics" for filtering |
| `timestamp` | ISO8601 | Yes | UTC timestamp of log entry |
| `hits` | int | Yes | Cumulative cache hits since cold start |
| `misses` | int | Yes | Cumulative cache misses since cold start |
| `hit_rate` | float | Yes | hits / (hits + misses), 0.0-1.0 |
| `entry_count` | int | Yes | Current number of cached entries |
| `max_entries` | int | Yes | Maximum entries before LRU eviction |
| `ticker` | string | No | Ticker context if logging per-ticker stats |
| `resolution` | string | No | Resolution context if logging per-resolution stats |
| `trigger` | string | Yes | What triggered this log: "periodic", "threshold", "cold_start" |
| `is_cold_start` | bool | Yes | True if this is first log after Lambda init |
| `connection_count` | int | Yes | Active SSE connections when logged |
| `lambda_request_id` | string | No | AWS request ID for correlation |

### Log Size Estimate

- Base entry: ~250 bytes JSON
- With ticker/resolution: ~300 bytes JSON
- Per-minute at 60s interval: 1 entry × 300 bytes = 300 bytes/minute
- Hourly: 60 entries × 300 bytes = 18KB/hour
- Daily: 432KB/day
- Monthly: ~13MB/month (well within CloudWatch Logs free tier)

---

## Existing CacheStats Model

Located in `src/lib/timeseries/cache.py:29-46`:

```python
@dataclass
class CacheStats:
    """Statistics for cache performance monitoring."""

    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate as hits / total operations."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total

    def reset(self) -> None:
        """Reset all counters to zero."""
        self.hits = 0
        self.misses = 0
```

**No changes needed** - existing model provides all required fields.

---

## ResolutionCache Additions

### Current Interface (no changes)

```python
class ResolutionCache:
    max_entries: int = 256
    stats: CacheStats
    _entries: OrderedDict[tuple[str, Resolution], CacheEntry]
```

### Stats Access Pattern

```python
from src.lib.timeseries.cache import get_global_cache

cache = get_global_cache()
metrics = {
    "hits": cache.stats.hits,
    "misses": cache.stats.misses,
    "hit_rate": cache.stats.hit_rate,
    "entry_count": len(cache._entries),
    "max_entries": cache.max_entries,
}
```

---

## E2E Test Data Model

### CacheMetrics (collected from Lambda logs)

```python
@dataclass
class CacheMetrics:
    """Cache metrics extracted from CloudWatch Logs."""
    timestamp: datetime
    hits: int
    misses: int
    hit_rate: float
    entry_count: int
    trigger: str
    is_cold_start: bool
```

### CachePerformanceReport (E2E test output)

```python
@dataclass
class CachePerformanceReport:
    """Aggregated cache performance over test duration."""
    duration_seconds: float
    total_hits: int
    total_misses: int
    aggregate_hit_rate: float
    min_hit_rate: float
    max_hit_rate: float
    sample_count: int
    cold_start_excluded: bool

    @property
    def meets_target(self) -> bool:
        """SC-008: >80% cache hit rate."""
        return self.aggregate_hit_rate > 0.80
```

---

## CloudWatch Logs Insights Fields

Fields available for querying:

| Field | Filter Example |
|-------|----------------|
| `event_type` | `filter event_type = "cache_metrics"` |
| `hit_rate` | `filter hit_rate < 0.80` |
| `hits` | `stats sum(hits) as total_hits` |
| `misses` | `stats sum(misses) as total_misses` |
| `trigger` | `filter trigger = "threshold"` |
| `is_cold_start` | `filter is_cold_start = false` |
| `@timestamp` | `stats avg(hit_rate) by bin(5m)` |
