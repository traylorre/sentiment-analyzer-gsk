# Cache Metrics Contract

**Feature Branch**: `001-cache-architecture-audit`
**Date**: 2026-03-17

## CloudWatch Metric Namespace

All cache metrics emitted under: `SentimentAnalyzer` (existing namespace)

## Metric Definitions

### Per-Cache Metrics

Emitted every 60 seconds (accumulated, then flushed).

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `Cache/Hit` | Count | Cache, Environment | Cache hits since last flush |
| `Cache/Miss` | Count | Cache, Environment | Cache misses since last flush |
| `Cache/Eviction` | Count | Cache, Environment | LRU evictions since last flush |
| `Cache/RefreshFailure` | Count | Cache, Environment | Failed upstream refresh attempts |

### Cache Dimension Values

| Cache Name | Source File | Description |
|------------|-----------|-------------|
| `jwks` | auth/cognito.py | Identity provider signing keys |
| `quota_tracker` | quota_tracker.py | API quota usage tracking |
| `ticker` | cache/ticker_cache.py | Ticker symbol list |
| `circuit_breaker` | circuit_breaker.py | Circuit breaker state |
| `ohlc_persistent` | cache/ohlc_cache.py | OHLC DynamoDB cache |
| `ohlc_response` | dashboard/ohlc.py | OHLC in-memory response cache |
| `sentiment` | dashboard/sentiment.py | Sentiment response cache |
| `metrics` | dashboard/metrics.py | Dashboard metrics cache |
| `config` | dashboard/configurations.py | User configuration cache |
| `secrets` | secrets.py | Secrets Manager cache |
| `tiingo` | adapters/tiingo.py | Tiingo API response cache |
| `finnhub` | adapters/finnhub.py | Finnhub API response cache |

### Alert Metrics

Emitted immediately (not accumulated).

| Metric Name | Unit | Dimensions | Description |
|-------------|------|------------|-------------|
| `QuotaTracker/Disconnected` | Count | Environment | Quota store unreachable, instance in 25% reduced-rate mode |
| `QuotaTracker/ThresholdWarning` | Count | Environment, Service | API usage exceeded 80% of limit |

### CloudWatch Alarms (recommended)

| Alarm | Metric | Threshold | Period | Action |
|-------|--------|-----------|--------|--------|
| Cache hit rate low | `Cache/Miss / (Cache/Hit + Cache/Miss)` | > 50% miss rate | 5 min | SNS notification |
| Quota disconnected | `QuotaTracker/Disconnected` | >= 1 | 1 min | SNS notification |
| Quota near limit | `QuotaTracker/ThresholdWarning` | >= 1 | 5 min | SNS notification |

## Emission Strategy

- **Accumulation**: CacheStats accumulates hit/miss/eviction counts in memory.
- **Flush interval**: Every 60 seconds, or when Lambda is about to return a response.
- **Batch emission**: Use `emit_metrics_batch()` to send all cache metrics in one CloudWatch API call.
- **Error handling**: Metric emission failures are logged but never fail the request.
- **Cost control**: ~12 unique metric/dimension combinations × $0.30/month = ~$3.60/month.
