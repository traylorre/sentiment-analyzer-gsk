# Cache Performance Guide

**Feature**: 1020-validate-cache-hit-rate
**Success Criterion**: SC-008 - Cache hit rate >80% during normal operation

---

## Overview

The ResolutionCache provides in-memory caching of time-series sentiment data in the SSE Lambda's global scope. This guide explains cache behavior, tuning, and troubleshooting.

## How the Cache Works

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Lambda Execution Environment (warm)                             │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Global Scope (persists across invocations)              │   │
│  │                                                         │   │
│  │  ResolutionCache                                        │   │
│  │  ├─ max_entries: 256                                   │   │
│  │  ├─ _entries: OrderedDict[(ticker, resolution), Entry] │   │
│  │  └─ stats: CacheStats(hits, misses)                    │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Handler Scope (per invocation)                          │   │
│  │                                                         │   │
│  │  cache = get_global_cache()  # Returns singleton        │   │
│  │  data = cache.get(ticker, resolution)                   │   │
│  │  if data is None:                                       │   │
│  │      data = fetch_from_dynamodb(...)                    │   │
│  │      cache.set(ticker, resolution, data=data)           │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### TTL Behavior

Cache entries expire based on their resolution's duration:

| Resolution | Duration | TTL (seconds) | Why |
|------------|----------|---------------|-----|
| 1 minute | 60s | 60 | Data changes every minute |
| 5 minutes | 300s | 300 | Data valid for 5 minutes |
| 10 minutes | 600s | 600 | Data valid for 10 minutes |
| 1 hour | 3600s | 3600 | Hourly aggregates stable |
| 3 hours | 10800s | 10800 | Multi-hour aggregates stable |
| 6 hours | 21600s | 21600 | Extended aggregates |
| 12 hours | 43200s | 43200 | Half-day aggregates |
| 24 hours | 86400s | 86400 | Daily aggregates |

**Rationale**: TTL equals resolution duration because data is complete/stable once the time bucket closes. A 5-minute bucket's data doesn't change after the 5-minute period ends.

### LRU Eviction

When the cache reaches `max_entries` (default 256), the **least recently used** entry is evicted:

```python
# Eviction happens on cache.set()
while len(self._entries) >= self.max_entries:
    self._entries.popitem(last=False)  # Remove oldest
```

**Capacity Planning**:
- 13 tickers × 8 resolutions = 104 key combinations
- 256 entries supports ~2.5 time ranges per (ticker, resolution)
- For 26 tickers, increase `max_entries` to 512

### Access Pattern

On `cache.get()`:
1. Look up key `(ticker, resolution)`
2. If found, check TTL → if expired, delete and return None (miss)
3. If found and valid, update `last_accessed`, move to end (LRU), return data (hit)
4. If not found, return None (miss)

---

## Cold Start Impact

### What Happens on Cold Start

1. Lambda starts fresh → cache is empty
2. First requests for each (ticker, resolution) are **all misses**
3. Cache gradually warms as data is fetched
4. After ~30 seconds, hit rate stabilizes

### Expected Cold Start Hit Rate

| Time Since Start | Expected Hit Rate | Notes |
|------------------|-------------------|-------|
| 0-10 seconds | 0-20% | Initial fetches, mostly misses |
| 10-20 seconds | 20-50% | Some repeat requests |
| 20-30 seconds | 50-70% | Cache warming |
| 30+ seconds | 80%+ | Steady state (target met) |

### Mitigating Cold Starts

1. **Provisioned Concurrency**: Keep Lambda warm with minimum instances
2. **Pre-warming**: Add a warmup endpoint that fetches common data
3. **Exclude from measurement**: E2E tests exclude first 30 seconds

---

## Hit Rate Analysis

### What Affects Hit Rate

| Factor | Impact | Solution |
|--------|--------|----------|
| Cold starts | Reduces hit rate | Provisioned concurrency |
| Short TTL (1m, 5m) | Data expires faster | Accept as expected |
| Many tickers | More cache pressure | Increase max_entries |
| Low traffic | Less cache sharing | Expected behavior |
| Cache thrashing | Constant eviction | Increase max_entries |

### Expected Breakdown

Under normal operation with 13 tickers and multiple users:

| Access Pattern | Probability | Hit Rate | Contribution |
|----------------|-------------|----------|--------------|
| Same ticker/resolution | 70% | 100% | 70% |
| Return to previous | 15% | 100% | 15% |
| New resolution (first) | 10% | 0% | 0% |
| TTL expired | 5% | 0% | 0% |
| **Total Expected** | 100% | - | **85%** |

---

## CloudWatch Logs Insights Queries

### Aggregate Hit Rate (Last Hour)

```
fields @timestamp, hit_rate, hits, misses
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate,
        sum(hits) as total_hits,
        sum(misses) as total_misses
        by bin(1h)
| sort @timestamp desc
| limit 24
```

### Hit Rate by Ticker

```
fields @timestamp, ticker, hit_rate
| filter event_type = "cache_metrics" and ispresent(ticker)
| stats avg(hit_rate) as ticker_hit_rate by ticker
| sort ticker_hit_rate asc
```

### Low Hit Rate Detection

```
fields @timestamp, hit_rate, is_cold_start, trigger
| filter event_type = "cache_metrics" and hit_rate < 0.80
| sort @timestamp desc
| limit 100
```

### Cold Start vs Warm Comparison

```
fields @timestamp, hit_rate, is_cold_start
| filter event_type = "cache_metrics"
| stats avg(hit_rate) as avg_hit_rate by is_cold_start
```

See full query library: `specs/1020-validate-cache-hit-rate/contracts/cache-metrics-queries.yaml`

---

## Troubleshooting

### Symptom: hit_rate < 80%

**Step 1: Check for cold starts**

```
# Run in CloudWatch Logs Insights
fields @timestamp, is_cold_start, hit_rate
| filter event_type = "cache_metrics"
| stats count() by is_cold_start
```

If many cold starts → consider provisioned concurrency.

**Step 2: Check cache utilization**

```
fields @timestamp, entry_count, max_entries
| filter event_type = "cache_metrics"
| stats max(entry_count) as peak
```

If `peak >= max_entries` → cache is full, increase `max_entries`.

**Step 3: Check ticker distribution**

```
fields ticker, hit_rate
| filter event_type = "cache_metrics" and ispresent(ticker)
| stats avg(hit_rate) by ticker
| sort hit_rate asc
```

If one ticker has low hit rate → unusual access pattern for that ticker.

**Step 4: Check time of day**

```
fields @timestamp, hit_rate
| filter event_type = "cache_metrics"
| stats avg(hit_rate) by bin(1h)
```

Low hit rate during off-hours is expected (fewer users = less cache sharing).

### Symptom: Cache thrashing

**Signs**: `entry_count` constantly at `max_entries`, frequent evictions.

**Causes**:
1. Too many tickers (more than 13)
2. Users accessing many different time ranges
3. `max_entries` too low

**Solution**: Increase `max_entries` in ResolutionCache:

```python
# src/lib/timeseries/cache.py
class ResolutionCache:
    def __init__(self, max_entries: int = 512):  # Increase from 256
        ...
```

### Symptom: Metrics not appearing in logs

**Check 1**: Lambda has correct log group

```bash
aws logs describe-log-groups --log-group-name-prefix "/aws/lambda/sse-streaming"
```

**Check 2**: Cache logger is initialized

```python
# stream.py should have:
from cache_logger import CacheMetricsLogger, log_cold_start_metrics
```

**Check 3**: Event type filter is correct

```
fields @message
| filter @message like /cache_metrics/
| limit 10
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SSE_HEARTBEAT_INTERVAL` | 30 | Heartbeat frequency (cache logged alongside) |

### Cache Parameters

| Parameter | Default | Location |
|-----------|---------|----------|
| `max_entries` | 256 | `src/lib/timeseries/cache.py:91` |
| `interval_seconds` | 60 | `src/lambdas/sse_streaming/stream.py:169` |

---

## References

- **Canonical Sources**:
  - [CS-005] AWS Lambda Best Practices - Global scope caching
  - [CS-006] Yan Cui - Warm invocation caching
  - [CS-015] CloudWatch Logs Insights Query Syntax

- **Related Documentation**:
  - [Parent Spec](../specs/1009-realtime-multi-resolution/spec.md) - SC-008 definition
  - [Cache Queries](../specs/1020-validate-cache-hit-rate/contracts/cache-metrics-queries.yaml)
  - [Quickstart](../specs/1020-validate-cache-hit-rate/quickstart.md)
