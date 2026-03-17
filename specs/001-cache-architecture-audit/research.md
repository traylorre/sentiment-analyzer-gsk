# Research: Cache Architecture Audit and Remediation

**Feature Branch**: `001-cache-architecture-audit`
**Date**: 2026-03-17

## Decision 1: JWKS Cache Strategy — TTL with Refresh-on-Failure

**Decision**: Replace `@lru_cache(maxsize=1)` on `_get_jwks()` with a manual cache dict keyed by config hash, using a 5-minute TTL and refresh-on-failure semantics.

**Rationale**:
- `@lru_cache` provides no TTL or invalidation mechanism. Once cached, JWKS keys persist for the entire Lambda container lifetime (hours to days).
- Cognito rotates keys on an unpredictable schedule. During rotation, both old and new keys are published briefly, then the old key is removed.
- A 5-minute TTL ensures keys are refreshed frequently enough to catch rotation within one or two refresh cycles.
- Refresh-on-failure adds a second safety net: if a token presents a `kid` not in the cached key set, the system fetches fresh keys before rejecting the token.
- 15-minute grace period on fetch failure balances availability (riding out transient Cognito blips) vs. security (limiting exposure to stale keys).

**Alternatives Considered**:
- **Keep @lru_cache, add manual invalidation**: Rejected — lru_cache doesn't support partial invalidation or TTL; `cache_clear()` wipes all entries, which would cause a thundering herd if called on every failure.
- **Use pyjwt's built-in JWKS client with caching**: Rejected — adds a dependency and doesn't give us control over the grace period or failure metrics. The current codebase uses manual JWKS fetching.
- **Event-driven invalidation via SNS**: Rejected — Cognito doesn't emit key rotation events. No event source to subscribe to.

**Implementation Approach**:
```python
# Module-level cache
_jwks_cache: dict[str, tuple[float, dict]] = {}  # {config_hash: (timestamp, jwks_data)}
_jwks_cache_lock = threading.Lock()
JWKS_CACHE_TTL = int(os.environ.get("JWKS_CACHE_TTL", "300"))  # 5 minutes

def _get_jwks(config: CognitoConfig) -> dict:
    # Check cache with TTL
    # On miss or expired: fetch from Cognito
    # On fetch failure: return stale if within 15-min grace, else raise

def _get_jwks_with_retry(config: CognitoConfig, target_kid: str | None = None) -> dict:
    # If target_kid not in cached keys: force refresh before failing
```

## Decision 2: Quota Tracker — DynamoDB Atomic Counters

**Decision**: Replace the batch `put_item()` sync with per-call `update_item()` using DynamoDB atomic `ADD` operations for quota increments.

**Rationale**:
- Current approach: each Lambda tracks quota locally and syncs the full tracker to DynamoDB every 60 seconds via `put_item()`. With N concurrent instances, up to N×60s of calls can go untracked, causing quota overages.
- Atomic `ADD` operations (`UpdateExpression: "ADD tiingo_used :count"`) provide immediate cross-instance visibility. Each call increments the shared counter atomically — no read-modify-write race.
- DynamoDB atomic counters are strongly consistent for writes. A subsequent `get_item()` with `ConsistentRead=True` returns the latest value.
- Cost impact: one `update_item` WCU per API call instead of one `put_item` every 60s. At 22 tickers with ~100 calls/hour, this is ~100 additional WCUs/hour ($0.000125/hr). At 8K tickers with ~1000 calls/hour, ~$0.00125/hr. Well within the $5/month budget.

**Alternatives Considered**:
- **Reduce sync interval to 5s**: Rejected — still allows 5s×N instances of drift. Doesn't solve the fundamental race condition, just narrows the window.
- **DynamoDB Streams + Lambda aggregator**: Rejected — over-engineered for the problem. Adds new infrastructure (Lambda, Stream) and latency.
- **ElastiCache/Redis atomic counters**: Rejected — adds a new service, violates the "no new infrastructure" constraint, and costs more than DynamoDB.
- **Hybrid: atomic increment + local cache for reads**: This is the chosen approach — atomic writes for accuracy, local cache for read performance. Reads check DynamoDB every 10s (configurable) for the aggregate count.

**Implementation Approach**:
```python
def record_api_call(service: str, count: int = 1) -> None:
    # Atomic DynamoDB increment (always, no local batching for writes)
    table.update_item(
        Key={"PK": "SYSTEM#QUOTA", "SK": today},
        UpdateExpression="ADD #svc :count",
        ExpressionAttributeNames={"#svc": f"{service}_used"},
        ExpressionAttributeValues={":count": count},
    )

def get_quota_remaining(service: str) -> int:
    # Local cache with 10s TTL for reads (avoid per-request DynamoDB read)
    # On cache miss: ConsistentRead=True from DynamoDB
```

**Fallback Behavior**:
- On DynamoDB write failure: log error, emit `QuotaSync/Failure` metric, reduce local call rate to 25%, raise alert via `emit_metric("QuotaTracker/Disconnected", 1)`.
- On DynamoDB read failure: use last known cached value, continue at current rate.

## Decision 3: Ticker Cache — TTL Refresh with S3 ETag

**Decision**: Replace `@lru_cache(maxsize=1)` with a TTL-based cache that checks S3 ETag on refresh to avoid unnecessary downloads.

**Rationale**:
- Current `@lru_cache(maxsize=1)` never refreshes — ticker list loaded once per container lifetime.
- The list changes weekly but at 8K tickers (~1-2MB), re-downloading every 5 minutes is wasteful.
- S3 `head_object()` returns the ETag (content hash). Comparing local ETag to remote costs 1 API call vs. downloading the full object.
- If ETag matches: skip download, reset TTL timer. If ETag differs: download new list, validate non-empty, swap cache.

**Alternatives Considered**:
- **S3 Event Notifications → SNS → Lambda**: Rejected — adds infrastructure, complex for a weekly update.
- **CloudWatch Events scheduled refresh**: Rejected — needs a separate Lambda, overkill.
- **Always download on TTL expiry**: Rejected — 1-2MB every 5 minutes × 20 instances = unnecessary bandwidth.

**Implementation Approach**:
```python
_ticker_cache: tuple[float, TickerCache, str] | None = None  # (timestamp, cache, etag)
TICKER_CACHE_TTL = int(os.environ.get("TICKER_CACHE_TTL", "300"))  # 5 minutes

def get_ticker_cache(bucket: str, key: str) -> TickerCache:
    # Check TTL
    # If expired: head_object() to get current ETag
    # If ETag unchanged: reset timer, return cached
    # If ETag changed: get_object(), validate non-empty, swap cache
    # On S3 failure: return stale cache, log warning
```

## Decision 4: Jitter Strategy — Uniform Random on TTL

**Decision**: Add `random.uniform(ttl * 0.9, ttl * 1.1)` to all cache expiry calculations (±10% of base TTL).

**Rationale**:
- All 12 caches currently use exact TTL values. With N instances starting at similar times, caches expire simultaneously → thundering herd.
- ±10% uniform jitter spreads expiry across a 20% window. For a 60s TTL, expiry ranges from 54s to 66s.
- Uniform distribution (not normal) ensures even spread — no clustering at the mean.

**Implementation Approach**:
- New utility in `src/lib/cache_utils.py`:
```python
def jittered_ttl(base_ttl: float, jitter_pct: float = 0.1) -> float:
    """Return TTL with ±jitter_pct random offset."""
    return base_ttl * random.uniform(1.0 - jitter_pct, 1.0 + jitter_pct)
```
- Applied at cache entry creation time, not on every read.

## Decision 5: Cache Metrics Emission — Piggyback on Existing emit_metric()

**Decision**: Use the existing `emit_metric()` from `src/lib/metrics.py` to emit per-cache hit/miss/eviction counts to CloudWatch.

**Rationale**:
- `emit_metric()` already handles namespace, environment dimension, and error suppression.
- `emit_metrics_batch()` allows batching multiple metrics per CloudWatch API call (more efficient).
- Emit on cache access (hit/miss) and on eviction events. Use dimension `Cache=<name>` for per-cache attribution.

**Metric Names**:
- `Cache/Hit` — dimensions: {Cache, Environment}
- `Cache/Miss` — dimensions: {Cache, Environment}
- `Cache/Eviction` — dimensions: {Cache, Environment}
- `Cache/RefreshFailure` — dimensions: {Cache, Environment}
- `QuotaTracker/Disconnected` — dimensions: {Environment} (alert trigger)

**Cost**: CloudWatch custom metrics cost $0.30/metric/month. With 12 caches × 4 metrics = 48 metrics = ~$14.40/month. To reduce cost, batch metrics and use fewer unique dimension combinations. Alternatively, emit aggregated stats every 60s instead of per-request.

**Chosen approach**: Emit stats every 60s (or on Lambda shutdown) rather than per-request, to keep CloudWatch costs under $5/month. Use a module-level accumulator that flushes periodically.

## Decision 6: Failure Policy Classification

**Decision**: Classify each cache into fail-open or fail-closed based on data criticality.

| Cache | Failure Policy | Grace Period | Rationale |
|-------|---------------|-------------|-----------|
| JWKS (Cognito keys) | Fail-closed | 15 min | Security-critical: stale keys = auth bypass risk |
| Secrets Manager | Fail-closed | 15 min | Security-critical: secrets must be current |
| Quota Tracker | Fail-conservative | N/A | Reduce to 25% rate + alert (not full stop) |
| Ticker List (S3) | Fail-open | Indefinite (stale list) | Stale tickers are cosmetic, not security |
| Resolution Cache | Fail-open | Until next TTL | Stale timeseries data is acceptable briefly |
| OHLC Response | Fail-open | Until next TTL | Stale price data acceptable briefly |
| Sentiment Response | Fail-open | Until next TTL | Stale sentiment acceptable briefly |
| Metrics Cache | Fail-open | Until next TTL | Stale dashboard metrics acceptable |
| Configuration Cache | Fail-open | Until next TTL | Stale user config acceptable briefly |
| Circuit Breaker | Fail-open (closed state) | 60s | If can't read state, assume circuit closed (allow traffic) |
| Tiingo API Cache | Fail-open | Until next TTL | Stale API data acceptable |
| Finnhub API Cache | Fail-open | Until next TTL | Stale API data acceptable |

## Decision 7: Cache Utility Module — Shared Abstractions

**Decision**: Create `src/lib/cache_utils.py` with shared utilities rather than a full cache abstraction layer.

**Rationale**:
- A full unified cache interface would require refactoring all 12 caches — high risk, large scope.
- Shared utilities (jitter function, stats accumulator, metric flusher) provide 80% of the benefit at 20% of the cost.
- Each cache retains its existing interface and semantics — only internals change.

**Module contents**:
- `jittered_ttl(base_ttl, jitter_pct)` — TTL with jitter
- `CacheStats` dataclass — hits, misses, evictions, refresh_failures
- `CacheMetricEmitter` — accumulates stats, flushes to CloudWatch every 60s
- `validate_non_empty(data, cache_name)` — rejects empty/None data for safety
