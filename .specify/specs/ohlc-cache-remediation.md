# Specification: OHLC Cache Remediation

**Feature ID:** CACHE-001
**Status:** Draft
**Created:** 2026-02-03
**Source:** `docs/cache/HL-cache-remediation-checklist.md`

---

## 1. Problem Statement

The OHLC caching infrastructure is **partially implemented but non-functional**:
- DynamoDB table exists (`{env}-ohlc-cache`)
- IAM permissions granted (Query, PutItem, BatchWriteItem)
- Cache functions defined (`get_cached_candles`, `put_cached_candles`)
- **BUT:** Functions are never called from the OHLC endpoint

### Impact
- Every Lambda cold start = redundant Tiingo API call
- Historical data lost across invocations
- Playwright tests flaky due to external API dependency
- ~$5-10/month wasted on unused DynamoDB table

---

## 2. Goals

### Primary Goals
1. **Enable DynamoDB cache writes** - After fetching from Tiingo, write candles to DynamoDB
2. **Enable DynamoDB cache reads** - Before calling Tiingo, check DynamoDB for cached data
3. **Fix cache key design** - Include end_date in cache key to prevent stale data across days
4. **Verify `PriceCandle.from_cached_candle()`** - Already exists at `models/ohlc.py:121-155`; verify correctness, update volume type
5. **Add local OHLC table** - Enable local development and testing

### Secondary Goals
1. **Reduce Playwright test flakiness** - By ensuring cache hits for repeated requests
2. **Reduce Tiingo API costs** - At most 1 API call per ticker per day
3. **Improve cold start performance** - Cache reads are ~20ms vs ~500-2000ms API calls

---

## 3. Non-Goals

- Cache warming strategy (future optimization)
- Parallel DynamoDB queries for large ranges (future optimization)
- Finnhub caching (out of scope - Tiingo is primary source)
- News caching (already working via in-memory cache)
- Ticker caching (already working via S3)

---

## 4. Technical Specification

### 4.1 Cache Key Fix

**File:** `src/lambdas/dashboard/ohlc.py`
**Function:** `_get_ohlc_cache_key()`

**Current Behavior (Broken):**
```python
# Predefined ranges use range name only
return f"ohlc:{ticker.upper()}:{resolution}:{time_range}"
```

**New Behavior:**
```python
def _get_ohlc_cache_key(
    ticker: str,
    resolution: str,
    time_range: str,
    start_date: date,
    end_date: date,
) -> str:
    """Generate cache key including end_date for day-anchoring."""
    ticker_upper = ticker.upper()
    date_anchor = end_date.isoformat()

    if time_range == "custom":
        return f"ohlc:{ticker_upper}:{resolution}:custom:{start_date.isoformat()}:{end_date.isoformat()}"
    else:
        return f"ohlc:{ticker_upper}:{resolution}:{time_range}:{date_anchor}"
```

**Rationale:** Including `end_date` ensures that:
- Same ticker/range on different days → different keys (prevents stale data)
- Same ticker/range/day with different resolution → different keys (preserves resolution)
- Cache key lookup matches cache key storage

### 4.2 Cache Writing (Write-Through)

**File:** `src/lambdas/dashboard/ohlc.py`
**New Function:** `_write_through_to_dynamodb()`

**Implementation:**
```python
from src.lambdas.shared.cache.ohlc_cache import (
    put_cached_candles,
    candles_to_cached,
)

def _write_through_to_dynamodb(
    ticker: str,
    source: str,
    resolution: str,
    ohlc_candles: list,
    end_date: date,  # Required for TTL calculation
) -> None:
    """Persist OHLC candles to DynamoDB for cross-invocation caching.

    Args:
        end_date: The request's end_date, used to determine TTL strategy
                  (5min for today's intraday, 90d for historical/daily)

    Fire-and-forget - errors are logged but don't fail the request.
    """
    try:
        cached_candles = candles_to_cached(ohlc_candles, source, resolution)
        if not cached_candles:
            logger.debug("No candles to cache", extra={"ticker": ticker})
            return

        written = put_cached_candles(
            ticker=ticker,
            source=source,
            resolution=resolution,
            candles=cached_candles,
            end_date=end_date,  # For TTL calculation
        )

        logger.info(
            "OHLC write-through complete",
            extra={
                "ticker": ticker,
                "source": source,
                "resolution": resolution,
                "candles_written": written,
            },
        )
    except Exception as e:
        logger.warning(
            "OHLC write-through failed",
            extra=get_safe_error_info(e),
        )
```

**Call Sites:**
1. After daily OHLC fetch (line ~371)
2. After intraday OHLC fetch (line ~386)
3. After fallback daily fetch (line ~412)

**Constraints:**
- Never cache error responses (404, 503)
- Never cache empty candle lists
- Fire-and-forget: errors logged but don't fail request

### 4.3 Cache Reading (Query DynamoDB First)

**File:** `src/lambdas/dashboard/ohlc.py`
**New Functions:** `_read_from_dynamodb()`, `_estimate_expected_candles()`, `_build_response_from_cache()`

**Implementation:**
```python
from datetime import UTC, datetime, time as dt_time
from src.lambdas.shared.cache.ohlc_cache import get_cached_candles

def _read_from_dynamodb(
    ticker: str,
    source: str,
    resolution: OHLCResolution,
    start_date: date,
    end_date: date,
) -> list[PriceCandle] | None:
    """Query DynamoDB for cached OHLC candles.

    Returns None if:
    - No data found
    - Query fails (graceful degradation)
    - Incomplete data (<100% expected candles)
    """
    try:
        start_time = datetime.combine(start_date, dt_time.min, tzinfo=UTC)
        end_time = datetime.combine(end_date, dt_time.max, tzinfo=UTC)

        result = get_cached_candles(
            ticker=ticker,
            source=source,
            resolution=resolution.value,
            start_time=start_time,
            end_time=end_time,
        )

        if not result.cache_hit or not result.candles:
            logger.debug("DynamoDB cache miss", extra={"ticker": ticker})
            return None

        # Convert CachedCandle to PriceCandle
        price_candles = [
            PriceCandle.from_cached_candle(c, resolution)
            for c in result.candles
        ]

        # Validate coverage (100% required - no partial hits)
        expected = _estimate_expected_candles(start_date, end_date, resolution)
        if len(price_candles) < expected:
            logger.info(
                "DynamoDB cache incomplete, fetching fresh",
                extra={"found": len(price_candles), "expected": expected},
            )
            return None

        return price_candles
    except Exception as e:
        logger.warning(
            "DynamoDB cache read failed, falling back to API",
            extra=get_safe_error_info(e),
        )
        return None
```

**Integration Point:** After in-memory cache check, before Tiingo API call (line ~351)

### 4.4 PriceCandle Converter

**File:** `src/lambdas/shared/models/ohlc.py`
**Method:** `PriceCandle.from_cached_candle()` — **Already exists** at `models/ohlc.py:121-155`. No new method needed. Verify existing implementation handles resolution-based date formatting correctly (daily → `date()`, intraday → `datetime`). Update `volume` type per Round 17 Q5 (`int = 0`).

### 4.5 Local API Table Setup

**File:** `scripts/run-local-api.py`

**Changes:**
1. Add `OHLC_CACHE_TABLE` environment variable
2. Create `local-ohlc-cache` table in `create_mock_tables()`

**Implementation:**
```python
# Line ~77
os.environ.setdefault("OHLC_CACHE_TABLE", "local-ohlc-cache")

# In create_mock_tables(), add:
dynamodb.create_table(
    TableName="local-ohlc-cache",
    KeySchema=[
        {"AttributeName": "PK", "KeyType": "HASH"},
        {"AttributeName": "SK", "KeyType": "RANGE"},
    ],
    AttributeDefinitions=[
        {"AttributeName": "PK", "AttributeType": "S"},
        {"AttributeName": "SK", "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST",
)
```

### 4.6 DynamoDB TTL Configuration

**Decision (Clarified 2026-02-03, updated 2026-02-04):**
- Historical data: 90-day TTL
- Today's intraday data: 5-minute TTL (ensures freshness, simplest Zone 2 migration path)

**Terraform Changes:** `infrastructure/dynamodb.tf`
```hcl
resource "aws_dynamodb_table" "ohlc_cache" {
  # ... existing config ...

  ttl {
    attribute_name = "ExpiresAt"
    enabled        = true
  }
}
```

**Write-Through Changes:** `src/lambdas/shared/cache/ohlc_cache.py`
```python
import time
from datetime import date, timedelta

TTL_DAYS_HISTORICAL = 90
TTL_MINUTES_TODAY_INTRADAY = 5

def _calculate_ttl(resolution: str, end_date: date) -> int:
    """Calculate TTL timestamp based on data freshness profile.

    Args:
        resolution: "D" for daily, "5"/"60" for intraday
        end_date: The end date of the cached data

    Returns:
        Unix timestamp for TTL expiration

    Strategy:
        - Historical data (any date before today): 90-day TTL
        - Today's intraday data: 5-minute TTL (auto-refresh for freshness)
        - Today's daily data: 90-day TTL (daily bar won't change until tomorrow)

    IMPORTANT (Clarified 2026-02-06 Round 18):
        Uses market timezone (ET) not UTC for "today" determination.
        Without this, ~3 hours/day (4PM ET to midnight UTC) would incorrectly
        assign 5-minute TTL to finalized daily data.
    """
    from src.lambdas.shared.utils.market import ET  # ZoneInfo("America/New_York")
    from datetime import datetime

    market_today = datetime.now(ET).date()
    is_today = end_date >= market_today
    is_intraday = resolution != "D"

    if is_today and is_intraday:
        # Today's intraday: short TTL for freshness
        # Zone 2 migration: no changes needed, just add WebSocket on top
        return int(time.time()) + (TTL_MINUTES_TODAY_INTRADAY * 60)
    else:
        # Historical or daily: long TTL (immutable data)
        return int(time.time()) + (TTL_DAYS_HISTORICAL * 24 * 60 * 60)

# In put_cached_candles(), add to each item:
item = {
    "PK": {"S": pk},
    "SK": {"S": sk},
    # ... existing attributes ...
    "ExpiresAt": {"N": str(_calculate_ttl(resolution, end_date))},
}
```

**Rationale:**
- 90 days covers most realistic use cases (YTD, 3-month charts)
- 5-minute TTL for today's intraday ensures users get recent completed bars
- Older data can be re-fetched from Tiingo if needed (historical data is immutable)
- Automatic cleanup prevents unbounded storage growth
- No operational burden (DynamoDB handles deletion asynchronously)
- **Zone 2 Migration:** When adding partial buckets via WebSocket, Zone 1 logic unchanged

### 4.7 Thundering Herd Prevention (Distributed Lock)

**Decision (Clarified 2026-02-03):** Use DynamoDB conditional write as distributed lock - first caller fetches from Tiingo, others wait and retry from cache.

**File:** `src/lambdas/shared/cache/ohlc_cache.py`

**Lock Table Design:** Reuse existing `ohlc-cache` table with lock items:
```
PK: "LOCK#AAPL#D#1W#2026-02-04"  (LOCK#{ticker}#{resolution}#{range}#{date_anchor})
SK: "LOCK"
LockHolder: "lambda-instance-uuid"
ExpiresAt: <current_time + 30 seconds>  (auto-cleanup via TTL)
```

**Decision (Clarified 2026-02-04):** Lock key MUST include the date anchor to match cache key granularity. This prevents false contention between requests for different days.

**Implementation:**
```python
import uuid
import time

LOCK_TTL_SECONDS = 30
LOCK_WAIT_MS = 200      # 200ms between retries
LOCK_MAX_RETRIES = 15   # 15 retries × 200ms = 3000ms total wait

def _acquire_fetch_lock(cache_key: str) -> str | None:
    """Attempt to acquire distributed lock for API fetch.

    Args:
        cache_key: Full cache key including date anchor (e.g., "ohlc:AAPL:D:1W:2026-02-04")

    Returns lock_id if acquired, None if another caller holds lock.

    Note: Lock key includes full cache_key to ensure granularity matches.
    Requests for different dates will not block each other.
    """
    lock_id = str(uuid.uuid4())
    lock_pk = f"LOCK#{cache_key}"  # Includes date anchor from cache_key
    expires_at = int(time.time()) + LOCK_TTL_SECONDS

    try:
        client = _get_dynamodb_client()
        client.put_item(
            TableName=_get_table_name(),
            Item={
                "PK": {"S": lock_pk},
                "SK": {"S": "LOCK"},
                "LockHolder": {"S": lock_id},
                "ExpiresAt": {"N": str(expires_at)},
            },
            ConditionExpression="attribute_not_exists(PK) OR ExpiresAt < :now",
            ExpressionAttributeValues={
                ":now": {"N": str(int(time.time()))},
            },
        )
        return lock_id
    except client.exceptions.ConditionalCheckFailedException:
        return None  # Lock held by another caller

def _release_fetch_lock(cache_key: str, lock_id: str) -> None:
    """Release distributed lock (best-effort, TTL handles cleanup)."""
    try:
        client = _get_dynamodb_client()
        client.delete_item(
            TableName=_get_table_name(),
            Key={
                "PK": {"S": f"LOCK#{cache_key}"},
                "SK": {"S": "LOCK"},
            },
            ConditionExpression="LockHolder = :holder",
            ExpressionAttributeValues={
                ":holder": {"S": lock_id},
            },
        )
    except Exception:
        pass  # TTL will clean up stale locks
```

**Integration in OHLC fetch flow:**
```python
async def _fetch_with_lock(ticker: str, cache_key: str, ...):
    """Fetch from API with distributed lock to prevent thundering herd."""

    # Try to acquire lock
    lock_id = _acquire_fetch_lock(cache_key)

    if lock_id:
        # We won the lock - fetch from API
        try:
            candles = await _fetch_from_tiingo(ticker, ...)
            await _write_through_to_dynamodb(ticker, candles, ...)
            return candles
        finally:
            _release_fetch_lock(cache_key, lock_id)
    else:
        # Another caller is fetching - wait and retry from cache
        for _ in range(LOCK_MAX_RETRIES):
            await asyncio.sleep(LOCK_WAIT_MS / 1000)
            cached = await _read_from_dynamodb(ticker, ...)
            if cached:
                return cached

        # Lock holder may have failed - fall through to API
        logger.warning("Lock wait timeout, falling back to API fetch")
        return await _fetch_from_tiingo(ticker, ...)
```

**Behavior:**
- First caller acquires lock, fetches from Tiingo, writes to DynamoDB
- Concurrent callers wait up to 3000ms (15 × 200ms), polling DynamoDB
- If cache populated, concurrent callers return cached data
- If lock holder crashes, 30s TTL auto-releases lock
- Fallback: if wait times out, caller fetches anyway (availability over consistency)

**Timeout Rationale:** Tiingo API latency is 500-2000ms. The 3000ms wait covers the 95th percentile response time plus write-through overhead (~100ms), preventing thundering herd while maintaining reasonable user experience.

### 4.8 Read-Through Cache Pattern

**Decision (Clarified 2026-02-04):** Use read-through cache with strong consistent DynamoDB reads to solve cross-Lambda consistency.

**Problem:** In-memory cache is per-Lambda-instance. When Caller A (Instance 1) writes to DynamoDB, Caller B (Instance 2) has a separate empty in-memory cache and must read from DynamoDB. Eventual consistency can cause Caller B to miss the just-written data.

**Solution:** Write-through + Read-through + Global Lock

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CACHE ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Lambda Instance 1          Lambda Instance 2                       │
│  ┌─────────────────┐        ┌─────────────────┐                    │
│  │ In-Memory Cache │        │ In-Memory Cache │  (isolated)        │
│  │ (read-through)  │        │ (read-through)  │                    │
│  └────────┬────────┘        └────────┬────────┘                    │
│           │                          │                              │
│           └──────────┬───────────────┘                              │
│                      ▼                                              │
│           ┌─────────────────────┐                                   │
│           │ DynamoDB (shared)   │  Strong consistent reads         │
│           │ + Global Lock       │                                   │
│           └─────────────────────┘                                   │
│                      │                                              │
│                      ▼ (on miss + lock acquired)                   │
│           ┌─────────────────────┐                                   │
│           │ Tiingo/Finnhub API  │  Write-through on fetch          │
│           └─────────────────────┘                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
from typing import Callable
from cachetools import TTLCache

class OHLCReadThroughCache:
    """In-memory cache with read-through to DynamoDB.

    Eviction Policy: LRU (Least Recently Used) when maxsize reached.
    This is acceptable because DynamoDB provides the durable cache layer.
    Evicted entries will be re-fetched from DynamoDB (~40ms) on next access.

    THREAD SAFETY (Clarified 2026-02-06):
    cachetools.TTLCache is NOT thread-safe. ALL reads/writes to self._cache
    MUST happen on the event loop thread. asyncio.to_thread() wraps only the
    raw DynamoDB I/O and returns data to the event loop thread, which then
    updates the cache. Never pass self._cache into a to_thread() callable.
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 3600):
        # maxsize=1000 balances memory usage with hit rate
        # ttl=3600 (1hr) matches typical Lambda warm instance lifetime
        self._cache = TTLCache(maxsize=maxsize, ttl=ttl)

    async def get_or_fetch(
        self,
        key: str,
        fetch_from_dynamodb: Callable[[], Awaitable[list[PriceCandle] | None]],
    ) -> list[PriceCandle] | None:
        """Read-through: check in-memory, then DynamoDB with strong consistency.

        Solves cross-Lambda consistency by always falling through to
        DynamoDB (with ConsistentRead=True) when in-memory misses.

        Thread boundary: fetch_from_dynamodb() uses asyncio.to_thread()
        internally for the DynamoDB call, but returns data to THIS coroutine
        (on the event loop thread). Cache writes below are event-loop-only.
        """
        # Check in-memory first (same-instance optimization, ~1ms)
        # SAFE: runs on event loop thread
        if key in self._cache:
            logger.debug("In-memory cache hit", extra={"key": key})
            return self._cache[key]

        # Read-through to DynamoDB (strong consistency, ~40ms)
        # fetch_from_dynamodb() awaits asyncio.to_thread() internally,
        # but returns result HERE on the event loop thread
        result = await fetch_from_dynamodb()
        if result:
            # SAFE: cache write on event loop thread (after await returns)
            self._cache[key] = result
            logger.debug("DynamoDB cache hit, populated in-memory", extra={"key": key})

        return result

# Module-level singleton
_ohlc_read_through_cache = OHLCReadThroughCache()
```

**Updated DynamoDB Query (Hybrid Consistency):**

```python
def get_cached_candles(
    ticker: str,
    source: str,
    resolution: str,
    start_time: datetime,
    end_time: datetime,
    consistent_read: bool = False,  # Default eventual (cost-efficient)
) -> OHLCCacheResult:
    """Query DynamoDB for cached OHLC candles.

    Args:
        consistent_read: If True, uses strongly consistent read (~40ms, 2 RCU).
                        If False, uses eventually consistent read (~20ms, 1 RCU).
                        Default False for cost efficiency.
                        Use True only for lock waiter retries (cross-instance race).
    """
    # ... existing query logic ...

    response = client.query(
        TableName=table_name,
        KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end",
        ExpressionAttributeValues={...},
        ConsistentRead=consistent_read,  # Strong consistency
    )
```

**Updated Lock Wait Flow:**

```python
async def _fetch_with_lock(ticker: str, cache_key: str, ...):
    """Fetch from API with distributed lock and read-through cache.

    Consistency Strategy (Cost Optimization):
    - Initial read: eventual consistency (1 RCU, ~20ms) - miss is acceptable
    - Lock waiter retries: strong consistency (2 RCU, ~40ms) - must see recent writes
    - Double-check after lock: strong consistency - prevent duplicate fetches
    """

    # Step 1: Check read-through cache (in-memory → eventual DynamoDB)
    # Eventual consistency is fine here - a miss just means we fetch from Tiingo
    cached = await _ohlc_read_through_cache.get_or_fetch(
        key=cache_key,
        fetch_from_dynamodb=lambda: _read_from_dynamodb(
            ticker, source, resolution, start_date, end_date,
            consistent_read=False  # Eventual: cost-efficient for initial check
        )
    )
    if cached:
        return cached

    # Step 2: Acquire lock (cache miss confirmed)
    lock_id = _acquire_fetch_lock(cache_key)

    if lock_id:
        try:
            # Step 3a: Double-check after lock (another caller might have just written)
            # Strong consistency required - we're about to call Tiingo if miss
            cached = await _read_from_dynamodb(..., consistent_read=True)
            if cached:
                _ohlc_read_through_cache._cache[cache_key] = cached
                return cached

            # Step 4: Fetch from Tiingo (write-through)
            candles = await _fetch_from_tiingo(ticker, ...)
            await _write_through_to_dynamodb(ticker, source, resolution, candles, end_date)
            _ohlc_read_through_cache._cache[cache_key] = candles
            return candles
        finally:
            _release_fetch_lock(cache_key, lock_id)
    else:
        # Step 3b: Lock not acquired - wait and poll read-through cache
        for _ in range(LOCK_MAX_RETRIES):
            await asyncio.sleep(LOCK_WAIT_MS / 1000)

            # Poll with STRONG consistency - must see lock holder's write
            cached = await _ohlc_read_through_cache.get_or_fetch(
                key=cache_key,
                fetch_from_dynamodb=lambda: _read_from_dynamodb(
                    ticker, source, resolution, start_date, end_date,
                    consistent_read=True  # Strong: must see recent writes
                )
            )
            if cached:
                return cached

        # Fallback: fetch anyway (availability over consistency)
        logger.warning("Lock wait timeout, falling back to API fetch")
        return await _fetch_from_tiingo(ticker, ...)
```

**Guarantees:**
1. Same-instance requests: In-memory hit (~1ms)
2. Initial cache check: Eventual consistency (~20ms, 1 RCU) - miss triggers lock acquisition
3. Lock waiters: Strong consistency (~40ms, 2 RCU) - guaranteed to see lock holder's write
4. Double-check after lock: Strong consistency - prevents duplicate Tiingo fetches
5. Cost optimization: Happy path (cache hit) uses eventual consistency (half the cost)

### 4.9 Cache Source Response Header

**Decision (Clarified 2026-02-04):** Add `X-Cache-Source` response header for immediate cache verification and debugging.

**Header Values:**

| Value | Meaning | Latency |
|-------|---------|---------|
| `in-memory` | Served from Lambda instance cache | ~1ms |
| `dynamodb` | Served from DynamoDB persistent cache | ~40ms |
| `tiingo` | Fetched fresh from Tiingo API | ~500-2000ms |
| `finnhub` | Fetched fresh from Finnhub API | ~500-2000ms |

**Implementation:**

```python
from fastapi import Response

async def get_ohlc_data(
    ticker: str,
    resolution: str,
    time_range: str,
    response: Response,  # FastAPI injects this
) -> OHLCResponse:
    """Get OHLC data with cache source tracking."""

    cache_source = "tiingo"  # Default: will fetch from API

    # Check read-through cache
    cache_key = _get_ohlc_cache_key(ticker, resolution, time_range, start_date, end_date)

    # In-memory check
    if cache_key in _ohlc_read_through_cache._cache:
        candles = _ohlc_read_through_cache._cache[cache_key]
        cache_source = "in-memory"
    else:
        # DynamoDB check (strong consistency)
        dynamodb_result = await _read_from_dynamodb(...)
        if dynamodb_result:
            candles = dynamodb_result
            cache_source = "dynamodb"
            _ohlc_read_through_cache._cache[cache_key] = candles
        else:
            # Fetch from API (with lock)
            candles = await _fetch_with_lock(ticker, cache_key, ...)
            cache_source = "tiingo"  # or "finnhub" based on adapter used

    # Set response header
    response.headers["X-Cache-Source"] = cache_source
    response.headers["X-Cache-Key"] = cache_key  # Useful for debugging

    return OHLCResponse(candles=candles, ...)
```

**Benefits:**
- Immediate verification (no CloudWatch latency)
- Works for any HTTP client (curl, browser, Playwright)
- Useful for debugging slow requests
- Smoke tests can assert on header value
- API contract, not log format dependency

---

## 5. Data Flow (After Implementation)

```
Request: GET /api/v2/tickers/AAPL/ohlc?range=1M&resolution=D

1. Check Read-Through Cache (in-memory → strong DynamoDB)
   ├─ IN-MEMORY HIT → Return cached OHLCResponse (~1ms)
   ├─ DYNAMODB HIT → Populate in-memory, return (~40ms)
   └─ BOTH MISS ↓

2. Acquire Distributed Lock (DynamoDB conditional write)
   ├─ ACQUIRED → Proceed to step 3
   └─ LOCKED → Wait 200ms, retry step 1 (up to 15 times / 3s total), then fallback to step 3

3. Double-Check DynamoDB (another caller might have just written)
   ├─ HIT → Populate in-memory, release lock, return
   └─ MISS ↓

4. Call Tiingo API
   ├─ SUCCESS → Write-through to DynamoDB, populate in-memory, release lock, return
   └─ FAILURE → Release lock, return 503/404 error
```

**Cache Layers:**
| Layer | Scope | Consistency | Latency | Cost | TTL |
|-------|-------|-------------|---------|------|-----|
| In-Memory | Per-Lambda instance | Immediate (same instance) | ~1ms | Free | 1hr |
| DynamoDB (initial) | Global | Eventual | ~20ms | 1 RCU/4KB | 90d / 5min |
| DynamoDB (lock wait) | Global | Strong | ~40ms | 2 RCU/4KB | 90d / 5min |

---

## 6. Edge Cases & Error Handling

### 6.1 Incomplete Cache Data
**Behavior:** Treat as cache miss if cache has fewer candles than expected, fetch fresh from Tiingo
**Rationale:** Users expect complete data; no "good enough" shortcuts (clarified 2026-02-03)

### 6.2 DynamoDB Query Failure
**Behavior:** Log warning, fall through to Tiingo API
**Rationale:** DynamoDB is optimization, not requirement; graceful degradation

### 6.3 DynamoDB Write Failure
**Behavior:** Log warning, continue with request
**Rationale:** Write-through is best-effort; request still succeeds

### 6.4 Circular Import Risk
**Mitigation:** Use local imports inside functions:
```python
def _read_from_dynamodb(...):
    from src.lambdas.shared.cache.ohlc_cache import get_cached_candles
```

### 6.5 Async/Sync Mismatch
**Decision (Clarified 2026-02-03):** Wrap sync DynamoDB calls in `asyncio.to_thread()` now.
**Rationale:** Calling sync blocking code from async functions defeats cooperative multitasking - the event loop is blocked and cannot handle other requests. See Section 11.4 for implementation details.
**Codebase Audit Required:** Check for other async functions making sync network calls without await (same antipattern).

### 6.6 Error Response Caching
**Decision:** NEVER cache error responses (404, 503)
**Rationale:** Ticker may become valid later; transient failures should retry

### 6.7 Intraday Data Freshness
**Decision:** Cache all fetched data; today's incomplete data will be overwritten on next fetch
**Rationale:** Yesterday's intraday data is immutable; today's is mutable but acceptable

### 6.8 Weekend/Holiday Handling
**Decision:** DynamoDB query range includes weekends; only trading day candles exist
**Behavior:** Works correctly - no trading data on weekends

---

## 7. Testing Strategy

**Note:** This section provides a quick reference. For the **authoritative canonical test plan** with 100+ tests derived by working backwards from failure modes, see **Section 15: Canonical Test Plan (Backwards-Engineered)**.

### 7.1 Unit Tests (Quick Reference)

**Cache Key Correctness (8 tests):** A1-A8 in Section 15.2
**Data Integrity (12 tests):** B1-B12 in Section 15.3
**Timing & TTL (12 tests):** C1-C12 in Section 15.4
**Race Conditions (12 tests):** D1-D12 in Section 15.5
**Dependency Failures (18 tests):** E1-E18 in Section 15.6
**State Management (9 tests):** F1-F9 in Section 15.7

| Priority | Test Category | Key Tests |
|----------|---------------|-----------|
| P0 | Race Conditions | `test_thundering_herd_prevention`, `test_lock_holder_crash_recovery` |
| P0 | Data Integrity | `test_price_precision_preserved_through_cache`, `test_volume_zero_not_null` |
| P0 | Dependency Failures | `test_dynamodb_read_failure_fallback_to_api` |
| P1 | Cache Keys | `test_cache_key_date_anchor_prevents_stale_data` |
| P1 | TTL | `test_ttl_today_intraday_5_minutes` |

### 7.2 Integration Tests (Quick Reference)

**Cache Key Consistency (2 tests):** A9-A10 in Section 15.2
**Data Integrity (2 tests):** B11-B12 in Section 15.3
**Timing (2 tests):** C11-C12 in Section 15.4
**Race Conditions (2 tests):** D11-D12 in Section 15.5
**Dependency Recovery (2 tests):** E13-E14 in Section 15.6
**State Coherence (2 tests):** F8-F9 in Section 15.7
**Edge Cases (3 tests):** G17-G19 in Section 15.8

| Test | Description |
|------|-------------|
| `test_ohlc_cache_round_trip` | First request writes to DDB, second reads from DDB |
| `test_cross_lambda_cache_coherence` | Lambda 1 writes, Lambda 2 reads correctly |
| `test_full_system_recovery_after_dynamodb_outage` | System recovers after DDB returns |

### 7.3 E2E Tests - Playwright (Quick Reference)

**Core Functionality (10 tests):** H1-H10 in Section 15.9
**Viewport Tests (4 tests):** H11-H14 in Section 15.9
**Network Conditions (3 tests):** H15-H17 in Section 15.9
**Animation & Timing (3 tests):** H18-H20 in Section 15.9

| Priority | Test | Description |
|----------|------|-------------|
| P0 | `test_chart_loads_on_first_visit` | Chart displays price data |
| P0 | `test_x_cache_source_header_visible` | Cache header accessible for verification |
| P1 | `test_cache_hit_faster_than_miss` | Cached response is measurably faster |
| P1 | `test_viewport_resize_maintains_data` | Resize doesn't cause data loss |
| P2 | `test_slow_3g_shows_loading_state` | Loading indicator on slow network |

### 7.4 Edge Cases (Quick Reference)

**See Section 15.8 for full edge case taxonomy (19 tests).**

Key edge cases to test:
- Weekend/holiday handling (G1-G3)
- Ticker format variations: BRK.B, single-letter F, 5-letter GOOGL (G4-G7)
- Delisted/changed tickers (G8-G9)
- Historical data boundaries: pre-IPO, very old data, stock splits (G10-G12)
- Date range boundaries: 5-year max, 1-day min, same-day custom (G13-G16)

---

## 8. Implementation Order

| # | Task | File | Priority | Depends On |
|---|------|------|----------|------------|
| 1 | Add lazy singleton clients to existing `dynamodb.py` | `shared/dynamodb.py` | P0 | - |
| 2 | Fix cache key design | `ohlc.py` | P0 | - |
| 3 | Add write-through | `ohlc.py` | P1 | #1, #2 |
| 4 | Add read-through cache class | `ohlc_cache.py` | P1 | #1 |
| 5 | Add strong consistent reads | `ohlc_cache.py` | P1 | #4 |
| 6 | Add cache reading (read-through) | `ohlc.py` | P2 | #2, #3, #4, #5 |
| 7 | Add `from_cached_candle()` | `models/ohlc.py` | P2 | - |
| 8 | Add X-Cache-Source response header | `ohlc.py` | P2 | #6 |
| 9 | Add local OHLC table | `run-local-api.py` | P3 | - |
| 10 | Add TTL configuration (conditional) | `dynamodb.tf`, `ohlc_cache.py` | P3 | #3 |
| 11 | Add distributed lock | `ohlc_cache.py`, `ohlc.py` | P2 | #3, #6 |
| 12 | Add CloudWatch alarms | `cloudwatch.tf` | P3 | #1, #3, #6 |
| 13 | Add smoke test script | `scripts/smoke-test-cache.py` | P3 | #8 |
| 14 | Add unit tests | `tests/unit/` | P4 | #1-13 |
| 15 | Add integration tests | `tests/integration/` | P4 | #1-13 |
| 16 | Add E2E tests | `frontend/tests/e2e/` | P4 | #1-13 |
| 17 | Audit async/sync antipattern | codebase-wide | P1 | - |

---

## 9. Success Criteria

### Functional
- [ ] First OHLC request populates DynamoDB
- [ ] Second OHLC request (same ticker/range) reads from DynamoDB
- [ ] Lambda cold start reads from DynamoDB (not Tiingo)
- [ ] Playwright tests pass without Tiingo connectivity

### Performance
- [ ] DynamoDB read latency < 100ms (vs Tiingo 500-2000ms)
- [ ] Cache hit rate > 90% for repeated requests

### Reliability
- [ ] DynamoDB errors fall through to Tiingo (graceful degradation)
- [ ] Partial cache hits handled correctly

---

## 10. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cache key mismatch | Medium | High | Thorough testing, log cache keys |
| DDB throttling | Low | Medium | On-demand billing mode, backoff, circuit breaker |
| Stale data served | Medium | Low | 90-day TTL, market hours logic |
| Timezone bugs | Medium | High | All timestamps UTC, unit tests |
| Circular imports | Low | Medium | Local imports in functions |
| Production bug requires rollback | Low | Medium | Fix-forward strategy (see below) |
| Hot partition (popular tickers) | Low | Medium | Monitor ConsumedCapacity; shard if needed (see below) |

### 10.2 Hot Partition Scaling Strategy

**Decision (Clarified 2026-02-03):** Accept current partition design - monitor for throttling, optimize if/when it occurs.

**Current Design:** `PK = "ohlc:{ticker}:{resolution}"` - all data for one ticker in same partition.

**Why Accept:**
- DynamoDB adaptive capacity handles moderate hot partitions automatically
- Distributed lock already serializes writes (reduces write contention)
- Write sharding complicates reads (scatter-gather across N shards)
- Would need sustained 3000+ RCU on single ticker to hit limits
- Current traffic is well below this threshold

**If Throttling Occurs (Future):**
1. Add CloudWatch alarm on `ConsumedReadCapacityUnits` > 2500 per partition
2. Implement write sharding: `PK = "ohlc:{ticker}:{resolution}#{hash(date) % 4}"`
3. Update reads to scatter-gather across shards
4. Consider DAX (DynamoDB Accelerator) for read-heavy patterns

### 10.1 Fix-Forward Strategy (No Feature Flag)

**Decision (Clarified 2026-02-03):** No feature flag - trust the tests, fix-forward if issues arise.

**Rationale:**
- Feature flags add complexity and potential failure modes
- Comprehensive test suite (unit, integration, E2E) provides confidence
- Circuit breaker provides automatic degradation if DynamoDB fails
- Graceful fallback to Tiingo API means users still get data

**If Issues Arise:**
1. Circuit breaker auto-triggers → system degrades to API-only (self-healing)
2. If persistent: deploy hotfix or revert commit (10-15 min deployment)
3. DynamoDB data can be purged via TTL or manual delete if corrupted
4. In-memory caches clear on Lambda cold start (force via deployment)

**Accepted Trade-off:** 10-15 min recovery time for full rollback vs. ongoing complexity of feature flag maintenance.

---

## Clarifications

**Full History:** See [ohlc-cache-remediation-clarifications.md](ohlc-cache-remediation-clarifications.md) for Rounds 1-15.

### Session 2026-02-06 (Round 18 - Architecture Reconciliation)

- Q: BatchWriteItem (Section 4.2 write-through, 25-item batches) vs ConditionExpression (`updated_at` from Round 16) are architecturally incompatible — DynamoDB BatchWriteItem does NOT support ConditionExpression. How do we reconcile? → A: **Drop `updated_at` ConditionExpression for cache writes** — accept that frozen Lambda can overwrite newer data (rare edge case). OHLC candle data is immutable historical data; the only risk is a frozen Lambda writing the same candle with a slightly different timestamp, which is idempotent. Lock acquisition (single PutItem) retains its ConditionExpression. Tests D15/D16 (`test_frozen_lambda_stale_write_rejected`, `test_conditional_write_newer_wins`) removed — candle writes are idempotent, no stale-write protection needed.

- Q: Codebase has 4 cache layers (not 3): Layer 0 `_tiingo_cache` (raw API, 1h TTL), Layer 1 `_ohlc_cache` dict (JSON response, 5-60min TTL), Layer 2 `OHLCReadThroughCache._cache` (PriceCandle list, 1h TTL), Layer 3 DynamoDB. Layers 1 and 2 store different types with different TTLs — dual in-memory caches cause invalidation risk and doubled heap usage. How do we consolidate? → A: **Replace `_ohlc_cache` dict with `OHLCReadThroughCache`** — single in-memory layer storing PriceCandle objects. Refactor `get_ohlc_data()` to use `OHLCReadThroughCache.get_or_fetch()` exclusively. Remove `_ohlc_cache`, `_get_cached_ohlc()`, `_set_cached_ohlc()`, `_ohlc_cache_stats`, `invalidate_ohlc_cache()`. Unified invalidation — one cache to clear, not two. Memory-efficient — no duplicate storage of same data in different formats. Return frozen/immutable copies from cache to prevent mutation on shared event loop.

- Q: `_calculate_ttl()` uses `date.today()` which returns UTC date. Between 4PM ET (market close) and midnight UTC (~3 hours/day), finalized daily data incorrectly gets 5-minute TTL instead of 90-day TTL because UTC date still equals "today" even though the market day is over. → A: **Use `datetime.now(ZoneInfo("America/New_York")).date()`** in `_calculate_ttl()`. `zoneinfo` is stdlib (Python 3.9+). Reuse existing `ET = ZoneInfo("America/New_York")` from `shared/utils/market.py`. Also use market-timezone-aware date for the `is_today` check. Covers DST transitions automatically.

- Q: Existing `circuit_breaker.py` (474 lines, DynamoDB-persisted, thread-safe, Pydantic models, per-service locks, half-open state) vs spec's simple dict-based circuit breaker (Section 11.16) — two incompatible CB implementations in the same codebase. → A: **Reuse existing `CircuitBreakerManager`** — register `"dynamodb_cache"` as a new service. Widen `Literal["tiingo", "finnhub", "sendgrid"]` to include `"dynamodb_cache"`. Add entry in `_service_locks`. Gets DynamoDB persistence, thread-safety, half-open recovery, and unified observability for free. Remove spec's dict-based `_circuit_breaker`, `_is_circuit_open()`, `_record_failure()`, `_record_success()` from Section 11.16. Async wrapper calls `CircuitBreakerManager.can_execute("dynamodb_cache")` on event loop thread (preserving thread-boundary rule).

- Q: Eager singleton `aws_clients.py` (Section 11.13) creates boto3 clients at module load time. But moto `@mock_aws` and LocalStack `endpoint_url` need to intercept client creation, which happens before test fixtures run. Module-level initialization breaks test isolation. → A: **Lazy singleton with `_reset_for_testing()`** — client created on first use (not import time), cached thereafter. `_reset_for_testing()` clears cached client so moto/@mock_aws works. Checks `LOCALSTACK_ENDPOINT` env var at creation time. Add to existing `shared/dynamodb.py` rather than creating new `aws_clients.py`. Uses Lambda Init phase burst CPU on first handler invocation (still fast). Pattern matches existing `chaos_injection.py:34-43` singleton.

### Session 2026-02-06 (Round 17 - Source Code Blind Spots)

- Q: Dual X-Ray instrumentation — existing codebase uses raw `aws-xray-sdk` (`patch_all()` in `handler.py:35`, 30+ `@xray_recorder.capture()` decorators across auth/notifications/alerts) while spec Section 12.4 introduces Powertools `Tracer`. How do we prevent double-patched boto3 clients and duplicate X-Ray segments? → A: **Coexist safely**: Use `Tracer(auto_patch=False)` for new cache code only. Existing `@xray_recorder.capture()` decorators remain untouched. No scope creep into auth/notifications/alerts in this PR. Full codebase migration to Powertools Tracer tracked as future work in HL.

- Q: `cachetools.TTLCache` is NOT thread-safe (per its docs), but `asyncio.to_thread()` introduces worker threads for DynamoDB I/O. If cache population happens on a worker thread while the event loop thread reads from TTLCache, internal LRU/TTL bookkeeping can corrupt. How do we prevent this? → A: **Event loop thread only**: `asyncio.to_thread()` wraps DynamoDB I/O exclusively and returns raw data. ALL TTLCache reads and writes happen on the event loop thread (after `await` returns). No threading lock needed. The existing `_ohlc_cache` dict pattern already works this way.

- Q: Circuit breaker (`_record_failure()`, `_is_circuit_open()`) is module-level mutable state placed inside sync `get_cached_candles()`/`put_cached_candles()` which run inside `asyncio.to_thread()` worker threads — violating the event-loop-only rule from Q2. Lock heartbeat (Round 16) also implies a background thread. How do we reconcile? → A: **Circuit breaker in async layer, drop heartbeat**: Move `_is_circuit_open()` and `_record_failure()` to the async wrapper functions (event loop thread). Remove background heartbeat thread entirely — 30s lock TTL already handles crash recovery, `updated_at` ConditionExpression (Round 16) handles stale writes from frozen Lambdas. Heartbeat adds complexity with no coverage gap it uniquely closes. Tests D18/D19 (heartbeat-specific) removed; D20 (FIS latency injection) retained.

- Q: Existing `tenacity`-based `@dynamodb_retry` in `shared/retry.py` (3 attempts, exponential backoff, retryable error codes) vs three hand-rolled retry patterns in spec. How do we standardize? → A: **Option C — Smart batch retry in `retry.py`**: Create `dynamodb_batch_retry` in `shared/retry.py` that extracts and re-sends only `UnprocessedItems` (not the entire batch) using the existing exponential backoff constants. Use `@dynamodb_retry` for single-item DynamoDB operations (Query, PutItem). Hand-rolled polling loop stays for lock-wait only (semantically a poll, not a retry). X-Ray guard: configure tenacity to NOT start a new X-Ray subsegment per retry attempt — use a single subsegment for the entire logical batch operation to prevent cluttered traces. This is the scale-ready choice for bursty customer-facing traffic where dumb retries would multiply WCU pressure.

- Q: `PriceCandle.volume: int | None` allows `None` to leak to API responses, but `CachedCandle.volume: int = 0` rejects `None`. The round-trip `PriceCandle → candles_to_cached() → int(None)` crashes. Should we tighten the type? → A: **Tighten to `int = 0`** across ALL models and adapters. Full blast radius (7 source files, 3 test files):
  - `models/ohlc.py:86` — `volume: int | None = Field(None, ge=0)` → `volume: int = Field(0, ge=0)`
  - `adapters/base.py:73` — `OHLCCandle.volume: int | None = None` → `volume: int = 0`
  - `adapters/tiingo.py:333` — `volume=... else None` → `volume=... else 0`
  - `adapters/tiingo.py:446` — `volume=None` → `volume=0`
  - `adapters/finnhub.py:378` — `volume=... else None` → `volume=... else 0`
  - `ohlc_cache.py:374` — belt-and-suspenders: `int(getattr(candle, "volume", 0) or 0)`
  - `models/volatility_metric.py:17` — already `volume: int` (no change)
  - Tests: `test_ohlc_contract.py:22`, `test_tiingo.py:290` (`is None` → `== 0`), `ohlc_validator.py:138`
  - Frontend `chart.ts:50` — `volume?: number` unchanged (handles `0` correctly)

### Session 2026-02-05 (Round 16 - Debugging Nightmare Prevention)

**Methodology:** Working backwards from "What makes caching bugs a debugging nightmare?" to derive tests that catch issues before production.

- Q: How can we trace a single OHLC request through all 3 cache layers (in-memory → DynamoDB → Tiingo) when debugging production issues? → A: **Composite approach (X-Ray + EMF + ServiceLens)**:
  - Use X-Ray segments/subsegments for cache layer timing (already using Lambda Powertools)
  - Use CloudWatch Embedded Metric Format (EMF) for cache metrics - cheaper than PutMetricData API (only pay for log ingestion)
  - Inject X-Ray Trace ID into all logs automatically (Powertools does this)
  - Use CloudWatch ServiceLens as single dashboard combining traces + metrics + logs with automatic correlation
  - Smart sampling: 1 req/sec + 5% of traffic to keep X-Ray costs negligible while capturing statistically significant data
  - Annotations on traces: `put_annotation("CacheLayer", "dynamodb")` for filtering by cache behavior
  - Add tests: O3 `test_trace_id_propagated_through_cache_layers`, O4 `test_emf_metrics_emit_cache_hit_miss`

- Q: What happens when Lambda is frozen (not crashed) mid-request due to concurrency limit? Could it overwrite data from a later request after lock TTL expires? → A: ~~**Conditional write with timestamp-based ConditionExpression**~~ (SUPERSEDED by Round 18 Q1: `updated_at` ConditionExpression dropped because BatchWriteItem does not support it, and OHLC candle data is idempotent — writing the same candle twice is harmless):
  - ~~Add `updated_at` timestamp to each cache item~~ (REMOVED)
  - ~~DynamoDB write uses `ConditionExpression: "attribute_not_exists(updated_at) OR updated_at < :new_timestamp"`~~ (REMOVED)
  - Lock acquisition PutItem retains its ConditionExpression (single-item operation, no conflict)
  - Frozen Lambda writes are harmless: same immutable candle data, same PK/SK → DynamoDB overwrites with identical values
  - ~~Add tests: D15 `test_frozen_lambda_stale_write_rejected`, D16 `test_conditional_write_newer_wins`~~ (REMOVED — candle writes are idempotent)

- Q: How do we prevent thundering herd when multiple Lambdas cold start simultaneously after DynamoDB outage? → A: **Existing lock is sufficient**:
  - Distributed lock already ensures only 1 Lambda calls Tiingo (thundering herd to external API prevented)
  - 9 waiters polling DynamoDB every 200ms = 45 queries/sec - DynamoDB handles this easily with on-demand billing
  - DynamoDB adaptive capacity absorbs recovery load spikes automatically
  - No additional jitter or rate limiting needed - complexity not justified
  - Add test: D17 `test_concurrent_cold_starts_single_api_call` (verify only 1 Tiingo call for 10 concurrent requests)

- Q: Should tests verify accessibility (keyboard navigation, screen reader) and touch gestures (pinch-to-zoom, swipe)? → A: **Touch gestures only (MVP), defer full accessibility to future work**:
  - Add H28-H30 for mobile touch interactions (pinch-to-zoom chart, swipe between timeframes, tap for tooltip)
  - Full accessibility suite (keyboard, ARIA, screen reader, high contrast) tracked in `future/accessibility-audit.md`
  - Touch is priority because mobile is primary user base for chart viewing
  - Link accessibility future work in Section 14

- Q: How do we test "gray failure" where DynamoDB is slow (1500ms) but not failing? → A: **~~Lock holder heartbeat with~~ AWS FIS testing** (Updated 2026-02-06: heartbeat removed per Round 17 Q3 — background threads violate event-loop-only thread boundary rule and freeze with Lambda runtime; 30s lock TTL covers crash/freeze scenarios; candle writes are idempotent per Round 18 Q1):
  - ~~Lock holder updates `last_heartbeat` attribute on lock item every 5 seconds during long operations~~ (REMOVED)
  - ~~Waiters check: if `currentTime - last_heartbeat < threshold`, continue polling~~ (REMOVED)
  - Lock waiters rely on 30s TTL for crash recovery; candle writes are idempotent (frozen Lambda overwrites same data harmlessly)
  - Use AWS Fault Injection Service (FIS) in preprod to inject DynamoDB latency (40ms → 1500ms)
  - Confirms lock TTL + conditional writes handle gray failures without heartbeat complexity
  - ~~Add tests: D18 `test_lock_heartbeat_updated_during_slow_operation`, D19 `test_waiter_respects_heartbeat_during_latency_spike`~~ (REMOVED)
  - Retained: D20 `test_fis_dynamodb_latency_injection_preprod`

- Q: What if Tiingo API returns two candles with identical timestamps (data quality issue)? → A: **Trust Tiingo but alert on duplicates**:
  - Assume Tiingo never returns duplicates (historical behavior supports this)
  - Add detection: scan response for duplicate timestamps before caching
  - If duplicates detected: log ERROR, emit CloudWatch metric `TiingoDuplicateTimestamp`, keep last occurrence
  - CloudWatch alarm on metric > 0 alerts team to investigate Tiingo data quality
  - Do NOT fail the request - user still gets data, we get alerted
  - Add tests: B13 `test_duplicate_timestamp_detected_and_logged`, B14 `test_duplicate_timestamp_keeps_last_occurrence`, O5 `test_duplicate_timestamp_alarm_fires`

- Q: How do we handle requests that span midnight market timezone? → A: **Cache key computed once at request start**:
  - Generate cache key at request entry point, store in request context
  - Use same key for both DynamoDB read and write
  - TTL calculation also uses request timestamp, not "now" timestamp
  - Prevents key mismatch between request phases
  - Edge case affects <0.01% of requests (11:59:58 PM - 12:00:02 AM window)
  - Add tests: C14 `test_midnight_spanning_request_consistent_cache_key`, C15 `test_ttl_uses_request_timestamp_not_current`

---

## 11. Critical Blind Spots (Principal Engineer Analysis)

This section documents silent failure modes discovered during deep-dive analysis. These are not just "edge cases" but architectural gaps that could cause production issues without any visible error.

### 11.1 Tests Give False Confidence

**Problem:** Unit tests for `get_cached_candles()` and `put_cached_candles()` pass (100% green), but the functions are NEVER called from production code.

**Impact:** CI pipeline shows green; team believes caching works; users experience 500-2000ms latency on every request.

**Decision (Clarified 2026-02-03):** Functional test - first request writes to mock DDB, second request reads from it (verify actual data round-trip).

**Required Fix:**
Add integration test that verifies complete cache round-trip:

```python
# tests/integration/test_ohlc_cache_integration.py
@pytest.fixture
def mock_tiingo_response():
    """Mock Tiingo API to return known candles."""
    return [OHLCCandle(date=date(2026, 1, 15), open=150.0, high=155.0, low=149.0, close=154.0, volume=1000000)]

def test_ohlc_cache_round_trip(mock_aws, test_client, mock_tiingo_response, mocker):
    """Verify first request writes to DDB, second request reads from DDB (not API)."""
    # Mock Tiingo to return known data
    mocker.patch.object(TiingoAdapter, 'get_ohlc', return_value=mock_tiingo_response)

    # First request: should call Tiingo API and write to DDB
    response1 = test_client.get("/api/v2/tickers/AAPL/ohlc?range=1W&resolution=D")
    assert response1.status_code == 200
    assert len(response1.json()["candles"]) == 1

    # Clear in-memory cache to force DDB read (Round 18: _ohlc_cache replaced by OHLCReadThroughCache)
    from src.lambdas.shared.cache.ohlc_cache import _ohlc_read_through_cache
    _ohlc_read_through_cache._cache.clear()

    # Second request: should read from DDB (Tiingo not called again)
    mocker.patch.object(TiingoAdapter, 'get_ohlc', side_effect=Exception("Should not be called"))
    response2 = test_client.get("/api/v2/tickers/AAPL/ohlc?range=1W&resolution=D")
    assert response2.status_code == 200
    assert len(response2.json()["candles"]) == 1  # Data came from DDB cache

    # Verify data integrity
    assert response1.json()["candles"] == response2.json()["candles"]
```

**Test guarantees:**
1. Fails if write-through is not called (second request would hit exception)
2. Fails if read-from-DDB is not called (second request would hit exception)
3. Fails if data is corrupted in round-trip (candle comparison fails)
4. Fails if cache key mismatch (second request wouldn't find first request's data)

### 11.2 Env Var Fallback Masks Misconfiguration

**Problem:** `_get_table_name()` has a fallback: if `OHLC_CACHE_TABLE` is not set, it constructs `{env}-ohlc-cache`. This fallback might not match the actual table name.

**Impact:** Query silently fails (caught as ClientError), logged as warning, gracefully degrades to API. No alarm fires.

**Decision (Clarified 2026-02-03):** Remove fallback, raise ValueError if env var missing (fail-fast).

**Required Fix:**
1. REMOVE the fallback - if env var is not set, raise immediately
2. Fail fast on Lambda cold start, not silently on first query

```python
def _get_table_name() -> str:
    """Get DynamoDB table name from environment.

    Raises:
        ValueError: If OHLC_CACHE_TABLE is not configured
    """
    table_name = os.environ.get(OHLC_CACHE_TABLE_ENV)
    if not table_name:
        raise ValueError(
            f"Environment variable {OHLC_CACHE_TABLE_ENV} must be set. "
            "Check Lambda configuration in Terraform."
        )
    return table_name
```

### 11.3 No Observability for Cache Effectiveness

**Problem:** In-memory cache tracks hits/misses (`_ohlc_cache_stats`). DynamoDB cache logs at DEBUG level (not visible in prod CloudWatch).

**Impact:** If DynamoDB queries silently fail for days, no metric reveals it. Team assumes caching is working.

**Mitigation:**
1. Add CloudWatch metrics for DynamoDB cache hit/miss
2. Log DynamoDB cache results at INFO level
3. Add dashboard widget for cache hit rate

```python
from src.lambdas.shared.dynamodb import get_cloudwatch_client

def _read_from_dynamodb(...):
    # ... query logic ...

    # Emit CloudWatch metric (using lazy singleton)
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace='SentimentAnalyzer/OHLCCache',
            MetricData=[{
                'MetricName': 'CacheHit' if result.cache_hit else 'CacheMiss',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': [
                    {'Name': 'Ticker', 'Value': ticker[:5]},  # Limit cardinality
                ]
            }]
        )
    except Exception:
        pass  # Metric emission should not fail the request
```

### 11.4 Async/Sync Event Loop Blocking

**Problem:** `get_ohlc_data()` is async. `get_cached_candles()` is sync (blocking). Sync call from async function blocks the event loop.

**Impact:** Lambda latency increases subtly; blamed on "slow API" not "event loop blocking". DynamoDB cold connections can hit 100-200ms.

**Decision (Clarified 2026-02-03):** Wrap sync DynamoDB calls in `asyncio.to_thread()` now.

**Required Fix:**
1. Rename `_read_from_dynamodb()` to `_read_from_dynamodb_sync()`
2. Create async wrapper `_read_from_dynamodb()` using `asyncio.to_thread()`
3. Similarly wrap `_write_through_to_dynamodb()` for consistency

```python
import asyncio

def _read_from_dynamodb_sync(...) -> list[PriceCandle] | None:
    """Sync implementation - do not call directly from async code."""
    # ... existing implementation ...

async def _read_from_dynamodb(...) -> list[PriceCandle] | None:
    """Non-blocking DynamoDB cache read.

    THREAD BOUNDARY (Clarified 2026-02-06): asyncio.to_thread() wraps
    ONLY the DynamoDB I/O. The returned data is handled on the event loop
    thread. Never touch TTLCache or module-level dicts inside to_thread().
    """
    return await asyncio.to_thread(
        _read_from_dynamodb_sync,
        ticker, source, resolution, start_date, end_date
    )

async def _write_through_to_dynamodb(...) -> None:
    """Non-blocking DynamoDB cache write.

    Same thread boundary rule: only DynamoDB I/O inside to_thread().
    """
    await asyncio.to_thread(
        _write_through_to_dynamodb_sync,
        ticker, source, resolution, ohlc_candles
    )
```

**Codebase Audit Required:**
This antipattern (sync network calls inside async functions without await) likely exists elsewhere. Audit for:
- `async def` functions calling `boto3` clients directly (DynamoDB, S3, SQS, etc.)
- `async def` functions calling `requests` library (should use `httpx` or `aiohttp`)
- Any `async def` with network I/O that doesn't have `await` on the I/O line

```bash
# Quick grep to find candidates:
grep -rn "async def" src/ | xargs -I{} grep -l "boto3\|requests\." {}
```

### 11.5 Timezone Edge Case: Naive Datetime

**Problem:** `candles_to_cached()` auto-converts naive datetime to UTC. But if Tiingo returns EST-local naive datetime, the timestamp will be wrong.

**Impact:** Candles stored with wrong timestamp; queries return empty; appears as "no data" not "wrong timezone".

**Mitigation:**
1. Assert timezone-awareness at entry point
2. Log warning if naive datetime received
3. Add unit test for timezone handling

```python
def candles_to_cached(candles: list, source: str, resolution: str) -> list[CachedCandle]:
    for candle in candles:
        ts = getattr(candle, 'date', getattr(candle, 'timestamp', None))
        if ts is not None and isinstance(ts, datetime) and ts.tzinfo is None:
            logger.warning(
                "Naive datetime received from adapter, assuming UTC",
                extra={"source": source, "timestamp": str(ts)}
            )
```

### 11.6 Resolution Format Mismatch

**Problem:** Cache module docstring shows resolution formats like `"5m"`, `"1h"`. OHLC endpoint uses `"5"`, `"60"`, `"D"`.

**Impact:** Misleading documentation could cause future developers to introduce format mismatches.

**Decision (Clarified 2026-02-03):** Use OHLCResolution enum values as-is ("5", "60", "D") - fix misleading docstring in `ohlc_cache.py`.

**Required Fix:**
1. Update docstring in `ohlc_cache.py` line 8-9 from `"5m#2025-12-27T10:30:00Z"` to `"5#2025-12-27T10:30:00Z"`
2. Verify current code already uses consistent format (it does - no mapping needed)
3. Add unit test asserting format consistency between write and read

### 11.7 Graceful Degradation = Silent Failure

**Problem:** All error handling returns `None` and falls through to API. This is "graceful" but also "silent".

**Impact:** Misconfiguration, permission issues, and bugs all look like "cache miss". No visibility into why cache isn't working.

**Decision (Clarified 2026-02-03):** Log at ERROR level for failures, add CloudWatch metric, add alarm with 1-hour mute period.

**Required Fix:**
1. Change `logger.warning()` to `logger.error()` for DynamoDB query/write failures
2. Add CloudWatch metric `OHLCCacheError` (Count) on each failure
3. Add CloudWatch alarm:
   - Metric: `OHLCCacheError > 0` in 1-minute period
   - Action: SNS notification
   - Treat missing data as: Not breaching
   - Period: 1 minute, Evaluation periods: 1
   - **Alarm suppression: 1 hour after first trigger** (prevents alert fatigue)

```python
from src.lambdas.shared.dynamodb import get_cloudwatch_client

# In _read_from_dynamodb() exception handler:
except Exception as e:
    logger.error(  # Changed from warning
        "DynamoDB cache read failed, falling back to API",
        extra=get_safe_error_info(e),
    )
    # Emit CloudWatch metric for alerting (using lazy singleton)
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace='SentimentAnalyzer/OHLCCache',
            MetricData=[{
                'MetricName': 'CacheError',
                'Value': 1,
                'Unit': 'Count',
            }]
        )
    except Exception:
        pass  # Metric emission should not fail the request
    return None
```

### 11.8 DynamoDB Query Pagination Not Handled

**Problem:** `get_cached_candles()` performs DynamoDB Query but doesn't check for `LastEvaluatedKey`. If results exceed 1MB, remaining data is silently lost.

**Impact:** Currently safe (max ~429KB for 1-month 1-minute data), but silent truncation if data grows.

**Decision (Clarified 2026-02-03):** Add warning log if `LastEvaluatedKey` present, but don't implement full pagination (detect before it bites).

**Required Fix:**
Add after line 185 in `ohlc_cache.py`:
```python
from src.lambdas.shared.dynamodb import get_cloudwatch_client

response = client.query(...)

# Detect pagination (would indicate silent data truncation)
if response.get("LastEvaluatedKey"):
    logger.error(
        "DynamoDB query returned paginated results - data truncated!",
        extra={
            "ticker": ticker,
            "source": source,
            "resolution": resolution,
            "items_returned": len(response.get("Items", [])),
        },
    )
    # Emit CloudWatch metric for alerting (using lazy singleton)
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace='SentimentAnalyzer/OHLCCache',
            MetricData=[{
                'MetricName': 'CachePaginationTruncation',
                'Value': 1,
                'Unit': 'Count',
            }]
        )
    except Exception:
        pass
```

### 11.9 Estimate Function Has Math Error

**Problem:** `_estimate_expected_candles()` line 353 has incorrect math:
```python
return int(days * 5 / 7 * 7)  # BUG: equals days * 5, not days * 5/7 * 6.5
```

**Impact:** Overestimates hourly candles by ~8%, causing valid cache hits to be rejected as "partial" (<80% coverage).

**Decision (Clarified 2026-02-03):** Fix math to match documented intent.

**Required Fix:**
Update `src/lambdas/dashboard/ohlc.py` line 353:
```python
# Before (broken)
return int(days * 5 / 7 * 7)

# After (fixed)
return int(days * 5 / 7 * 6.5)
```

### 11.10 80% Coverage Threshold Serves Incomplete Data

**Problem:** The 80% coverage threshold in `_read_from_dynamodb()` allows cache hits when up to 20% of data is missing. This is a "good enough" shortcut that can serve stale/incomplete data.

**Impact:** User may see gaps or miss the most recent candles (which are often the most valuable).

**Decision (Clarified 2026-02-03):** Remove 80% threshold entirely - require 100% expected candles for cache hit. User always gets complete data.

**Required Fix:**
Update `src/lambdas/dashboard/ohlc.py` `_read_from_dynamodb()`:
```python
# Before (80% threshold)
if len(price_candles) < expected * 0.8:
    logger.info("DynamoDB cache partial hit, fetching fresh", ...)
    return None

# After (100% threshold)
if len(price_candles) < expected:
    logger.info("DynamoDB cache incomplete, fetching fresh", ...)
    return None
```

**Also update:**
- Section 4.3 code example (change 0.8 to 1.0)
- Section 6.1 description (update "80%" references)
- Test `test_read_returns_none_on_partial_hit` (update threshold)

### 11.11 Three-Layer Cache with Partial Invalidation

**Problem:** Three caching layers exist:
1. Tiingo adapter in-memory cache (5 min TTL)
2. OHLC response in-memory cache (`_ohlc_cache`)
3. DynamoDB persistent cache (new)

Current `invalidate_ohlc_cache()` only clears layer 2. Callers might think they've invalidated all caches but layer 1 still serves stale data.

**Impact:** Subtle bugs where cache appears invalidated but stale data is still served. Integration tests may pass incorrectly.

**Decision (Clarified 2026-02-03):** Add unified `invalidate_all_caches(ticker)` that clears all layers. Remove/replace obsolete partial invalidate functions - ONE function clears ALL layers.

**Required Fix:**
1. Create `src/lambdas/shared/cache/cache_manager.py`:
```python
"""Unified cache management for OHLC data."""

from src.lambdas.shared.adapters.tiingo import invalidate_tiingo_cache
from src.lambdas.dashboard.ohlc import _ohlc_cache

def invalidate_all_caches(ticker: str | None = None) -> dict[str, int]:
    """Invalidate ALL cache layers for a ticker.

    Args:
        ticker: Stock symbol, or None to clear all entries

    Returns:
        Dict with count of invalidated entries per layer
    """
    results = {}

    # Layer 1: Tiingo adapter cache
    results["tiingo_adapter"] = invalidate_tiingo_cache(ticker)

    # Layer 2: OHLC response cache
    results["ohlc_response"] = _invalidate_ohlc_response_cache(ticker)

    # Layer 3: DynamoDB (optional - usually not needed, data is immutable)
    # Don't delete from DDB by default - historical data doesn't go stale

    return results
```

2. Remove or deprecate `invalidate_ohlc_cache()` from `ohlc.py` - replace all usages with `invalidate_all_caches()`

3. Add `invalidate_tiingo_cache()` to Tiingo adapter if not exists

### 11.12 Unprocessed BatchWriteItems Silently Lost

**Problem:** `put_cached_candles()` line 308-313 comment says "Retry unprocessed items" but NO RETRY actually happens. Unprocessed items are logged and then silently lost.

**Impact:** Under DynamoDB throttling, cache writes partially fail. Data is lost without alerting.

**Decision (Clarified 2026-02-03, updated 2026-02-06):** Use smart batch retry via new `dynamodb_batch_retry` in `shared/retry.py`. Re-sends only `UnprocessedItems` (not the full batch). Uses existing exponential backoff constants from `retry.py`. X-Ray: single subsegment for entire batch operation, NOT per retry attempt.

**Required Fix:**

1. Add to `src/lambdas/shared/retry.py`:
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_result

def _has_unprocessed_items(result: dict) -> bool:
    """Check if BatchWriteItem response has unprocessed items."""
    return bool(result.get("UnprocessedItems"))

def dynamodb_batch_write_with_retry(
    client,
    table_name: str,
    write_requests: list[dict],
    max_retries: int = 3,
) -> tuple[int, int]:
    """Smart batch write that retries ONLY unprocessed items.

    Uses exponential backoff constants from this module.
    Single X-Ray subsegment for the entire logical operation.

    Returns:
        Tuple of (written_count, failed_count)
    """
    written = 0
    total_failed = 0

    for i in range(0, len(write_requests), 25):
        batch = write_requests[i : i + 25]
        unprocessed = batch
        retries = 0

        while unprocessed and retries <= max_retries:
            response = client.batch_write_item(
                RequestItems={table_name: unprocessed},
            )
            new_unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])
            written += len(unprocessed) - len(new_unprocessed)
            unprocessed = new_unprocessed

            if unprocessed and retries < max_retries:
                retries += 1
                # Reuse backoff constants: 0.5s, 1s, 2s (matches dynamodb_retry)
                import time
                time.sleep(0.5 * (2 ** (retries - 1)))

        total_failed += len(unprocessed)

    return written, total_failed
```

2. Update `put_cached_candles()` to use the new helper:
```python
from src.lambdas.shared.retry import dynamodb_batch_write_with_retry

written, failed = dynamodb_batch_write_with_retry(
    client=client,
    table_name=table_name,
    write_requests=write_requests,
)

if failed:
    logger.error(
        "OHLC cache writes failed after retries",
        extra={"failed": failed, "written": written},
    )
    # CloudWatch metric via singleton
    try:
        get_cloudwatch_client().put_metric_data(
            Namespace='SentimentAnalyzer/OHLCCache',
            MetricData=[{
                'MetricName': 'UnprocessedWriteItems',
                'Value': failed,
                'Unit': 'Count',
            }]
        )
    except Exception:
        pass
```

### 11.13 Boto3 Clients Must Be Singletons

**Problem:** Multiple places create fresh boto3 clients on every call, adding ~50-100ms connection overhead per operation:
- `_get_dynamodb_client()` in `ohlc_cache.py`
- `boto3.client('cloudwatch')` in metric emission code
- Various other service clients across codebase

**Impact:** Operations that should be fast (~20ms) become slow (~70-120ms), negating performance benefits.

**Decision (Clarified 2026-02-03, strengthened 2026-02-04):**
**ALL boto3 clients must be singletons** - DynamoDB, CloudWatch, and any future service clients. This is an **architectural principle**, not a one-off fix.

**Audit Findings (boto3 client patterns in codebase):**

| Pattern | Files | Status |
|---------|-------|--------|
| Singleton (good) | `chaos_injection.py`, `chaos.py`, `analysis/handler.py` | ✓ |
| Fresh each call (bad) | `ohlc_cache.py`, `ticker_cache.py`, `sse_streaming/config.py`, `auth.py` | FIX |
| Dependency injection (good) | `notification.py`, `metrics.py` | ✓ |

**Required Fix - Lazy Singleton Client Factory (Clarified 2026-02-06 Round 18):**

Add lazy singleton pattern to existing `src/lambdas/shared/dynamodb.py` (no new `aws_clients.py` file needed). Lazy initialization ensures moto `@mock_aws` and LocalStack `endpoint_url` work correctly — client created on first use inside handler context, not at import time.

```python
# Add to src/lambdas/shared/dynamodb.py (alongside existing get_dynamodb_resource/get_table)
import os
import boto3

# ARCHITECTURAL PRINCIPLE: All boto3 clients MUST be singletons.
# Fresh client creation adds ~50-100ms overhead per call (TCP+TLS handshake).
#
# Pattern: Lazy singleton — created on first use, cached thereafter.
# Benefits:
# - First handler invocation absorbs client init (Lambda Init phase burst CPU)
# - Connection pools warm for all subsequent requests
# - moto/@mock_aws can intercept because client created after test fixtures
# - LocalStack endpoint_url picked up from env vars at creation time
#
# Usage:
#     from src.lambdas.shared.dynamodb import get_dynamo_client, get_cloudwatch_client
#
#     client = get_dynamo_client()  # Returns cached singleton

_DYNAMO_CLIENT = None
_CLOUDWATCH_CLIENT = None
_S3_CLIENT = None

def _get_region() -> str:
    return os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")

def get_dynamo_client():
    """Get DynamoDB client (lazy singleton)."""
    global _DYNAMO_CLIENT
    if _DYNAMO_CLIENT is None:
        endpoint_url = os.environ.get("LOCALSTACK_ENDPOINT")
        _DYNAMO_CLIENT = boto3.client(
            "dynamodb",
            region_name=_get_region(),
            endpoint_url=endpoint_url,
            config=RETRY_CONFIG,  # Reuse existing RETRY_CONFIG from dynamodb.py
        )
    return _DYNAMO_CLIENT

def get_cloudwatch_client():
    """Get CloudWatch client (lazy singleton)."""
    global _CLOUDWATCH_CLIENT
    if _CLOUDWATCH_CLIENT is None:
        endpoint_url = os.environ.get("LOCALSTACK_ENDPOINT")
        _CLOUDWATCH_CLIENT = boto3.client(
            "cloudwatch",
            region_name=_get_region(),
            endpoint_url=endpoint_url,
        )
    return _CLOUDWATCH_CLIENT

def get_s3_client():
    """Get S3 client (lazy singleton)."""
    global _S3_CLIENT
    if _S3_CLIENT is None:
        endpoint_url = os.environ.get("LOCALSTACK_ENDPOINT")
        _S3_CLIENT = boto3.client(
            "s3",
            region_name=_get_region(),
            endpoint_url=endpoint_url,
        )
    return _S3_CLIENT

def _reset_all_clients():
    """Clear cached clients. FOR TESTING ONLY.

    Call in test fixtures (e.g., conftest.py autouse fixture) so that
    moto/@mock_aws intercepts the next client creation.
    """
    global _DYNAMO_CLIENT, _CLOUDWATCH_CLIENT, _S3_CLIENT
    _DYNAMO_CLIENT = None
    _CLOUDWATCH_CLIENT = None
    _S3_CLIENT = None
```

**Update Metric Emission Code:**

```python
# Before (bad - creates fresh client every time)
cloudwatch = boto3.client('cloudwatch')
cloudwatch.put_metric_data(...)

# After (good - uses lazy singleton)
from src.lambdas.shared.dynamodb import get_cloudwatch_client

cloudwatch = get_cloudwatch_client()
cloudwatch.put_metric_data(...)
```

**Follow-up Tasks:**
1. Add lazy singleton functions to existing `src/lambdas/shared/dynamodb.py`
2. Update `ohlc_cache.py` to use `get_dynamo_client()` singleton
3. Update all metric emission code to use `get_cloudwatch_client()` singleton
4. Audit and fix `ticker_cache.py`, `sse_streaming/config.py`, `auth.py`
5. Add linting rule to prevent direct `boto3.client()` calls (future)
6. Add `_reset_all_clients()` call to `tests/conftest.py` autouse fixture

### 11.14 Volume=None Crashes Cache Write for Intraday Data

**Problem:** `candles_to_cached()` line 374 calls `int(getattr(candle, "volume", 0))`. Both Tiingo IEX and Finnhub can return `volume=None`. `int(None)` raises TypeError.

**Affected Adapters:**
- `tiingo.py` line 446: `volume=None,  # IEX doesn't include volume`
- `finnhub.py` line 378: `volume=int(volumes[i]) if i < len(volumes) else None`

**Impact:** Cache writes silently fail for intraday data from either adapter.

**Decision (Clarified 2026-02-03, expanded 2026-02-06):** Fix at ALL layers — tighten `volume` type to `int = 0` across every model and adapter. Pydantic enforces the invariant at the model boundary. Full blast radius documented in Round 17 Q5.

**Required Fixes (7 source files, 3 test files):**

1. **Model layer** — tighten types so Pydantic rejects `None`:
   ```python
   # models/ohlc.py:86
   volume: int = Field(0, ge=0, description="Trading volume")  # Was: int | None = Field(None, ...)

   # adapters/base.py:73 (OHLCCandle)
   volume: int = 0  # Was: int | None = None
   ```

2. **Adapter layer** — normalize at system boundary:
   ```python
   # tiingo.py:333
   volume=int(item["volume"]) if item.get("volume") else 0,  # Was: else None

   # tiingo.py:446
   volume=0,  # Was: volume=None  (IEX doesn't include volume in resampled data)

   # finnhub.py:378
   volume=int(volumes[i]) if i < len(volumes) else 0,  # Was: else None
   ```

3. **Cache layer** — belt-and-suspenders:
   ```python
   # ohlc_cache.py:374
   volume=int(getattr(candle, "volume", 0) or 0),  # Handles any lingering None
   ```

4. **Test updates** (must match new contract):
   ```python
   # tests/contract/test_ohlc_contract.py:22
   volume: int = 0  # Was: int | None = None

   # tests/unit/shared/adapters/test_tiingo.py:290
   assert result[0].volume == 0  # Was: assert result[0].volume is None

   # tests/fixtures/validators/ohlc_validator.py:138
   # Update None check to == 0 check
   ```

5. **Frontend** — no change needed (`chart.ts:50` `volume?: number` handles `0` correctly)

### 11.15 No Production Verification of Cache Effectiveness

**Problem:** Integration tests use moto (mocked DynamoDB), not real AWS. Deployments could fail due to IAM permissions, missing tables, or network issues that mocked tests don't catch.

**Impact:** Cache could be broken in production while all tests pass green.

**Decision (Clarified 2026-02-03, updated 2026-02-04):** Add post-deployment smoke test using `X-Cache-Source` response header for immediate verification (no CloudWatch latency).

**Required Fix:**
Add `scripts/smoke-test-cache.py`:
```python
#!/usr/bin/env python3
"""Post-deployment smoke test for OHLC cache.

Run after deployment to verify cache is working in production.
Usage: python scripts/smoke-test-cache.py --env preprod

Uses X-Cache-Source response header for immediate verification.
No CloudWatch latency - results available instantly.

Authentication: Requires SMOKE_TEST_API_KEY env var.
Pipeline worker retrieves from AWS Secrets Manager at job start.
"""
import argparse
import os
import requests
import sys
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "preprod", "prod"])
    args = parser.parse_args()

    # Authentication - API key from pipeline worker environment
    api_key = os.environ.get("SMOKE_TEST_API_KEY")
    if not api_key:
        print("❌ SMOKE_TEST_API_KEY not set")
        print("   Pipeline worker should retrieve from Secrets Manager:")
        print("   aws secretsmanager get-secret-value --secret-id sentiment-analyzer/smoke-test-api-key")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {api_key}"}

    api_url = f"https://api.{args.env}.sentiment-analyzer.example.com"
    ticker = "AAPL"
    endpoint = f"{api_url}/api/v2/tickers/{ticker}/ohlc?range=1W&resolution=D"

    print(f"Testing cache on {args.env}...")

    # Request 1: Should fetch from Tiingo and write to DynamoDB
    print(f"Request 1: Fetching {ticker}...")
    response1 = requests.get(endpoint, headers=headers)
    assert response1.status_code == 200, f"Request 1 failed: {response1.status_code}"

    source1 = response1.headers.get("X-Cache-Source", "unknown")
    print(f"  X-Cache-Source: {source1}")

    # First request should be "tiingo" (or "dynamodb" if already cached)
    if source1 == "tiingo":
        print("  ✓ Fresh fetch from Tiingo (expected for first request)")
    elif source1 in ("dynamodb", "in-memory"):
        print("  ✓ Already cached (previous test run?)")
    else:
        print(f"  ⚠ Unexpected source: {source1}")

    # Brief wait for write-through (should be fast, but give it 1s)
    time.sleep(1)

    # Request 2: Should read from DynamoDB or in-memory cache
    print(f"Request 2: Fetching {ticker} again...")
    response2 = requests.get(endpoint, headers=headers)
    assert response2.status_code == 200, f"Request 2 failed: {response2.status_code}"

    source2 = response2.headers.get("X-Cache-Source", "unknown")
    print(f"  X-Cache-Source: {source2}")

    # Second request MUST be from cache
    if source2 in ("dynamodb", "in-memory"):
        print(f"✅ PASS: Cache hit on second request (source: {source2})")
    elif source2 == "tiingo":
        print("❌ FAIL: Second request hit Tiingo - cache not working!")
        print("  Check: DynamoDB table exists, IAM permissions, env vars")
        exit(1)
    else:
        print(f"❌ FAIL: Unexpected cache source: {source2}")
        exit(1)

    # Verify data integrity
    candles1 = response1.json().get("candles", [])
    candles2 = response2.json().get("candles", [])

    if candles1 == candles2:
        print("✅ PASS: Data integrity verified (responses match)")
    else:
        print("❌ FAIL: Data mismatch between requests!")
        exit(1)

    print("\n🎉 All smoke tests passed!")

if __name__ == "__main__":
    main()
```

**Integration with CI/CD:**
Add to deployment pipeline after `terraform apply`:
```yaml
- name: Smoke test cache
  run: python scripts/smoke-test-cache.py --env ${{ env.ENVIRONMENT }}
```

**Benefits of Header-Based Verification:**
- Immediate result (no 2-minute CloudWatch latency)
- Works offline (no AWS CLI dependency for verification)
- Useful for local debugging too
- API contract, not log format dependency

### 11.16 No Circuit Breaker for DynamoDB Failures

**Problem:** If DynamoDB is unavailable, every request attempts read + write, adding ~100-200ms latency with no mechanism to skip failing operations.

**Impact:** During DynamoDB outages, all OHLC requests are slower even though graceful degradation works.

**Decision (Clarified 2026-02-03, updated 2026-02-06 Round 18):** Reuse existing `CircuitBreakerManager` from `shared/circuit_breaker.py` — register `"dynamodb_cache"` as a new service alongside `tiingo`/`finnhub`/`sendgrid`.

**Why reuse existing (Round 18):** The existing `CircuitBreakerManager` (474 lines) provides DynamoDB-persisted state (survives cold starts, shared across Lambda instances), per-service threading locks, half-open recovery, and unified observability. A second dict-based CB would fragment monitoring and lack persistence.

**Required Changes to `shared/circuit_breaker.py`:**
1. Widen service Literal: `Literal["tiingo", "finnhub", "sendgrid", "dynamodb_cache"]`
2. Add lock: `_service_locks["dynamodb_cache"] = threading.Lock()`
3. No other changes — existing `CircuitBreakerManager.can_execute()`, `record_failure()`, `record_success()` are generic.

**Integration in async wrapper layer (Clarified 2026-02-06):**

Circuit breaker checks MUST run on the event loop thread (async wrappers), NOT inside the sync functions that run in `asyncio.to_thread()`. This preserves the thread-boundary rule from Section 4.8.

```python
from src.lambdas.shared.circuit_breaker import CircuitBreakerManager

# In the async wrapper (event loop thread) — NOT inside get_cached_candles_sync()
async def _read_from_dynamodb(...) -> list[PriceCandle] | None:
    cb_manager = CircuitBreakerManager(table)
    if not cb_manager.can_execute("dynamodb_cache"):
        logger.debug("DynamoDB circuit open, skipping cache read")
        return None

    try:
        result = await asyncio.to_thread(
            _read_from_dynamodb_sync, ticker, source, resolution, start_date, end_date
        )
        cb_manager.record_success("dynamodb_cache")  # Event loop thread — safe
        return result
    except ClientError as e:
        cb_manager.record_failure("dynamodb_cache")  # Event loop thread — safe
        return None
```

---

## 12. Alerting & Operational Runbook

**Decision (Clarified 2026-02-03):** Tiered alerting to balance visibility without alert fatigue.

### 12.1 Alert Definitions

| Metric | Threshold | Destination | Severity | Response |
|--------|-----------|-------------|----------|----------|
| `OHLCCacheError` | >10 in 1 min | Slack #alerts | Warning | Investigate during business hours |
| `CircuitBreakerOpen` | >0 | PagerDuty | Critical | Page on-call immediately |
| `CachePaginationTruncation` | >0 | PagerDuty | Critical | Page on-call - data loss occurring |
| `UnprocessedWriteItems` | >100 in 5 min | Slack #alerts | Warning | Check DynamoDB throttling |
| `CacheHitRate` | <50% over 15 min | Slack #alerts | Warning | Investigate cache effectiveness |

### 12.2 Terraform Alert Configuration

**File:** `infrastructure/cloudwatch.tf`

```hcl
# Critical: Circuit Breaker Open - page immediately
resource "aws_cloudwatch_metric_alarm" "ohlc_circuit_breaker" {
  alarm_name          = "${var.environment}-ohlc-circuit-breaker-open"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CircuitBreakerOpen"
  namespace           = "SentimentAnalyzer/OHLCCache"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "OHLC cache circuit breaker opened - DynamoDB may be unavailable"
  alarm_actions       = [aws_sns_topic.pagerduty.arn]
  ok_actions          = [aws_sns_topic.pagerduty.arn]
  treat_missing_data  = "notBreaching"
}

# Critical: Data Truncation - page immediately
resource "aws_cloudwatch_metric_alarm" "ohlc_pagination_truncation" {
  alarm_name          = "${var.environment}-ohlc-pagination-truncation"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CachePaginationTruncation"
  namespace           = "SentimentAnalyzer/OHLCCache"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "OHLC cache query exceeded 1MB - data truncated!"
  alarm_actions       = [aws_sns_topic.pagerduty.arn]
  treat_missing_data  = "notBreaching"
}

# Warning: Cache errors above threshold - Slack notification
resource "aws_cloudwatch_metric_alarm" "ohlc_cache_errors" {
  alarm_name          = "${var.environment}-ohlc-cache-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CacheError"
  namespace           = "SentimentAnalyzer/OHLCCache"
  period              = 60
  statistic           = "Sum"
  threshold           = 10
  alarm_description   = "OHLC cache errors elevated - investigate DynamoDB health"
  alarm_actions       = [aws_sns_topic.slack_alerts.arn]
  treat_missing_data  = "notBreaching"
}

# Warning: Write failures - Slack notification
resource "aws_cloudwatch_metric_alarm" "ohlc_unprocessed_writes" {
  alarm_name          = "${var.environment}-ohlc-unprocessed-writes"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "UnprocessedWriteItems"
  namespace           = "SentimentAnalyzer/OHLCCache"
  period              = 300
  statistic           = "Sum"
  threshold           = 100
  alarm_description   = "OHLC cache write failures elevated - check DynamoDB capacity"
  alarm_actions       = [aws_sns_topic.slack_alerts.arn]
  treat_missing_data  = "notBreaching"
}
```

### 12.3 On-Call Response Procedures

**CircuitBreakerOpen Alert:**
1. Check AWS Health Dashboard for DynamoDB issues in region
2. Check CloudWatch Logs for error patterns: `filter @message like /DynamoDB/`
3. If DynamoDB healthy, check Lambda IAM permissions
4. Circuit auto-resets after 60s; monitor for repeat triggers
5. If persistent, consider increasing circuit breaker threshold or timeout

**CachePaginationTruncation Alert:**
1. This indicates data volume exceeded 1MB query limit
2. Identify affected ticker/resolution from logs
3. Consider implementing pagination or reducing date range
4. Add to backlog for pagination implementation

**CacheError Slack Alert:**
1. Check during next business hours
2. Review CloudWatch Logs for error patterns
3. Typical causes: network blips, IAM token refresh, cold start timing
4. If sustained >1 hour, escalate to on-call

### 12.4 Observability Infrastructure (Clarified 2026-02-04)

**Decision:** Use AWS Lambda Powertools for Python with full observability (Logger + Metrics + X-Ray 100%).

**Cost:** ~$18/month at 100K requests/day for maximum debugging visibility.

**Dependency:** Add `aws-lambda-powertools>=2.0` to `requirements.txt`.

**IMPORTANT — Dual Instrumentation Guard (Clarified 2026-02-06):**
The existing codebase uses raw `aws-xray-sdk` (`patch_all()` in `handler.py:35`, 30+ `@xray_recorder.capture()` decorators). To avoid double-patched boto3 clients and duplicate X-Ray segments, Powertools Tracer MUST use `auto_patch=False`. Existing decorators are NOT migrated in this PR. Full Powertools migration tracked in HL as future work.

**Implementation Pattern:**

```python
# src/lambdas/shared/observability.py
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit

logger = Logger(service="ohlc-cache")
tracer = Tracer(service="ohlc-cache", auto_patch=False)  # handler.py already calls patch_all()
metrics = Metrics(service="ohlc-cache", namespace="SentimentAnalyzer/OHLCCache")

# Usage in handler
@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    logger.info("Cache lookup", extra={
        "ticker": ticker,
        "cache_key": cache_key,
        "resolution": resolution,
    })
    # request_id, function_name, cold_start automatically injected
```

**Cache-Specific Logging:**

```python
# Log on cache miss (for debugging)
@tracer.capture_method
def _read_from_dynamodb(ticker: str, source: str, resolution: str, ...):
    with tracer.provider.in_subsegment("dynamodb_cache_read") as subsegment:
        subsegment.put_annotation("ticker", ticker)
        subsegment.put_annotation("cache_key", cache_key)

        result = client.query(...)

        if not result.get("Items"):
            logger.info("Cache miss", extra={
                "ticker": ticker,
                "cache_key": cache_key,
                "reason": "no_items",
            })
        return result
```

**X-Ray Trace Structure:**
```
Lambda Handler
├── dynamodb_cache_read (annotation: ticker=AAPL, cache_key=ohlc:AAPL:D:1W:2026-02-04)
│   └── cache miss / cache hit
├── tiingo_api_call (if cache miss)
│   └── response time, status
└── dynamodb_cache_write (if cache miss)
    └── items written, TTL
```

**Smoke Test (O1):**

```python
# tests/integration/test_observability_smoke.py
def test_O1_correlation_id_in_logs(caplog, lambda_context):
    """Verify Powertools injects correlation ID into all log entries."""
    from src.lambdas.dashboard.handler import handler

    with caplog.at_level(logging.INFO):
        handler({"ticker": "AAPL"}, lambda_context)

    # Every log entry should have request_id
    for record in caplog.records:
        assert hasattr(record, "request_id") or "request_id" in record.message, \
            f"Log entry missing correlation ID: {record.message}"
```

**CloudWatch Logs Insights Query (for debugging):**
```sql
fields @timestamp, @message, ticker, cache_key, request_id
| filter @message like /Cache miss/
| sort @timestamp desc
| limit 100
```

---

## 15. Canonical Test Plan (Backwards-Engineered)

**Full Test Plan:** See [ohlc-cache-remediation-tests.md](ohlc-cache-remediation-tests.md) (160 tests across 11 categories; D15/D16 removed Round 18).

### Quick Reference

| Category | Tests | Focus |
|----------|-------|-------|
| A: Cache Keys | 10 | Stale data, key collisions |
| B: Data Integrity | 14 | Corruption, precision, truncation |
| C: Timing & TTL | 15 | Expiry, freshness, clock drift |
| D: Race Conditions | 17 | Thundering herd, locks, dirty reads (D15/D16 removed Round 18) |
| E: Dependencies | 30 | DynamoDB, Tiingo, CloudWatch outages |
| F: State Management | 11 | Multi-layer cache, invalidation |
| G: Edge Cases | 19 | Boundaries, holidays, ticker changes |
| H: Playwright | 29 | Viewport, touch, network, animation |
| S: Security | 5 | Secrets, PII, stack traces |
| M: Metrics | 5 | CloudWatch metric emission |
| O: Observability | 5 | X-Ray, EMF, alarms |

### Test Priority Matrix

| Priority | Tests | Run When |
|----------|-------|----------|
| P0 | D1-D5, B1-B5, E1-E4 | Every PR |
| P1 | A1-A6, C1-C5, F1-F3 | Every PR |
| P2 | D6-D10, G1-G10 | Daily CI |
| P3 | H11-H30, G11-G19 | Weekly CI |

---

## 13. References

- [HL-cache-remediation-checklist.md](docs/cache/HL-cache-remediation-checklist.md)
- [fix-cache-key.md](docs/cache/fix-cache-key.md)
- [fix-cache-writing.md](docs/cache/fix-cache-writing.md)
- [fix-cache-reading.md](docs/cache/fix-cache-reading.md)
- [fix-local-api-tables.md](docs/cache/fix-local-api-tables.md)
- [fix-cache-tests.md](docs/cache/fix-cache-tests.md)
- Feature 1087: OHLC Persistent Cache (original spec)
- Feature 1076/1078: Response cache improvements

---

## 14. Future Work

**Out of Scope for CACHE-001** - See separate specs for future work:

- [realtime-ohlc-two-zone-architecture.md](future/realtime-ohlc-two-zone-architecture.md)
- [observability-metric-coverage-audit.md](future/observability-metric-coverage-audit.md) - Full codebase audit for CloudWatch metric and warning emission coverage; pattern established in this spec's Section 15.15.1 to be ported codebase-wide
- [accessibility-audit.md](future/accessibility-audit.md) - Full accessibility suite including keyboard navigation (Tab, Enter, Arrow keys), ARIA labels for screen readers, high contrast mode, and reduced motion preferences. Mobile touch gestures (H28-H30) implemented in CACHE-001; full A11y compliance deferred.
- **WebSocket/Real-Time Cache Invalidation** (deferred from 15.19): When real-time price updates are implemented via WebSocket, explore cache invalidation via push rather than TTL expiry. Tests would verify: WebSocket message invalidates in-memory cache, DynamoDB item updated, connected clients receive fresh data.
- **Powertools Tracer Full Migration** (deferred from Round 17): Migrate all 30+ `@xray_recorder.capture()` decorators across auth, notifications, alerts, middleware, and SSE streaming to `@tracer.capture_method`. Remove raw `aws-xray-sdk` imports. Enables unified observability with auto-annotation, EMF integration, and single instrumentation layer. Track in HL.
- **Multi-Region/Disaster Recovery** (deferred from 15.19): If us-east-1 fails entirely, what happens? Considerations: DynamoDB Global Tables for cache replication, cross-region consistency guarantees (eventual vs strong), failover testing strategy. Tests would verify: cache readable from secondary region, write failover transparent to client, consistency window acceptable.

### Two-Zone Data Model (Future)

This spec addresses **Zone 1 (filled/locked buckets) only**:

| Zone | Description | This Spec | Future |
|------|-------------|-----------|--------|
| **Zone 1: Locked** | Completed intervals (immutable) | **Yes** | Reused |
| **Zone 2: In-Progress** | Current forming bar (mutable) | No | WebSocket ingestion |

**Design for Reusability:**
- Cache key structure supports future `is_closed` filtering
- DynamoDB schema compatible with `is_closed: bool` attribute
- Resolution enum covers all intervals (1m, 5m, 15m, 30m, 1h, 1d)
- Separate read/write functions can be extended for partial buckets

**Future Integration Point:**
```python
# Current (CACHE-001): Returns only locked buckets
candles = await _read_from_dynamodb(ticker, resolution, start, end)

# Future: Append current partial bucket from WebSocket/real-time source
if include_partial and end >= date.today():
    partial = await _get_partial_bucket(ticker, resolution)
    candles.append(partial)
```
