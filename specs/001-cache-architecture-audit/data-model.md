# Data Model: Cache Architecture Audit and Remediation

**Feature Branch**: `001-cache-architecture-audit`
**Date**: 2026-03-17

## Entities

### CacheStats

Tracks hit/miss/eviction counts for a single named cache. Thread-safe accumulator that flushes to CloudWatch periodically.

**Attributes**:
- `name` (str): Unique cache identifier (e.g., "jwks", "quota_tracker", "ticker")
- `hits` (int): Number of cache hits since last flush
- `misses` (int): Number of cache misses since last flush
- `evictions` (int): Number of LRU evictions since last flush
- `refresh_failures` (int): Number of failed upstream refresh attempts since last flush
- `last_flush_at` (float): Timestamp of last metric emission

**Relationships**: One per cache instance. Aggregated by CacheMetricEmitter.

**Validation**: All counters >= 0. Name must be non-empty.

### CacheEntry (conceptual — not a shared class)

Represents a single cached value across all cache implementations. Not a shared base class — each cache implements its own tuple/dict pattern, but all must include these fields.

**Attributes**:
- `value` (Any): The cached data
- `created_at` (float): time.time() when entry was created
- `effective_ttl` (float): Base TTL with jitter applied (via `jittered_ttl()`)
- `etag` (str | None): Source change-detection token (S3 ETag, HTTP ETag). Only for caches that support conditional refresh.

**State Transitions**:
```
EMPTY → FRESH (on first load)
FRESH → STALE (when time.time() - created_at > effective_ttl)
STALE → FRESH (on successful refresh)
STALE → GRACE (on failed refresh, within grace period)
GRACE → FAILED (on failed refresh, past grace period)
FAILED → FRESH (on successful refresh after failure)
```

**Validation**: effective_ttl > 0. created_at > 0.

### QuotaLedger (DynamoDB)

Shared record of API usage across all Lambda instances. Uses atomic counters for writes.

**Table**: Existing quota tracker DynamoDB table
**Key Schema**:
- PK: `SYSTEM#QUOTA` (partition key, string)
- SK: `YYYY-MM-DD` (sort key, date partition)

**Attributes**:
- `tiingo_used` (number): Atomic counter for Tiingo API calls today
- `finnhub_used` (number): Atomic counter for Finnhub API calls today
- `tiingo_limit` (number): Daily limit for Tiingo
- `finnhub_limit` (number): Daily limit for Finnhub
- `last_alert_at` (string | None): ISO timestamp of last quota alert (prevents alert spam)
- `ttl` (number): DynamoDB TTL — auto-delete after 7 days

**Operations**:
- Write: `update_item` with `ADD #svc :count` (atomic increment, no read-modify-write)
- Read: `get_item` with `ConsistentRead=True` (for accurate count)
- Daily reset: New SK partition per day, old days auto-deleted via TTL

### JWKSCache (module-level)

In-memory cache for identity provider signing keys with TTL and refresh-on-failure.

**Attributes**:
- `keys` (dict): Parsed JWKS JSON (key ID → key material)
- `fetched_at` (float): Timestamp of last successful fetch
- `last_failure_at` (float | None): Timestamp of last fetch failure (None if healthy)
- `config_hash` (str): Hash of CognitoConfig to detect config changes

**State Machine**:
```
COLD → WARM (first successful fetch)
WARM → EXPIRED (fetched_at + TTL < now)
EXPIRED → WARM (successful refresh)
EXPIRED → GRACE (failed refresh, within 15-min window)
GRACE → WARM (successful refresh)
GRACE → DENIED (failed refresh, past 15-min window → fail closed)
```

### TickerCacheEntry (module-level)

In-memory cache for ticker symbol list with S3 ETag-based conditional refresh.

**Attributes**:
- `tickers` (TickerCache): Parsed ticker list object
- `loaded_at` (float): Timestamp of last successful load
- `etag` (str): S3 ETag from last download
- `effective_ttl` (float): Jittered TTL for next refresh check

**Validation**: Ticker list must be non-empty on refresh. Empty lists rejected to prevent serving blank dashboard.

## Existing Entities Modified

### All 12 In-Memory Caches

Each existing cache gains:
- `CacheStats` instance for hit/miss/eviction tracking
- `jittered_ttl()` call at entry creation time
- `max_entries` bound (if not already present — metrics cache currently unbounded)

### Circuit Breaker State

Existing `recovery_timeout_seconds` gains jitter: `random.uniform(timeout * 0.9, timeout * 1.1)`.

No schema changes to DynamoDB — existing table structure is preserved.
