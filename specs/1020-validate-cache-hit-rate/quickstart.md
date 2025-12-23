# Quickstart: Validate Cache Hit Rate

**Feature**: 1020-validate-cache-hit-rate
**Success Criterion**: SC-008 - Cache hit rate >80% during normal operation

---

## Quick Validation

### 1. Run E2E Test

```bash
# From sentiment-analyzer-gsk repo root
pytest tests/e2e/test_cache_hit_rate.py -v

# Expected output:
# test_cache_hit_rate_exceeds_80_percent PASSED
# test_cache_metrics_logged_to_cloudwatch PASSED
```

### 2. Query CloudWatch Logs (Manual)

```bash
# Get aggregate hit rate for last hour
aws logs start-query \
  --log-group-name "/aws/lambda/sse-streaming-preprod" \
  --start-time $(date -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, hit_rate | filter event_type = "cache_metrics" | stats avg(hit_rate) as avg_hit_rate'

# Wait 5 seconds, then get results
aws logs get-query-results --query-id <QUERY_ID>

# Expected: avg_hit_rate > 0.80
```

---

## Understanding Cache Behavior

### How the Cache Works

1. **Resolution-Based TTL**: Each cached entry expires based on its resolution
   - 1-minute resolution → 60 second TTL
   - 5-minute resolution → 300 second TTL
   - 1-hour resolution → 3600 second TTL

2. **LRU Eviction**: When cache reaches 256 entries, oldest entries are evicted

3. **Per-Ticker/Resolution Keys**: Cache key is `(ticker, resolution)` tuple

### Why 80% is the Target

- **First request**: Always a cache miss (0% hit rate)
- **Subsequent requests for same data**: 100% hit rate
- **Resolution switching**: First view of new resolution is miss, returns are hits
- **Typical usage pattern**: 70% same-data, 15% return visits, 15% new requests = ~85% expected

### Cold Start Impact

- Fresh Lambda invocation has empty cache
- First 30 seconds show ~0% hit rate
- After warm-up, hit rate stabilizes >80%
- E2E test excludes first 30 seconds from measurement

---

## Troubleshooting Low Hit Rate

### Symptom: hit_rate < 0.80

**Check 1: Cold starts**
```
# Query for cold start frequency
fields @timestamp, is_cold_start
| filter event_type = "cache_metrics"
| stats count() by is_cold_start
```
- If many cold starts, consider provisioned concurrency

**Check 2: Cache thrashing (full cache)**
```
# Query for cache utilization
fields @timestamp, entry_count, max_entries
| filter event_type = "cache_metrics"
| stats max(entry_count) as peak by bin(1h)
```
- If entry_count consistently at 256, increase max_entries

**Check 3: TTL too short**
- Short resolution data (1m, 5m) expires quickly
- Users accessing same data after TTL expires → miss
- Solution: Pre-warm cache or increase user activity

**Check 4: Low traffic**
- Few users = less cache sharing = lower hit rate
- Expected behavior for low-traffic periods

---

## CloudWatch Logs Insights Queries

Full query library in: `specs/1020-validate-cache-hit-rate/contracts/cache-metrics-queries.yaml`

### Most Useful Queries

1. **Aggregate Hit Rate** - Overall performance check
2. **Hit Rate by Ticker** - Find problematic tickers
3. **Cold Start Impact** - Quantify cold start effect
4. **Low Hit Rate Events** - Investigate failures

---

## Related Documentation

- [Cache Performance Guide](../../../docs/cache-performance.md) - Full documentation
- [Parent Spec](../1009-realtime-multi-resolution/spec.md) - SC-008 definition
- [ResolutionCache Source](../../../src/lib/timeseries/cache.py) - Implementation
