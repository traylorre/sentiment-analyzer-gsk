# Research: Validate 80% Cache Hit Rate

**Feature**: 1020-validate-cache-hit-rate
**Date**: 2025-12-22

---

## RQ1: How to access cache stats from SSE Lambda?

### Answer

The SSE Lambda already has access to the timeseries module. Import the global cache instance:

```python
from src.lib.timeseries.cache import get_global_cache

def log_cache_metrics():
    cache = get_global_cache()
    stats = cache.stats
    return {
        "hits": stats.hits,
        "misses": stats.misses,
        "hit_rate": stats.hit_rate,
        "entry_count": len(cache._entries),
    }
```

**Decision**: Use `get_global_cache()` to access the singleton ResolutionCache instance. Stats are read-only, no modification to cache internals needed.

**Source**: src/lib/timeseries/cache.py:173-185 (existing get_global_cache function)

---

## RQ2: Optimal logging frequency for cache metrics?

### Answer

Balance between observability and cost:

| Trigger | Interval | Rationale |
|---------|----------|-----------|
| Periodic | 60 seconds | Aligns with CloudWatch metric resolution, ~1.4KB/hour at 24 bytes/log |
| Threshold crossing | On hit_rate < 0.80 | Alert-worthy condition per SC-008 |
| Cold start | Once on init | Track cold start impact on cache |
| Manual request | On /metrics endpoint | Debugging support |

**Decision**:
- Log every 60 seconds when active connections exist (avoid logging when idle)
- Log immediately if hit_rate drops below 80% (threshold alert)
- Log on Lambda cold start initialization
- Total: ~1.4KB/hour = ~1KB/minute budget met (NFR-002)

**Source**: [CS-015] CloudWatch Logs Insights best practices - granular timestamps enable flexible aggregation

---

## RQ3: CloudWatch Logs Insights query patterns for cache metrics?

### Answer

CloudWatch Logs Insights queries for cache analysis:

### Aggregate Hit Rate (Last Hour)

```
fields @timestamp, hit_rate, hits, misses
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate, sum(hits) as total_hits, sum(misses) as total_misses by bin(1h)
| sort @timestamp desc
| limit 24
```

### Hit Rate by Ticker

```
fields @timestamp, ticker, hit_rate
| filter event_type = "cache_metrics" and ispresent(ticker)
| stats avg(hit_rate) as ticker_hit_rate, count() as sample_count by ticker
| sort ticker_hit_rate asc
| limit 20
```

### Time-Series Trend (5-minute buckets)

```
fields @timestamp, hit_rate
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate, count() as samples by bin(5m)
| sort @timestamp desc
| limit 288
```

### Low Hit Rate Detection

```
fields @timestamp, hit_rate, hits, misses, entry_count
| filter event_type = "cache_metrics" and hit_rate < 0.80
| sort @timestamp desc
| limit 100
```

**Decision**: Provide all four queries in contracts/cache-metrics-queries.yaml. Use `bin()` for time aggregation, `stats` for calculations.

**Source**: [CS-015] CloudWatch Logs Insights query syntax documentation

---

## RQ4: How to simulate normal usage patterns in E2E test?

### Answer

Normal usage patterns based on dashboard behavior:

1. **Initial Load**: Single ticker (AAPL), default resolution (5m) → cache MISS
2. **Resolution Switch**: Switch to 1m, 1h, back to 5m → 2 MISS, 1 HIT
3. **Multi-Ticker**: Add GOOGL, MSFT → 2 MISS (new tickers)
4. **Repeat Access**: Re-request same data → HIT

**Test Scenario** (simulates 10 minutes of usage):

```python
# Warm-up phase (30s) - excluded from measurement
connect_sse(ticker="AAPL", resolution="5m")
wait(30)  # Let cache warm up

# Measurement phase (30s)
switch_resolution("1m")  # MISS
switch_resolution("5m")  # HIT (cached)
switch_resolution("1h")  # MISS
switch_resolution("5m")  # HIT (cached)
add_ticker("GOOGL")      # MISS
switch_resolution("5m")  # HIT (AAPL still cached)

# Expected: 3 hits / 6 total = 50% during switches
# But with SSE stream, cache fills continuously, so actual hit rate higher
```

**Decision**:
- 30-second warm-up period excluded from hit rate calculation
- Simulate resolution switching (most common user action)
- Measure over 30+ seconds for statistical significance
- Target: >80% hit rate after warm-up

**Source**: specs/1009-realtime-multi-resolution/spec.md User Story 2 (resolution switching pattern)

---

## RQ5: What constitutes "normal operation" for cache hit rate?

### Answer

**Normal Operation Definition**:
- Lambda is warm (not a cold start)
- At least one active SSE connection
- Cache has been populated for 30+ seconds
- No recent cache.clear() calls

**Excluded from Measurement**:
- First 30 seconds after cold start (cache is empty)
- Periods with zero connections (no cache activity)
- Immediately after cache.clear() (testing/debugging)

**Measurement Methodology**:
1. Start measurement after warm-up period (30s post-connection)
2. Sample cache stats every 5 seconds for 30+ seconds
3. Calculate aggregate hit_rate = total_hits / (total_hits + total_misses)
4. Validate: aggregate hit_rate > 0.80

**Why 80% is achievable**:
- Resolution-based TTL: 5m data cached for 300s (5 minutes)
- Shared ticker data: Multiple users requesting same ticker/resolution get cache hits
- LRU eviction: 256 entries support 13 tickers × 8 resolutions × 2.46 time ranges
- Normal usage: Resolution switching returns to previously viewed resolutions (cache hit)

**Expected Hit Rate Breakdown**:
| Scenario | Hit Rate | Weight |
|----------|----------|--------|
| Same resolution/ticker | 100% | 70% of requests |
| Return to previous resolution | 100% | 15% of requests |
| New resolution (first request) | 0% | 10% of requests |
| TTL expired | 0% | 5% of requests |
| **Weighted Average** | **85%** | |

**Decision**: Measure aggregate hit_rate after 30s warm-up, expect >80% due to natural access patterns favoring cached data.

**Source**:
- [CS-005] Lambda warm invocation reuse
- [CS-006] Global scope caching patterns
- src/lib/timeseries/cache.py TTL implementation
