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

### 4.0 Request Context Object (Round 24)

**File:** `src/lambdas/dashboard/ohlc.py`

**Problem (identified Round 24):** The call chain `get_ohlc_handler → _get_ohlc_data_with_write_context → _fetch_with_lock → _read_from_dynamodb` passes 5-7 individual parameters through each level. `start_date`, `end_date`, and `source` were undefined in intermediate signatures (NameError). Adding future params (e.g., `user_tier`, `is_test_request`) would require refactoring every function in the chain.

**Solution:** Frozen dataclass groups all request-scoped values. Constructed once at handler entry point, passed as single `ctx` param through the chain.

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class OHLCRequestContext:
    """Immutable request context for the OHLC cache pipeline.

    Constructed once in get_ohlc_handler(), passed through the entire
    L1 → L2 → Lock → Tiingo → Phase 2 chain. Frozen for thread safety
    (safe to pass into asyncio.to_thread() closures).
    """
    ticker: str
    resolution: str
    time_range: str
    start_date: date
    end_date: date
    source: str        # "tiingo" or "finnhub" — determined at handler entry
    cache_key: str     # Pre-computed by _get_ohlc_cache_key()

    def to_metadata(self) -> dict:
        """For X-Ray put_metadata() and EMF dimensions."""
        return {
            "ticker": self.ticker,
            "resolution": self.resolution,
            "time_range": self.time_range,
            "source": self.source,
            "cache_key": self.cache_key,
        }
```

**Usage pattern:**
```python
# Handler entry point — construct once
start_date, end_date = _resolve_date_range(time_range)
cache_key = _get_ohlc_cache_key(ticker, resolution, time_range, start_date, end_date)
ctx = OHLCRequestContext(
    ticker=ticker, resolution=resolution, time_range=time_range,
    start_date=start_date, end_date=end_date,
    source=_get_default_source(ticker), cache_key=cache_key,
)

# Pass through chain
result, pending_write = await _get_ohlc_data_with_write_context(ctx, response)
```

**Test fixture pattern:**
```python
# tests/conftest.py
@pytest.fixture
def ohlc_ctx() -> OHLCRequestContext:
    return OHLCRequestContext(
        ticker="AAPL", resolution="D", time_range="1W",
        start_date=date(2026, 2, 1), end_date=date(2026, 2, 8),
        source="tiingo", cache_key="ohlc:AAPL:D:1W:2026-02-08",
    )

# Per-test override (frozen → use dataclasses.replace)
from dataclasses import replace
msft_ctx = replace(ohlc_ctx, ticker="MSFT", cache_key="ohlc:MSFT:D:1W:2026-02-08")
```

**Refactored signatures (Round 24):**

| Before | After |
|--------|-------|
| `_get_ohlc_data_with_write_context(ticker, resolution, time_range, response, cache_key)` | `_get_ohlc_data_with_write_context(ctx: OHLCRequestContext, response: Response)` |
| `_fetch_with_lock(ticker, cache_key, source, resolution, start_date, end_date)` | `_fetch_with_lock(ctx: OHLCRequestContext)` |
| `_read_from_dynamodb(ticker, source, resolution, start_date, end_date)` | `_read_from_dynamodb(ctx: OHLCRequestContext)` |
| `_write_through_to_dynamodb(ticker, source, resolution, candles, end_date)` | `_write_through_to_dynamodb(ctx: OHLCRequestContext, candles: list[PriceCandle])` |
| Write context dict: `{"ticker": ..., "source": ..., "candles": ...}` | `{"ctx": ctx, "candles": candles}` |

### 4.0.1 Handler Entry Helpers (Round 25)

**File:** `src/lambdas/dashboard/ohlc.py`

**Problem (identified Round 25):** `_resolve_date_range(time_range)` and `_get_default_source(ticker)` are called at handler entry (lines 993, 998) to construct `OHLCRequestContext`, but neither function was defined anywhere in the spec or codebase. Double `NameError` — 100% crash rate before the cache pipeline even starts.

**Solution:** Define both as pure, stateless helper functions. No I/O, no state, trivially testable.

```python
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

# Reuse existing market timezone constant (shared/utils/market.py)
ET = ZoneInfo("America/New_York")

# Predefined time range mappings (calendar days, not trading days)
_TIME_RANGE_DAYS: dict[str, int] = {
    "1D": 1,
    "1W": 7,
    "1M": 30,
    "3M": 90,
    "6M": 180,
    "1Y": 365,
    "YTD": -1,  # Sentinel: computed dynamically
}

def _resolve_date_range(time_range: str) -> tuple[date, date]:
    """Map time_range string to (start_date, end_date) in ET market time.

    Uses market timezone (ET) per Round 18 — NOT date.today() (UTC).
    Prevents ~3-hour ET/UTC gap from creating wrong date anchors
    between 4PM ET and midnight UTC.

    For "custom" ranges, caller must pass start/end explicitly
    (not handled here — custom ranges bypass this helper).

    Raises:
        ValueError: If time_range is not a recognized predefined range.
    """
    market_today = datetime.now(ET).date()
    end_date = market_today

    if time_range == "custom":
        raise ValueError(
            "Custom ranges must provide explicit start_date and end_date. "
            "Do not call _resolve_date_range for custom ranges."
        )

    if time_range == "YTD":
        start_date = date(market_today.year, 1, 1)
        return start_date, end_date

    days = _TIME_RANGE_DAYS.get(time_range)
    if days is None:
        raise ValueError(
            f"Unknown time_range '{time_range}'. "
            f"Valid values: {', '.join(_TIME_RANGE_DAYS.keys())}, custom"
        )

    start_date = end_date - timedelta(days=days)
    return start_date, end_date


def _get_default_source(ticker: str) -> str:
    """Return the primary OHLC data provider for a ticker.

    Currently returns "tiingo" unconditionally — Tiingo is the primary
    source for all OHLC data. Finnhub is available as a manual fallback
    (resolution fallback uses it), but automatic source selection is
    future work.

    Centralized here as a single "knob" — if Tiingo has a major outage,
    update this one function to re-route dashboard traffic to Finnhub.
    """
    return "tiingo"
```

**Test coverage:**
```python
# tests/unit/test_ohlc_helpers.py
from datetime import date
from freezegun import freeze_time

class TestResolveDateRange:
    @freeze_time("2026-02-08 14:00:00", tz_offset=-5)  # 2PM ET
    def test_1W_returns_7_day_range(self):
        start, end = _resolve_date_range("1W")
        assert end == date(2026, 2, 8)
        assert start == date(2026, 2, 1)

    @freeze_time("2026-02-08 14:00:00", tz_offset=-5)
    def test_YTD_starts_jan_1(self):
        start, end = _resolve_date_range("YTD")
        assert start == date(2026, 1, 1)

    def test_custom_raises_ValueError(self):
        with pytest.raises(ValueError, match="custom"):
            _resolve_date_range("custom")

    def test_unknown_range_raises_ValueError(self):
        with pytest.raises(ValueError, match="Unknown"):
            _resolve_date_range("5Y")

class TestGetDefaultSource:
    def test_returns_tiingo(self):
        assert _get_default_source("AAPL") == "tiingo"
        assert _get_default_source("BRK.B") == "tiingo"
```

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

async def _write_through_to_dynamodb(  # Round 23: async def (was sync def — await crashed with TypeError)
    ctx: OHLCRequestContext,  # Round 24: replaces (ticker, source, resolution, end_date) params
    candles: list[PriceCandle],  # Round 23: renamed from ohlc_candles to match domain language
) -> None:
    """Phase 2 Awaited: Persist OHLC candles to DynamoDB for cross-invocation caching.

    Awaited before handler returns to prevent Lambda freeze mid-write.
    Invisible to user latency; additive to billed duration only (~50ms normal).
    Errors are logged but do not fail the request (non-fatal).

    Contributes to _DDB_BREAKER health (Round 24 Q2): record_success() on
    successful write, record_failure() on exception. DynamoDB is a single
    service — write failures are a leading indicator of read failures.
    During HALF_OPEN, a successful write helps close the circuit faster.

    Uses asyncio.to_thread() to offload blocking boto3 batch_write_item() to a
    worker thread (Round 1 Q4 architectural decision). Prevents event loop freeze
    during DynamoDB throttling (up to 10s hard cap).

    Invariant: User P99 = 5s (Phase 1). Write integrity = guaranteed (Phase 2).

    Args:
        ctx: Frozen request context (Round 24). Thread-safe for asyncio.to_thread().
        candles: PriceCandle list from Tiingo/Finnhub fetch (Round 23: aligned
                 with _fetch_with_lock write_context dict key)
    """
    # Round 24 Q2: Breaker check encapsulated here (was in handler guard)
    if _DDB_BREAKER.is_open():
        logger.debug("DynamoDB circuit open, skipping write-through",
                      extra={"ticker": ctx.ticker})
        return

    try:
        cached_candles = candles_to_cached(candles, ctx.source, ctx.resolution)
        if not cached_candles:
            logger.debug("No candles to cache", extra={"ticker": ctx.ticker})
            return

        # Offload blocking DynamoDB I/O to worker thread (Round 23)
        # Event loop remains free to serve concurrent requests during Phase 2
        # ctx is frozen (thread-safe) — safe to read from worker thread
        written = await asyncio.to_thread(
            put_cached_candles,
            ticker=ctx.ticker,
            source=ctx.source,
            resolution=ctx.resolution,
            candles=cached_candles,
            end_date=ctx.end_date,  # For TTL calculation
        )

        # Round 24 Q2: Write success feeds into breaker — unified health signal
        _DDB_BREAKER.record_success()

        logger.info(
            "OHLC write-through complete",
            extra={
                "ticker": ctx.ticker,
                "source": ctx.source,
                "resolution": ctx.resolution,
                "candles_written": written,
            },
        )
    except Exception as e:
        # Round 24 Q2: Write failure feeds into breaker — proactive resilience
        # Prevents burning 200ms per request on a dead write path
        _DDB_BREAKER.record_failure()

        logger.warning(
            "OHLC write-through failed",
            extra=get_safe_error_info(e),
        )
```

**Call Site (Round 21+):**
Called exclusively from `get_ohlc_handler()` Phase 2, outside the `asyncio.wait_for(timeout=5.0)` boundary. No longer called inline at individual fetch sites — write context is passed up from `_fetch_with_lock()` through `_get_ohlc_data_with_write_context()` to the handler, which awaits the write in Phase 2.

**Constraints:**
- Never cache error responses (404, 503)
- Never cache empty candle lists
- Phase 2 awaited: errors logged, non-fatal, but write completion guaranteed under normal conditions (Round 22 — replaces "fire-and-forget" per Round 20/21 architecture)
- Skipped when DDB circuit breaker is open (encapsulated: `_DDB_BREAKER.is_open()` check inside function, Round 24 Q2)
- Contributes to `_DDB_BREAKER` health: `record_success()` on write completion, `record_failure()` on exception (Round 24 Q2 — unified breaker visibility)

### 4.3 Cache Reading (Query DynamoDB First)

**File:** `src/lambdas/dashboard/ohlc.py`
**New Functions:** `_read_from_dynamodb_sync()` (inner sync logic), `_read_from_dynamodb()` (async wrapper — see Section 11.7), `_estimate_expected_candles()`, `_build_response_from_cache()`

**Implementation (sync inner function — Round 25: renamed from `_read_from_dynamodb`):**

> **IMPORTANT:** This is the sync inner function. It performs blocking DynamoDB I/O.
> Callers MUST use the async wrapper `_read_from_dynamodb()` from Section 11.7,
> which wraps this in `asyncio.to_thread()` and manages `_DDB_BREAKER` state.
> Direct calls from async code will block the event loop.

```python
from datetime import UTC, datetime, time as dt_time
from src.lambdas.shared.cache.ohlc_cache import get_cached_candles

def _read_from_dynamodb_sync(
    ctx: OHLCRequestContext,  # Round 24: replaces (ticker, source, resolution, start_date, end_date)
    consistent_read: bool = False,  # Round 20: eventual (1 RCU) vs strong (2 RCU)
) -> list[PriceCandle] | None:
    """Sync inner implementation: query DynamoDB for cached OHLC candles.

    NOTE: Must be called via the async wrapper _read_from_dynamodb() in
    Section 11.7. The async wrapper adds: (1) _DDB_BREAKER.is_open() guard,
    (2) asyncio.to_thread() for non-blocking I/O, (3) record_success/failure
    for circuit breaker health. This function contains only the data logic.

    Returns None if:
    - No data found
    - Query fails (graceful degradation)
    - Incomplete data (<100% expected candles)
    """
    try:
        start_time = datetime.combine(ctx.start_date, dt_time.min, tzinfo=UTC)
        end_time = datetime.combine(ctx.end_date, dt_time.max, tzinfo=UTC)

        result = get_cached_candles(
            ticker=ctx.ticker,
            source=ctx.source,
            resolution=ctx.resolution,
            start_time=start_time,
            end_time=end_time,
        )

        if not result.cache_hit or not result.candles:
            logger.debug("DynamoDB cache miss", extra={"ticker": ctx.ticker})
            return None

        # Convert CachedCandle to PriceCandle
        price_candles = [
            PriceCandle.from_cached_candle(c, ctx.resolution)  # Round 25: was bare `resolution` (NameError)
            for c in result.candles
        ]

        # Validate coverage (100% required - no partial hits)
        # Round 26 Q2: resolution must be OHLCResolution enum for type-safe bars_per_day lookup
        res_enum = OHLCResolution(ctx.resolution)  # str → enum conversion
        expected = _estimate_expected_candles(ctx.start_date, ctx.end_date, res_enum)
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
# NOTE: This is the simplified pre-Round-20 version. See Section 4.8 for
# the canonical implementation with degraded mode, uniform tuple returns,
# Round 24 OHLCRequestContext, and two-phase write architecture.
async def _fetch_with_lock(ctx: OHLCRequestContext):
    """Fetch from API with distributed lock to prevent thundering herd."""

    lock_id = _acquire_fetch_lock(ctx.cache_key)

    if lock_id:
        try:
            candles = await _fetch_from_tiingo(ctx.ticker, ...)
            return candles, {"ctx": ctx, "candles": candles}
        finally:
            _release_fetch_lock(ctx.cache_key, lock_id)
    else:
        for _ in range(LOCK_MAX_RETRIES):
            await asyncio.sleep(LOCK_WAIT_MS / 1000)
            cached = await _read_from_dynamodb(ctx)
            if cached:
                return cached, None

        logger.warning("Lock wait timeout, falling back to API fetch")
        candles = await _fetch_from_tiingo(ctx.ticker, ...)
        return candles, {"ctx": ctx, "candles": candles}
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
from collections.abc import Callable, Awaitable  # PEP 585/603 (Round 19 Q5)
from src.lib.timeseries.cache import ResolutionCache  # Reuse internal LRU (Round 19 Q5)

class OHLCReadThroughCache:
    """In-memory cache with read-through to DynamoDB.

    Eviction Policy: LRU (Least Recently Used) via ResolutionCache when max_size reached.
    This is acceptable because DynamoDB provides the durable cache layer.
    Evicted entries will be re-fetched from DynamoDB (~40ms) on next access.

    Age Tracking (Clarified 2026-02-08 Round 21, refined Round 22):
    ResolutionCache stores (value, inserted_at) tuples internally — atomic eviction
    ensures timestamp is physically removed when LRU evicts an entry. No separate
    _timestamps dict needed. Eliminates "zombie age" bug where evicted-then-reinserted
    keys could return stale ages. get_age() derives from tuple metadata.

    ResolutionCache Modification Required (Round 22, extended Round 23):
    - set(key, value) stores (value, time.time()) tuple internally
    - get(key) returns unwrapped value (not the tuple)
    - get_with_age(key) -> tuple[Any | None, float]: returns (value, age_seconds) on hit,
      returns (None, 0.0) sentinel tuple on miss (Round 23 — zero-surprise contract,
      callers always destructure safely without guards or try/except)
    - Eviction (popitem) removes both value and timestamp atomically
    - invalidate(prefix: str) -> int: removes all keys starting with prefix, returns count (Round 23)
    - clear() -> int: clears all entries, returns count of evicted items (Round 23)
    - ~10-15 line delta to existing OrderedDict-based implementation

    THREAD SAFETY (Clarified 2026-02-06, updated 2026-02-07 Round 20):
    ResolutionCache (like cachetools.TTLCache) is NOT thread-safe.
    ALL reads/writes via self._cache MUST happen on the event loop thread.
    asyncio.to_thread() wraps only the raw DynamoDB I/O and returns data
    to the event loop thread, which then updates the cache via .get()/.set().
    Never pass self._cache into a to_thread() callable.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        # max_size=1000 balances memory usage with hit rate
        # default_ttl=3600 (1hr) matches typical Lambda warm instance lifetime
        self._cache = ResolutionCache(max_size=max_size, default_ttl=default_ttl)

    def get(self, key: str) -> list[PriceCandle] | None:
        """Get from in-memory cache. Returns None on miss.

        ResolutionCache.get() unwraps the (value, timestamp) tuple internally,
        returning only the value. Callers never see the tuple.
        """
        return self._cache.get(key)

    def set(self, key: str, value: list[PriceCandle]) -> None:
        """Set in in-memory cache. Event-loop-thread only.

        ResolutionCache.set() stores (value, time.time()) tuple internally.
        Eviction of oldest entry (if at max_size) atomically removes both
        value and timestamp — no orphaned metadata (Round 22).
        """
        self._cache.set(key, value)

    def get_age(self, key: str) -> int:
        """Get age in seconds since entry was set(). Returns 0 if not found.

        Uses ResolutionCache.get_with_age() which reads the stored timestamp
        from the (value, inserted_at) tuple. Atomically correct — if the entry
        was evicted and re-inserted, returns age from the latest insertion.
        """
        _, age = self._cache.get_with_age(key)
        return max(0, int(age))

    def has(self, key: str) -> bool:
        """Check if key exists in cache without triggering LRU update."""
        return self._cache.get(key) is not None

    def invalidate(self, ticker: str) -> int:
        """Remove all cache entries for a ticker. Delegates to ResolutionCache.

        Scans keys matching "ohlc:{ticker}:" prefix. O(N) on max_size=1000
        takes <1ms — safe for event loop thread. Returns count of evicted entries.

        Used by invalidate_ohlc_cache() public API (Section 11.11).
        """
        return self._cache.invalidate(f"ohlc:{ticker.upper()}:")

    def clear(self) -> int:
        """Clear all cache entries. Delegates to ResolutionCache.

        Returns count of evicted entries. Used by invalidate_ohlc_cache(None).
        """
        return self._cache.clear()

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
        cached = self._cache.get(key)
        if cached is not None:
            logger.debug("In-memory cache hit", extra={"key": key})
            return cached

        # Read-through to DynamoDB (strong consistency, ~40ms)
        # fetch_from_dynamodb() awaits asyncio.to_thread() internally,
        # but returns result HERE on the event loop thread
        result = await fetch_from_dynamodb()
        if result:
            # SAFE: cache write on event loop thread (after await returns)
            self.set(key, result)  # Stores (value, timestamp) tuple atomically (Round 22)
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
async def _fetch_with_lock(
    ctx: OHLCRequestContext,  # Round 24: replaces (ticker, cache_key, source, resolution, start_date, end_date)
) -> tuple[list[PriceCandle], dict | None]:
    """Fetch from API with distributed lock and read-through cache.

    Returns:
        Uniform tuple (candles, write_context | None) for ALL code paths (Round 22).
        - Cache hit: (candles, None) — no persistence needed
        - Fresh fetch: (candles, {"ctx": ctx, "candles": ...}) — caller awaits write in Phase 2
        - Degraded mode: (candles, None) — DDB unavailable, skip write

    Consistency Strategy (Cost Optimization):
    - Initial read: eventual consistency (1 RCU, ~20ms) - miss is acceptable
    - Lock waiter retries: strong consistency (2 RCU, ~40ms) - must see recent writes
    - Double-check after lock: strong consistency - prevent duplicate fetches

    Degraded Mode (Clarified 2026-02-07 Round 20):
    - When LocalCircuitBreaker is open, skip lock+poll entirely
    - Direct-to-Tiingo (~800ms) vs wasted 3s polling dead DynamoDB
    - Tiingo still protected by its own distributed CircuitBreakerManager
    """

    # Step 0: Check DynamoDB health ONCE at flow start (Round 20)
    ddb_healthy = not _DDB_BREAKER.is_open()

    # Step 1: Check read-through cache (in-memory → eventual DynamoDB)
    if ddb_healthy:
        cached = await _ohlc_read_through_cache.get_or_fetch(
            key=ctx.cache_key,
            fetch_from_dynamodb=lambda: _read_from_dynamodb(
                ctx, consistent_read=False  # Eventual: cost-efficient for initial check
            )
        )
        if cached:
            return cached, None  # Cache hit — no write needed (Round 22)
    else:
        # CB open: check in-memory only (no DynamoDB call)
        cached = _ohlc_read_through_cache.get(ctx.cache_key)
        if cached is not None:
            return cached, None  # L1 hit while degraded — no write needed (Round 22)

    # Step 1.5: DEGRADED MODE — skip lock+poll, direct to Tiingo (Round 20)
    if not ddb_healthy:
        logger.info(
            "DynamoDB degraded (CB open), bypassing lock — direct to Tiingo",
            extra={"ticker": ctx.ticker, "cache_key": ctx.cache_key},
        )
        candles = await _fetch_from_tiingo(ctx.ticker, ...)
        return candles, None  # DDB broken — skip write (Round 22)

    # Step 2: Acquire lock (cache miss confirmed, DynamoDB healthy)
    lock_id = _acquire_fetch_lock(ctx.cache_key)

    if lock_id:
        try:
            # Step 3a: Double-check after lock (another caller might have just written)
            # Strong consistency required - we're about to call Tiingo if miss
            cached = await _read_from_dynamodb(ctx, consistent_read=True)
            if cached:
                _ohlc_read_through_cache.set(ctx.cache_key, cached)
                return cached, None  # Double-check hit — no write needed (Round 22)

            # Step 4: Fetch from Tiingo (Critical Section — lock protects THIS)
            candles = await _fetch_from_tiingo(ctx.ticker, ...)

            # Step 5: Populate L1 in-memory BEFORE releasing lock (Round 20)
            # Same-instance waiters see data immediately via L1
            _ohlc_read_through_cache.set(ctx.cache_key, candles)
        finally:
            # Step 6: Release lock BEFORE write-through (Round 20 "Fast Release")
            # Lock hold = ~800ms (API only), NOT ~10,800ms (API + throttled batch write)
            _release_fetch_lock(ctx.cache_key, lock_id)

        # Step 7: Return write context to caller (Round 21 "Two-Phase" refinement)
        # Lock is already released — other instances unblocked.
        # Write-through is NOT awaited here — it's deferred to the handler's
        # Phase 2 (outside asyncio.wait_for) to prevent timeout cancellation.
        # Preserves Round 20 Q3 guarantee: write completes before Lambda freeze.
        # Round 24: ctx is frozen — safe to pass through write context dict.
        return candles, {"ctx": ctx, "candles": candles}
    else:
        # Step 3b: Lock not acquired - wait and poll read-through cache
        for _ in range(LOCK_MAX_RETRIES):
            await asyncio.sleep(LOCK_WAIT_MS / 1000)

            # Poll with STRONG consistency - must see lock holder's write
            cached = await _ohlc_read_through_cache.get_or_fetch(
                key=ctx.cache_key,
                fetch_from_dynamodb=lambda: _read_from_dynamodb(
                    ctx, consistent_read=True  # Strong: must see recent writes
                )
            )
            if cached:
                return cached, None  # Lock waiter got data — no write needed (Round 22)

        # Fallback: fetch anyway (availability over consistency)
        logger.warning("Lock wait timeout, falling back to API fetch")
        candles = await _fetch_from_tiingo(ctx.ticker, ...)
        # Timeout fallback also needs write — data fetched but not yet in DDB
        return candles, {"ctx": ctx, "candles": candles}
```

**Guarantees:**
1. Same-instance requests: In-memory hit (~1ms)
2. Initial cache check: Eventual consistency (~20ms, 1 RCU) - miss triggers lock acquisition
3. Lock hold duration: ~800ms (Tiingo API only) — write-through deferred to handler Phase 2 outside timeout boundary (Round 21)
4. Lock waiters: Strong consistency (~40ms, 2 RCU) - guaranteed to see lock holder's write
5. Degraded mode (CB open): Skip lock+poll entirely, direct to Tiingo (~800ms) — no 3s wasted polling (Round 20)
6. Double-check after lock: Strong consistency - prevents duplicate Tiingo fetches
7. Cost optimization: Happy path (cache hit) uses eventual consistency (half the cost)

### 4.9 Cache Source Response Header

**Decision (Clarified 2026-02-04, extended 2026-02-07 Round 20):** Add `X-Cache-Source` and `X-Cache-Age` response headers for immediate cache verification and debugging.

**Header Values:**

| Header | Value | Meaning | Latency |
|--------|-------|---------|---------|
| `X-Cache-Source` | `in-memory` | Served from Lambda instance cache | ~1ms |
| `X-Cache-Source` | `dynamodb` | Served from DynamoDB persistent cache | ~40ms |
| `X-Cache-Source` | `tiingo` | Fetched fresh from Tiingo API | ~500-2000ms |
| `X-Cache-Source` | `finnhub` | Fetched fresh from Finnhub API | ~500-2000ms |
| `X-Cache-Source` | `stale` | Timeout fallback — served last-known data from L1/L2 (Round 20) | <5s |
| `X-Cache-Age` | `<seconds>` | Age in seconds since data was cached (Round 20). `0` for fresh fetches. Enables frontend "Last updated Xm ago" display. | — |

**Implementation (Rewritten Round 22 to align with Two-Phase Handler):**

This function is called by the handler's Phase 1 (`asyncio.wait_for`). It delegates to `_fetch_with_lock()` which returns a uniform `(candles, write_context | None)` tuple. Headers are determined by which cache layer served the data.

```python
import time
from fastapi import Response

async def _get_ohlc_data_with_write_context(
    ctx: OHLCRequestContext,  # Round 24: replaces (ticker, resolution, time_range, cache_key)
    response: Response,
) -> tuple[OHLCResponse, dict | None]:
    """Fetch OHLC data with cache source tracking + deferred write context.

    Returns:
        (OHLCResponse with headers set, write_context | None for Phase 2)

    Header determination uses the cache layer that served the data:
    - L1 hit (in-memory): X-Cache-Source: in-memory, age from get_age()
    - L2 hit (DynamoDB): X-Cache-Source: dynamodb, age from ExpiresAt derivation
    - L3 fresh (Tiingo): X-Cache-Source: tiingo, age = 0
    - Degraded (CB open): X-Cache-Source: tiingo, age = 0 (bypassed DDB)
    """
    cache_source = "tiingo"  # Default: will fetch from API
    cache_age = 0

    # Step 1: Check L1 in-memory (same-instance, ~1ms)
    cached = _ohlc_read_through_cache.get(ctx.cache_key)
    if cached is not None:
        cache_source = "in-memory"
        cache_age = _ohlc_read_through_cache.get_age(ctx.cache_key)  # Round 22: atomic tuple
        response.headers["X-Cache-Source"] = cache_source
        response.headers["X-Cache-Age"] = str(cache_age)
        response.headers["X-Cache-Key"] = ctx.cache_key
        return OHLCResponse(candles=cached, ...), None  # No write needed

    # Step 2: Delegate to _fetch_with_lock (L2 → Lock → L3 flow)
    # Returns uniform (candles, write_context | None) tuple (Round 22)
    candles, write_context = await _fetch_with_lock(ctx)  # Round 24: single ctx param

    # Step 3: Determine cache source from write_context
    if write_context is not None:
        # Fresh fetch from Tiingo — data not yet in DDB
        cache_source = ctx.source  # Round 24: use actual source from ctx
        cache_age = 0
    elif candles is not None:
        # Cache hit (L2 DynamoDB or lock-waiter poll)
        cache_source = "dynamodb"
        cache_age = _estimate_cache_age_from_dynamodb(candles, ctx.resolution)  # Round 21
    else:
        cache_source = ctx.source
        cache_age = 0

    # Step 4: Set response headers
    response.headers["X-Cache-Source"] = cache_source
    response.headers["X-Cache-Age"] = str(cache_age)
    response.headers["X-Cache-Key"] = ctx.cache_key

    return OHLCResponse(candles=candles, ...), write_context
```

**Benefits:**
- Immediate verification (no CloudWatch latency)
- Works for any HTTP client (curl, browser, Playwright)
- Useful for debugging slow requests
- Smoke tests can assert on header value
- API contract, not log format dependency
- `X-Cache-Age` derives from `ResolutionCache` tuple (L1) or `ExpiresAt` derivation (L2) — no stale references (Round 22)
- `stale` source (set by handler on timeout) enables automated synthetic monitors to alert on degradation
- Uniform tuple return aligns with handler Phase 1/Phase 2 architecture (Round 21+22)

### 4.10 Handler Two-Phase Architecture ("Emergency Brake")

**Decision (2026-02-07 Round 20, refined 2026-02-08 Round 21):** Split the handler into two distinct phases: (1) Response Phase capped at 5s via `asyncio.wait_for()`, (2) Persistence Phase uncapped but awaited before handler returns. Guarantees both deterministic P99 user latency AND write-through completion (no Lambda freeze mid-write).

**Problem (Round 20):** Without a handler-level timeout, worst-case flow is ~47 seconds:
```
L1 miss (1ms) → L2 retry (3.5s) → Lock (50ms) → Double-check L2 (3.5s) → Tiingo (30s!) → Write (10s) = ~47s
```
API Gateway hard limit is 29s → user sees 504 while Lambda keeps burning compute.

**Refinement (Round 21 Q1):** Round 20's original design placed write-through INSIDE the 5s `asyncio.wait_for()`. This creates a contradiction: `batch_write_with_retry` has a 10s hard cap, but if the handler reaches write-through at t=4.5s, the 5s timeout cancels the write at t=5.0s — the exact "Lambda freeze mid-write" scenario Round 20 Q3 was designed to prevent. Solution: **separate the clock for the user from the clock for the database**.

**Constants:**

```python
# Phase 1: Response — user gets candles within this window, always.
DASHBOARD_TIMEOUT_SECONDS = 5.0

# Tiingo httpx timeout — must be < DASHBOARD_TIMEOUT to leave buffer for recovery.
# Buffer (1s) covers: double-check L2 read (~200ms), JSON serialization (~150ms),
# X-Ray/EMF flush (~50ms), stale fallback logic (~100ms).
TIINGO_HTTP_TIMEOUT_SECONDS = 4.0  # Was: 30.0 in tiingo.py:85

# Phase 2: Persistence — no user-facing timeout, but batch_write_with_retry
# has its own 10s MAX_BATCH_RETRY_DURATION_SECONDS hard cap (Round 19 Q4).
```

**Implementation:**

**Response Models (Round 26 Q1 — Discriminated Union):**

```python
from pydantic import BaseModel, Field
from typing import Literal, Union

class OHLCErrorResponse(BaseModel):
    """Dedicated error/degraded response for timeout and failure paths.

    Separates success and failure contracts (Round 26): OHLCResponse requires
    all 7 mandatory fields (ticker, time_range, start_date, etc.) which are
    not available during emergency timeout. OHLCErrorResponse is "cheap" to
    construct — no cache_expires_at, no count, no source required.

    Frontend uses TypeScript type guard: if ('status' in response) → error path.
    CloudWatch Logs Insights: stats count(*) by status for degradation tracking.
    """
    status: Literal["degraded", "error"]
    message: str
    candles: list[PriceCandle] = Field(default_factory=list)
    ticker: str | None = None  # Optional in error state

# Handler return type — discriminated union
OHLCHandlerResponse = Union[OHLCResponse, OHLCErrorResponse]
```

**Implementation:**

```python
import asyncio
from fastapi import Response

async def get_ohlc_handler(
    ticker: str,
    resolution: str,
    time_range: str,
    response: Response,
) -> OHLCHandlerResponse:  # Round 26: was OHLCResponse — crashed on timeout paths
    """Top-level OHLC handler with two-phase architecture.

    Phase 1 (Response): L1 → L2 → Lock → Tiingo under 5s hard ceiling.
        Returns candles + cache_source to user. On timeout: stale fallback.
    Phase 2 (Persistence): Write-through to DynamoDB AFTER response is built.
        Awaited before handler returns to prevent Lambda freeze mid-write.
        Invisible to user latency; additive to billed duration only (~50ms normal).

    Invariant: User P99 = 5s. Write integrity = guaranteed.
    """
    # ── CONTEXT CONSTRUCTION (Round 24) ───────────────────────────────
    start_date, end_date = _resolve_date_range(time_range)
    cache_key = _get_ohlc_cache_key(ticker, resolution, time_range, start_date, end_date)
    ctx = OHLCRequestContext(
        ticker=ticker, resolution=resolution, time_range=time_range,
        start_date=start_date, end_date=end_date,
        source=_get_default_source(ticker), cache_key=cache_key,
    )
    pending_write = None  # Deferred write-through context (Round 21)

    # ── PHASE 1: RESPONSE (capped at 5s) ──────────────────────────────
    try:
        # Returns (OHLCResponse, pending_write_context | None)
        # pending_write_context is {"ctx": ctx, "candles": candles} for Phase 2
        result, pending_write = await asyncio.wait_for(
            _get_ohlc_data_with_write_context(ctx, response),
            timeout=DASHBOARD_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Handler timeout — serving stale fallback",
            extra={"ticker": ctx.ticker, "cache_key": ctx.cache_key},
        )

        # Stale fallback: L1 first (0ms), then "last gasp" L2 (100ms, no retries)
        stale_candles = _ohlc_read_through_cache.get(ctx.cache_key)
        stale_age = 0

        if stale_candles is None and not _DDB_BREAKER.is_open():
            # Cold start: L1 empty, but L2 might have data from prior invocation.
            # Quick read: 100ms limit, no retries, eventual consistency (cheapest).
            try:
                stale_candles = await asyncio.wait_for(
                    _read_from_dynamodb(
                        ctx, consistent_read=False,  # Round 24: ctx carries all params
                    ),
                    timeout=0.1,  # 100ms — "last gasp"
                )
                if stale_candles:
                    stale_age = _estimate_cache_age_from_dynamodb(stale_candles, ctx.resolution)  # Round 24 Q3: was missing resolution param
            except (asyncio.TimeoutError, Exception):
                pass  # L2 also unavailable — proceed to error response

        if stale_candles:
            response.headers["X-Cache-Source"] = "stale"
            response.headers["X-Cache-Age"] = str(stale_age)
            response.headers["X-Cache-Key"] = ctx.cache_key
            # Round 26 Q1: OHLCErrorResponse (not OHLCResponse) — avoids pydantic
            # ValidationError from missing 7 required fields during emergency timeout
            result = OHLCErrorResponse(
                status="degraded",
                message="Serving cached data due to upstream latency",
                candles=stale_candles,
                ticker=ctx.ticker,
            )
        else:
            # Total failure: no stale data available (cold start + L2 unavailable)
            response.status_code = 503
            response.headers["X-Cache-Source"] = "none"
            response.headers["Retry-After"] = "5"
            # Round 26 Q1: OHLCErrorResponse — cheap to construct, no cache_expires_at needed
            result = OHLCErrorResponse(
                status="error",
                message="Service temporarily unavailable — please retry",
                ticker=ctx.ticker,
            )

    # ── PHASE 2: PERSISTENCE (outside 5s cap, awaited before handler returns) ──
    if pending_write:
        # Round 24 Q2: Breaker check moved INSIDE _write_through_to_dynamodb.
        # Function is self-contained: is_open() → early return, record_success/failure
        # on outcome. Handler only needs to check if write context exists.
        # Write-through runs AFTER user response is built but BEFORE Lambda freezes.
        # Billed duration: ~50ms normal, up to 10s under throttling (hard cap).
        # X-Ray: separate "DynamoDB_Write" segment after "Response" segment.
        await _write_through_to_dynamodb(**pending_write)

    return result
```

**Key Design: `_get_ohlc_data_with_write_context()`**

The inner fetch function returns a tuple: `(response, pending_write_context)`. When fresh data is fetched from Tiingo, instead of awaiting write-through inline, it bundles the write arguments into a dict and returns them to the handler. The handler then awaits the write outside the timeout boundary.

```python
async def _get_ohlc_data_with_write_context(
    ctx: OHLCRequestContext,  # Round 24: frozen dataclass carries all request params
    response: Response,
) -> tuple[OHLCResponse, dict | None]:
    """Fetch OHLC data, returning response + deferred write context.

    The write context (if any) is a dict with keys {ctx, candles} for Phase 2.
    Caller is responsible for awaiting the write OUTSIDE the timeout boundary.
    """
    # ... L1 → L2 → Lock → Tiingo flow (same as _fetch_with_lock) ...
    # On cache hit: return (response, None)  — no write needed
    # On fresh fetch: return (response, {"ctx": ctx, "candles": candles})
```

**Cache Age Derivation (Round 21):**

```python
import time

def _estimate_cache_age_from_dynamodb(candles: list, resolution: str) -> int:
    """Derive cache age from DynamoDB ExpiresAt — no extra attribute needed.

    Formula: WrittenAt = ExpiresAt - TTL_DURATION
             Age = now - WrittenAt

    Uses the first candle's ExpiresAt (all candles in a batch share the same TTL).
    Returns 0 if ExpiresAt is missing (defensive — should not happen).
    Clamps to max(0, age) to handle minor clock skew.
    """
    if not candles:
        return 0

    # ExpiresAt is on the raw DynamoDB item; candles here are PriceCandle objects
    # converted from DynamoDB items. The caller must pass the raw ExpiresAt
    # from the first item in the query response.
    expires_at = getattr(candles[0], '_expires_at', 0)  # Set during conversion
    if not expires_at:
        return 0

    # Reverse the TTL calculation from Section 4.6
    is_intraday = resolution != "D"
    if is_intraday:
        ttl_duration = TTL_MINUTES_TODAY_INTRADAY * 60  # 5 min = 300s
    else:
        ttl_duration = TTL_DAYS_HISTORICAL * 24 * 60 * 60  # 90 days

    written_at = expires_at - ttl_duration
    return max(0, int(time.time() - written_at))
```

**Note:** During `PriceCandle.from_cached_candle()` conversion, store the raw `ExpiresAt` value as a transient `_expires_at` attribute on the first candle. This avoids passing DynamoDB metadata through the entire call chain while keeping the derivation clean.

**Tiingo Adapter Change:**

```python
# src/lambdas/shared/adapters/tiingo.py:85
# BEFORE:
TIMEOUT = 30.0

# AFTER (Round 20):
TIMEOUT = 4.0  # Must be < DASHBOARD_TIMEOUT_SECONDS (5s) to leave buffer for stale fallback
```

**Worst-Case Timeline (Two-Phase):**

```
─── PHASE 1: RESPONSE (user-facing, 5s cap) ───
0ms     L1 miss
100ms   L2 read (throttled, 1st attempt fails, 2nd starts)
500ms   L2 miss confirmed
550ms   Lock acquired + double-check L2
800ms   Tiingo returns candles → populate L1 → release lock
850ms   Response built: 200 OK, X-Cache-Source: tiingo
        ← User latency ends here (~850ms) →

─── PHASE 2: PERSISTENCE (invisible to user) ───
850ms   Write-through begins (outside asyncio.wait_for)
900ms   batch_write_item completes (~50ms normal)
900ms   Handler returns → Lambda environment safe to freeze
        ← Billed duration: ~900ms total →

─── WORST CASE: TIMEOUT + THROTTLED WRITE ───
0ms     L1 miss
4500ms  Tiingo 4s timeout fires → L1 populated with partial/stale
5000ms  Handler timeout fires → stale fallback response sent
        ← User latency: 5000ms (hard cap) →
5001ms  Phase 2: pending_write from pre-timeout Tiingo fetch
15000ms Write completes after DynamoDB throttling retries (10s hard cap)
15000ms Handler returns
        ← Billed duration: ~15s, but user saw response at 5s →
```

**Guarantees:**
1. User P99 latency capped at 5s regardless of downstream health
2. Write-through always completes before Lambda freeze — no orphaned writes, no corrupted connection pools (Round 20 Q3 preserved)
3. Stale data preferred over 504 — "stale is better than broken"
4. `X-Cache-Source: stale` + `X-Cache-Age` enable frontend "Last updated Xm ago" display
5. CloudWatch Synthetics can alert on stale percentage >5%
6. Billed duration may exceed 5s under throttling, but user latency never does
7. X-Ray trace shows clean separation: Response segment (~850ms) + DynamoDB_Write segment (~50ms)

---

## 5. Data Flow (After Implementation)

```
Request: GET /api/v2/tickers/AAPL/ohlc?range=1M&resolution=D

══════════════════════════════════════════════════════════════════════
  PHASE 1: RESPONSE (capped at 5s — user-facing latency)
══════════════════════════════════════════════════════════════════════
┌─ asyncio.wait_for(timeout=5.0) ─────────────────────────────────────┐
│                                                                      │
│  0. Check DynamoDB Health (LocalCircuitBreaker) — Round 20 Q1        │
│     ├─ CB OPEN → Skip to step 4 (Degraded Mode, direct to Tiingo)   │
│     └─ CB CLOSED ↓                                                   │
│                                                                      │
│  1. Check Read-Through Cache (in-memory → eventual DynamoDB)         │
│     ├─ IN-MEMORY HIT → Return (response, None)  (~1ms)              │
│     ├─ DYNAMODB HIT → Populate L1, return (response, None)  (~40ms) │
│     └─ BOTH MISS ↓                                                   │
│                                                                      │
│  2. Acquire Distributed Lock (DynamoDB conditional write)            │
│     ├─ ACQUIRED → Proceed to step 3                                  │
│     └─ LOCKED → Wait 200ms, retry step 1 (up to 15×200ms / 3s)     │
│                                                                      │
│  3. Double-Check DynamoDB (strong consistency)                       │
│     ├─ HIT → Populate L1, release lock, return (response, None)     │
│     └─ MISS ↓                                                        │
│                                                                      │
│  4. Call Tiingo API (4s httpx timeout) — Round 20                    │
│     ├─ SUCCESS → Populate L1, release lock,                          │
│     │            return (response, pending_write_context) ← NEW R21  │
│     └─ FAILURE → Release lock, fall through ↓                       │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
     │ TIMEOUT or FAILURE ↓
     │
5. Stale Fallback (Round 20)
   ├─ L1 HAS DATA → Return 200 + X-Cache-Source: stale + X-Cache-Age
   ├─ L1 EMPTY + CB CLOSED → "Last gasp" L2 read (100ms, no retries)
   │   ├─ L2 HIT → Return 200 + X-Cache-Source: stale
   │   └─ L2 MISS ↓
   └─ TOTAL FAILURE → Return 503 + Retry-After: 5

══════════════════════════════════════════════════════════════════════
  PHASE 2: PERSISTENCE (outside 5s cap — invisible to user)  ← R21
══════════════════════════════════════════════════════════════════════
6. If pending_write_context exists AND CB closed:
   ├─ await _write_through_to_dynamodb(**pending_write_context)
   │   ├─ SUCCESS → L2 populated, cross-instance cache warm (~50ms)
   │   └─ FAILURE → Log warning, non-fatal (L1 still has data)
   └─ Handler returns → Lambda environment safe to freeze
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

### 6.9 Concurrent Resolution Fallback (Duplicate Tiingo Calls)
**Decision (Clarified 2026-02-08 Round 21):** Accept as known trade-off — document, do not fix.
**Scenario:** Requests for different resolutions (5-min, 60-min) on the same ticker both fall back to daily ("D"). Each acquires a separate lock (different cache key), both call Tiingo for the same daily data, both write under `ohlc:AAPL:D:1M:...` (last-write-wins, idempotent).
**Why accept:**
- Natural cap: at most ~3 concurrent fallback paths (number of standard resolutions), not a true thundering herd
- Writes are idempotent: identical daily candle data, DynamoDB overwrites with same values
- Self-correcting: once the first write completes, all subsequent requests (any resolution) hit cache
- Secondary lock (Option B) risks deadlocks with nested DynamoDB locks under Lambda timeout pressure
- Pre-check alias read (Option C) adds strongly consistent read cost to every fallback, penalizing 100% to save <1%
- Parallel calls actually increase availability: if one Lambda freezes, the other still populates the cache

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
| CB convergence spike (brownout) | Medium | Low | 50 instances × 3 threshold = 150 failed calls before all breakers open; DynamoDB on-demand absorbs; `CircuitBreakerOpenCount` Sum alarm detects correlated events (Round 20 Q5) |

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

### Session 2026-02-08 (Round 25 - Post-Round-24 Full Drift Audit)

- Q: `_get_default_source(ticker)` and `_resolve_date_range(time_range)` are called at handler entry (Sections 4.0/4.10) to construct `OHLCRequestContext`, but neither function is defined anywhere — double NameError, 100% crash rate before cache pipeline starts. → A: **Define both as pure stateless helpers in new Section 4.0.1.** `_resolve_date_range` maps predefined time_range strings ("1D", "1W", "1M", "3M", "6M", "1Y", "YTD") to `(start_date, end_date)` using ET market timezone (per Round 18). Raises `ValueError` for unknown/custom ranges. `_get_default_source` returns `"tiingo"` — centralized "knob" for future Finnhub failover. Both are pure, no I/O, trivially testable. Also fixed Section 4.3 bare `resolution`/`start_date`/`end_date` variables → `ctx.resolution`/`ctx.start_date`/`ctx.end_date`.

- Q: Section 4.3 defines `_read_from_dynamodb` as sync `def` but every caller uses `await`. Section 11.7 defines the async wrapper with the same name. Implementers reading Section 4.3 in isolation would write a sync function, then hit `TypeError` at every call site — same bug class as Round 23 Q4. → A: **Rename Section 4.3 function to `_read_from_dynamodb_sync`** with cross-reference to Section 11.7 async wrapper. Establishes naming symmetry with write path (`_write_through_to_dynamodb` async + `put_cached_candles` sync inner). Section 4.3 = data logic (completeness gate, resolution validation). Section 11.7 = resilience logic (breaker, `to_thread`, error recording). Implementer reads both; neither is complete alone.

- Q: Section 12.4 observability snippets use pre-Round-24 signature `_read_from_dynamodb(ticker: str, source: str, resolution: str, ...)` with bare `cache_key` variable (never a parameter) and `@tracer.capture_method` on the sync function (orphaned X-Ray segments in worker thread). Handler snippet also uses bare `ticker`, `cache_key`, `resolution`. → A: **Update all Section 12.4 snippets to `ctx: OHLCRequestContext` pattern with post-await X-Ray instrumentation.** Handler snippet uses `ctx.ticker`, `ctx.cache_key`, `ctx.resolution`, `ctx.source`. Cache-specific logging moves to async wrapper with `tracer.provider.in_subsegment()` on event loop thread, `asyncio.to_thread()` for sync I/O, and post-await annotation enrichment (`status: hit/miss/error`). Matches Round 19 Q4 "Clean Room" pattern: sync function = pure I/O, async wrapper = orchestration + tracing. Ensures CloudWatch Logs Insights queries reference `ctx.*` fields that actually exist.

- Q: Section 15 Quick Reference says "176 tests" and "D: 28 tests" — stale after Round 24 added D36-D39 (total 180, D: 36). Test plan file header correctly says 180. Quick Reference is the most frequently consulted section — stale counts create "Shadow Debt" where developers think they've finished before CI catches the gap. → A: **Update Section 15 counts to match canonical test plan.** D: 28 → 36. Total: 176 → 180. Added R24 and R25 mentions to parenthetical history. R25 helper function tests (`_resolve_date_range`, `_get_default_source`) to be formally numbered during `/speckit.plan`.

- Q: Test C14 calls `_resolve_date_range("1D")` and `_get_ohlc_cache_key(...)` without importing either — NameError. Test M1 calls `_read_from_dynamodb("AAPL", "tiingo", "D", ...)` with pre-Round-24 positional string arguments — TypeError. Both are in the canonical test plan that implementers build to. → A: **Fix both tests to use Round 24+25 ctx pattern.** C14: add explicit imports `from src.lambdas.dashboard.ohlc import OHLCRequestContext, _resolve_date_range, _get_ohlc_cache_key`. M1/M2: construct `OHLCRequestContext` fixture, call `await _read_from_dynamodb(ctx, consistent_read=False)` and `await _write_through_to_dynamodb(ctx, [...])`. Test bodies verify same metric assertions — only the call interface changed.

### Session 2026-02-08 (Round 24 - OHLCRequestContext & Circuit Breaker Audit)

- Q: Handler uses `start_date`, `end_date`, `source` as bare variables but they aren't in `_get_ohlc_data_with_write_context` or `_fetch_with_lock` signatures — NameError at runtime. The call chain passes 5-7 individual params through each level (Data Clump anti-pattern). Adding future params (e.g., `user_tier`) would require refactoring every function. → A: **Introduce frozen `OHLCRequestContext` dataclass** — constructed once at handler entry, passed as single `ctx` param through the entire L1 → L2 → Lock → Tiingo → Phase 2 chain. Frozen for thread safety (`asyncio.to_thread()` closures). Includes `to_metadata()` for X-Ray/EMF. Test fixtures use `dataclasses.replace()` for per-test overrides. Refactored: `_get_ohlc_data_with_write_context(ctx, response)`, `_fetch_with_lock(ctx)`, `_read_from_dynamodb(ctx, consistent_read)`, `_write_through_to_dynamodb(ctx, candles)`. Write context dict simplified from 5 keys to 2: `{"ctx": ctx, "candles": candles}`.

- Q: Sections 11.3 and 11.7 contain async wrapper snippets still using pre-Round-24 individual parameters (`ticker, source, resolution, start_date, end_date`) instead of `OHLCRequestContext`. Section 11.7 write wrapper also missing `_DDB_BREAKER` calls from Q2. Implementers copying these snippets would get NameErrors and re-introduce the breaker blind spot. → A: **Update all three snippets to `ctx: OHLCRequestContext` pattern** — Section 11.7 read wrapper: `_read_from_dynamodb(ctx, consistent_read)` with breaker integration. Section 11.7 write wrapper: `_write_through_to_dynamodb(ctx, candles)` with `is_open()` guard, `record_success()`, `record_failure()`. Section 11.3 breaker integration: `_read_from_dynamodb_sync, ctx, consistent_read`. All supplementary sections now speak the same language as canonical Sections 4.2-4.10. Zero architectural drift.

- Q: Test plan has zero Round 24 coverage — no R24 column in summary table. `OHLCRequestContext` construction, circuit breaker write visibility (`record_success()`/`record_failure()` in `_write_through_to_dynamodb`), and timeout fallback age fix (`ctx.resolution` param) have no tests. C14 uses stale `OHLCRequestContext.create()` factory method that doesn't exist in spec. → A: **Update test plan with D36-D39** — D36: write success calls `record_success()`, D37: write failures trip breaker open, D38: timeout fallback age uses `ctx.resolution` (daily vs intraday derive different ages), D39: `OHLCRequestContext` frozen + `to_metadata()` + `dataclasses.replace()`. Fixed C14 stale factory method to use direct constructor. Summary table extended with R24 column. Total 176 → 180.

- Q: Handler timeout fallback (line 1031) calls `_estimate_cache_age_from_dynamodb(stale_candles)` — missing `resolution` parameter. Function signature is `(candles: list, resolution: str) -> int`. `TypeError` every time a user hits the 5s timeout and L2 has stale data. Happy path in Section 4.9 already passes `ctx.resolution` correctly. Error path was never updated — classic "happy path updated but error path missed" bug. Turns graceful degradation into a total dashboard crash. → A: **Pass `ctx.resolution`** — ctx is in scope, resolution needed for TTL duration lookup (intraday=5min vs daily=90d). Fixed to `_estimate_cache_age_from_dynamodb(stale_candles, ctx.resolution)`. Matches Section 4.9 happy-path pattern. X-Cache-Age now accurate in stale fallback. Avoids data bloat (Option B would inject resolution into every PriceCandle or DynamoDB metadata).

- Q: `_write_through_to_dynamodb` catches exceptions and logs but never calls `_DDB_BREAKER.record_failure()` or `record_success()`. The circuit breaker is "deaf" to write-side health — only read failures feed it. A DynamoDB outage affecting writes only (WCU throttling) would never trip the breaker. Phase 2 keeps attempting writes on every request, burning ~200ms per attempt on a dead write path. During HALF_OPEN, write outcomes don't contribute to recovery detection. → A: **Writes contribute to the same `_DDB_BREAKER`** — DynamoDB is a single service; write failures are a leading indicator of read failures. Add `_DDB_BREAKER.is_open()` early return inside `_write_through_to_dynamodb` (encapsulates breaker check, handler guard simplified to `if pending_write:`). Add `record_success()` after successful `asyncio.to_thread(put_cached_candles, ...)`. Add `record_failure()` in except block. During HALF_OPEN, successful write helps close circuit faster. X-Ray Service Map now reflects holistic DDB health. `CircuitBreakerOpenCount` EMF metric becomes single indicator of database health.

### Session 2026-02-08 (Round 23 - Post-Round-22 Deep Audit)

- Q: `_write_through_to_dynamodb(**pending_write)` crashes with `TypeError` — write context dict uses key `"candles"` (lines 703, 725) but function parameter is `ohlc_candles` (line 105). Every Tiingo fetch succeeds but Phase 2 write silently fails (caught by `except Exception`), so L2 DynamoDB cache is never populated. Cross-Lambda requests always hit Tiingo, defeating the cache. → A: **Rename function parameter from `ohlc_candles` to `candles`** — aligns with ubiquitous domain language used throughout the stack (Pydantic models, `OHLCReadThroughCache`, adapters, write context dict). Makes `**pending_write` kwargs unpacking self-documenting. Type hint tightened to `list[PriceCandle]`. Body reference updated (`candles_to_cached(candles, ...)`). Zero external impact — purely internal function.

- Q: `OHLCReadThroughCache` class spec defines `get`, `set`, `get_age`, `has`, `get_or_fetch` — but Section 11.11's `invalidate_ohlc_cache()` public API calls `.invalidate(ticker)` and `.clear()`, which don't exist. `AttributeError` crashes the entire cache invalidation subsystem — Round 22 Q4 fixed the import boundary but didn't add the methods it delegates to. → A: **Delegate to `ResolutionCache` directly** — add `invalidate(prefix) -> int` and `clear() -> int` to `ResolutionCache` (data layer owns data operations). `OHLCReadThroughCache` wraps them as thin domain-specific delegates: `.invalidate(ticker)` maps to `self._cache.invalidate(f"ohlc:{ticker.upper()}:")`, `.clear()` maps to `self._cache.clear()`. O(1000) key scan <1ms — safe for event loop. Reusable if `ResolutionCache` serves other domain caches (News, Sentiment).

- Q: Test plan file says 162 tests but main spec says 172. D28-D31 (Round 21), D21-D27 + E31 (Round 20) never propagated to the canonical test plan. Round 22/23 introduced `get_with_age()`, `invalidate()`, `.clear()`, `invalidate_ohlc_cache()` with zero test coverage. Test plan is the implementation contract — implementers build to it. → A: **Update test plan file as canonical source of truth**. Added: D21-D27 (degraded mode + handler timeout, 7 tests), E31 (Tiingo timeout budget, 1 test), D28-D31 (two-phase handler + half-open CB, 4 tests), D32-D35 (invalidation API + cache age, 4 tests). Total updated from 162 → 178. Summary table extended with R20/R21/R23 columns. Section 11.1 test example updated to use `invalidate_ohlc_cache()` public API.

- Q: `_write_through_to_dynamodb` is `def` (sync) but Phase 2 does `await _write_through_to_dynamodb(**pending_write)` — `TypeError: object NoneType can't be used in 'await' expression`. Every fresh Tiingo fetch crashes at Phase 2. Additionally, the sync function blocks the event loop during DynamoDB I/O (50ms-10s), freezing concurrent requests on the same Lambda instance. → A: **Make `async def` with `asyncio.to_thread()` wrapping `put_cached_candles()`** — function becomes awaitable, event loop stays free during Phase 2 DDB write. Aligns with Round 1 Q4 ("wrap sync DynamoDB calls in `asyncio.to_thread()`"). Caller `await` at line 965 now works correctly. Future migration to `aioboto3` requires only swapping the internal implementation, no caller changes.

- Q: `ResolutionCache.get_with_age()` behavior on missing keys is unspecified. `OHLCReadThroughCache.get_age()` does `_, age = self._cache.get_with_age(key)` then `return max(0, int(age))`. If `get_with_age("missing")` returns `None`, tuple unpacking crashes with `TypeError: cannot unpack non-iterable NoneType`. Docstring says "Returns 0 if not found" but the implementation depends on `get_with_age()` returning a specific structure for misses. → A: **Return `(None, 0.0)` sentinel tuple for missing keys** — zero-surprise contract. Callers always get a 2-tuple, always destructure safely without guards or `try/except`. `get_age()` path: `_, age = (None, 0.0)` → `max(0, int(0.0))` → `0`. Type signature: `get_with_age(key: str) -> tuple[Any | None, float]`. Self-documenting: a miss has age zero.

### Session 2026-02-08 (Round 22 - Post-Round-21 Consistency Audit)

- Q: `_fetch_with_lock` has inconsistent return types after Round 21 — Step 7 returns `(candles, write_dict)` tuple, but all cache-hit paths (Steps 1, 1.5, 3a, 3b) and fallback paths return bare `candles`. Handler destructures `result, pending_write = await ...` which crashes on bare returns (`ValueError: too many values to unpack`). → A: **Uniform tuple contract**: ALL return paths return `(candles, write_context | None)`. Cache hits return `(candles, None)`. Fresh Tiingo fetches return `(candles, {"ticker": ..., ...})`. Degraded mode returns `(candles, None)` since DDB is broken. Wait-timeout fallback also returns `(candles, write_dict)` since data was fetched but not persisted. Type signature: `-> tuple[list[PriceCandle], dict | None]`. Zero-overhead branching in handler: `if pending_write: await _write_through(...)`.

- Q: `OHLCReadThroughCache._timestamps` dict (Round 21) grows unbounded — `ResolutionCache` evicts LRU entries but `_timestamps` keys are never removed, causing memory leak and "zombie age" bug where evicted-then-reinserted keys return stale ages. → A: **Store `(value, inserted_at)` tuples inside `ResolutionCache` directly** — atomic eviction removes both value and timestamp in the same `popitem()` call. No separate `_timestamps` dict needed. `ResolutionCache` modification: `set()` stores `(value, time.time())`, `get()` unwraps and returns value only, new `get_with_age()` returns `(value, age_seconds)`. ~3-5 line delta to existing `OrderedDict` implementation. Zero maintenance (no pruner), zero memory leak, 100% accurate ages.

- Q: Section 4.9 `get_ohlc_data()` references non-existent `dynamodb_result.age_seconds` attribute and uses pre-Round-21 single-return pattern that conflicts with two-phase handler's `(response, write_context)` tuple contract. Handler calls `result, pending_write = await ...` but old `get_ohlc_data()` returns bare `OHLCResponse`. → A: **Rewrite Section 4.9 as `_get_ohlc_data_with_write_context()`** — returns `tuple[OHLCResponse, dict | None]`. L1 cache age from `_ohlc_read_through_cache.get_age()` (Round 22 atomic tuples). L2 cache age from `_estimate_cache_age_from_dynamodb()` (Round 21). Write context passthrough from `_fetch_with_lock()` uniform tuple. Headers set inside function. Handler Phase 1 calls this directly.

- Q: Section 11.11 `invalidate_all_caches()` imports `from src.lambdas.dashboard.ohlc import _ohlc_cache` — but `_ohlc_cache` was removed in Round 18 and replaced by `OHLCReadThroughCache` (`_ohlc_read_through_cache`). This `ImportError` makes the entire cache invalidation subsystem dead on arrival. Additionally, `_invalidate_ohlc_response_cache(ticker)` is a phantom function never defined anywhere. → A: **Export a named `invalidate_ohlc_cache(ticker)` function from `ohlc.py`** — a public API that delegates to `_ohlc_read_through_cache.invalidate(ticker)` / `.clear()`. `cache_manager.py` imports the function, not the private instance. Preserves encapsulation: `ohlc.py` can change internal storage (singleton → pool) without breaking consumers. Eliminates phantom helper. Enables X-Ray subsegment tracing on invalidation and clean `pytest` mocking of a top-level function.

- Q: Section 4.2 `_write_through_to_dynamodb()` docstring says "Fire-and-forget" and constraints repeat "Fire-and-forget: errors logged but don't fail request" — but Round 20 Q2+Q3 changed write-through to **awaited** (prevent Lambda freeze mid-write) and Round 21 Q1 refined it into Phase 2 of the Two-Phase Handler. The term "fire-and-forget" implies no `await`, no completion guarantee, and safe to skip — contradicting the actual `await _write_through_to_dynamodb(**pending_write)` in Phase 2. → A: **Replace "fire-and-forget" with "Phase 2 awaited"** — docstring becomes: "Awaited before handler returns to prevent Lambda freeze mid-write. Invisible to user latency; additive to billed duration only (~50ms normal). Errors are logged but do not fail the request (non-fatal)." Constraints become: "Phase 2 awaited: errors logged, non-fatal, but write completion guaranteed under normal conditions." Call sites updated to reflect single Phase 2 call site (no longer inline at each fetch).

### Session 2026-02-08 (Round 21 - Two-Phase Handler Architecture)

- Q: Write-through `await` (Round 20 Q2+Q3) runs INSIDE `asyncio.wait_for(timeout=5.0)` — but `batch_write_with_retry` has a 10s hard cap. If handler reaches write-through at t=4.5s, the 5s timeout cancels the write at t=5.0s, creating the exact "Lambda freeze mid-write" scenario Round 20 Q3 was designed to prevent. How do we satisfy both the 5s user SLA and write-through completion guarantee? → A: **Two-Phase Handler Architecture — separate the clock for the user from the clock for the database**. Phase 1 (Response): `asyncio.wait_for(timeout=5.0)` wraps only the L1→L2→Lock→Tiingo flow. Returns `(response, pending_write_context)` — candles to user + deferred write args. Phase 2 (Persistence): Outside the timeout boundary, `await _write_through_to_dynamodb(**pending_write_context)` runs before handler returns. User latency capped at 5s (Phase 1). Write integrity guaranteed (Phase 2 awaited, no Lambda freeze). Billed duration may exceed 5s under throttling but user never waits. X-Ray shows clean two-segment trace: Response (~850ms) + DynamoDB_Write (~50ms). Refines Round 20 Q2+Q3 — `_fetch_with_lock` returns write context instead of awaiting inline. Add test: D28 `test_write_through_outside_handler_timeout`, D29 `test_phase2_skipped_when_cb_open`.

- Q: `LocalCircuitBreaker` half-open recovery behavior unspecified — how many probe requests, what success threshold to close, what if probe succeeds but next request fails? → A: **Single-probe model**: After 30s timeout, state transitions OPEN→HALF_OPEN, exactly 1 request probes. Success → CLOSED (reset failure count, lock re-enabled). Failure → OPEN (another 30s). During HALF_OPEN, all requests except the in-flight probe are blocked. Matches existing `CircuitBreakerManager` pattern for SRE consistency. Multi-probe (2 extra ~200ms penalties) and gradual ramp (designed for long-lived clusters) are over-engineering for Lambda's ephemeral lifecycle. Single-probe provides instant recovery detection with zero flapping risk. `record_success()` in CLOSED state also resets failure count to prevent slow accumulation across unrelated transient errors. Add `reset()` method for test isolation. Add test: D30 `test_half_open_single_probe_success_closes_circuit`, D31 `test_half_open_probe_failure_reopens_for_30s`.

- Q: Concurrent resolution fallback creates duplicate Tiingo calls — requests for 5-min and 60-min both fall back to daily, acquire separate locks (different cache keys), both call Tiingo for same daily data. Lock only prevents thundering herd for same cache key, not across resolutions. → A: **Accept as known trade-off — do not fix**. Natural cap of ~3 standard resolutions limits concurrent fallbacks (not a true herd). Writes are idempotent (identical daily candle data). Self-correcting: first write populates cache, ending the race for all subsequent requests. Secondary lock (Option B) risks deadlocks with nested DynamoDB locks. Pre-check alias (Option C) adds consistent read cost to 100% of fallbacks to save <1%. Parallel calls actually increase availability (if one Lambda freezes, other still populates cache). Documented in Section 6.9.

- Q: `_estimate_cache_age_from_dynamodb()` and `OHLCReadThroughCache.get_age()` are referenced in code but never defined — `X-Cache-Age` would always be 0, breaking frontend "Last updated" display and CloudWatch staleness alerting. → A: **Derivation over redundancy (no new DynamoDB attributes)**. L1 (in-memory): `OHLCReadThroughCache` stores `_timestamps` dict mapping key→insertion time; `get_age(key)` returns `int(time.time() - inserted_at)`. Negligible memory (one float per entry). L2 (DynamoDB): derive from existing `ExpiresAt` attribute — `WrittenAt = ExpiresAt - TTL_DURATION`, `Age = now - WrittenAt`. No new `WrittenAt` attribute needed (saves storage cost across millions of rows). `_expires_at` stored as transient attribute on first `PriceCandle` during conversion. `max(0, age)` clamps for minor clock skew. Updated `OHLCReadThroughCache.set()` to track timestamps; updated `get_or_fetch()` to use `self.set()` (not `self._cache.set()`) for timestamp consistency.

- Q: `_estimate_expected_candles()` may drift by 1 candle on US DST transition days (2 days/year) because formula assumes fixed 6.5 trading hours — actual candle count from Tiingo may differ. With 100% completeness threshold, this forces unnecessary Tiingo re-fetch on those days. Worth fixing? → A: **Accept as known limitation — document, do not fix**. Cost is ~100 extra Tiingo API calls/year (~50 tickers × 2 DST days). Self-correcting: fresh fetch populates cache with actual candle count. `exchange_calendars` (Option B) adds maintenance tax and dependency to hot path for 0.6% of days. 1-candle tolerance (Option C) weakens data contract for all 363 normal days to handle 2 edge-case days — technically allows incomplete data into cache permanently. Documented in Section 11.9 code comments.

### Session 2026-02-07 (Round 20 - Implementation Timing & Degraded Mode)

- Q: When `LocalCircuitBreaker` is open (DynamoDB degraded), `_fetch_with_lock` still attempts lock acquisition (DynamoDB PutItem), fails, enters "lock not acquired" branch, polls DynamoDB 15×200ms = 3s — all returning `None`. Burns 3 seconds doing nothing before falling through to Tiingo. → A: **CB open → skip lock+poll entirely, fetch directly from Tiingo ("Degraded Mode")**. The thundering herd lock is a luxury provided by DynamoDB as coordination service. If the coordination service is down, the lock is unavailable — attempting to wait on a broken lock degrades P99 latency for zero functional gain. When `_DDB_BREAKER.is_open()`, bypass the entire lock+poll path and go direct-to-source (~800ms Tiingo latency vs 3800ms wasted). Tiingo is still protected by its own distributed `CircuitBreakerManager`. Half-open probe on `LocalCircuitBreaker` automatically re-enables locking when DynamoDB recovers. X-Ray traces during degraded mode show clean direct line to Tiingo (no noise from 15 failed polls). Add test: D21 `test_cb_open_skips_lock_direct_to_tiingo`.

- Q: `_fetch_with_lock` holds the lock during Tiingo fetch (~800ms) AND `batch_write_with_retry` (up to 10s hard cap during throttling) = 10,800ms total lock hold. But waiters timeout at 3000ms — they all fall through to Tiingo, defeating the thundering herd lock. → A: **Release lock after Tiingo fetch + in-memory populate, fire-and-forget write-through AFTER lock release ("Fast Release" pattern)**. The lock's purpose is to serialize the Tiingo fetch (expensive: latency + API credits), NOT the DynamoDB write. Once data is in `ResolutionCache` (L1), the thundering herd is defeated for same-instance waiters. Cross-instance waiters polling DynamoDB will see data as soon as the background write completes (~50ms normal, up to 10s throttled) — still within their 3s polling window for the normal case. Lock hold reduced from ~10,800ms worst-case to ~800ms (API latency only). Write-through `await`-ed after lock release — NOT `asyncio.create_task()` (see Q3 refinement below). X-Ray shows `DynamoDBLock` segment closing quickly, `BatchWrite` as separate awaited segment. Add test: D22 `test_lock_released_before_write_through`.

- Q: `asyncio.create_task()` fire-and-forget write-through (Q2) risks Lambda freeze mid-write — AWS Lambda can freeze the execution environment after handler returns, leaving stale TCP connections, orphaned boto3 sessions, and lost writes. → A: **`await` the write-through after lock release, not `create_task()`**. Refines Q2: the lock is still released after Tiingo fetch + L1 populate (~800ms hold), but the write-through is `await`-ed before the handler returns (~50ms additional billed time). This guarantees: (1) DynamoDB write completes before freeze, (2) boto3 connection pool returns to clean state for next warm start, (3) no "retry storms" from frozen writes failing on next invocation, (4) X-Ray trace shows complete Lock→Tiingo→Write sequence with no orphaned segments. The ~50ms write cost is the price of reliability — avoidable only if candle data were truly disposable (it isn't: cache misses spike Tiingo bill). Add test: D23 `test_write_through_completes_before_handler_returns`.

- Q: `LocalCircuitBreaker` is per-instance (in-memory-only). 50 concurrent Lambda instances during DynamoDB brownout = 50 independent breakers, each needing 3 failures to open = 150-call spike before all breakers converge. Cold starts reset breakers even if DynamoDB still degraded. No cross-instance visibility. → A: **Accept as trade-off of cell-based resilience — document and alert, no external coordination**. Adding SSM Parameter Store (~50ms per request) or Lambda config API creates a permanent latency tax on healthy requests and adds a new critical-path dependency during the exact moment regional services may be under pressure. The 150-call spike is a statistical blip for DynamoDB on-demand billing (~2-3 seconds across staggered cold starts). Many discovery failures occur during Lambda Init phase (free 10s burst CPU window) — users may not feel it. Cross-instance visibility via EMF: emit `CircuitBreakerOpenCount` metric from each instance; CloudWatch alarm on Sum > 10 in 1 minute fires high-severity SNS alert, providing "global visibility from local intelligence." Each instance as independent cell = high availability (Instance A's flaky network path doesn't drag down Instance B). Add test: D24 `test_cold_start_resets_circuit_breaker_to_closed`.

- Q: Section 4.8 `OHLCReadThroughCache` still uses `from cachetools import TTLCache` (not in requirements) and `from typing import Callable` (Ruff UP035 violation). All direct `._cache[key]` access patterns assume `TTLCache` dict-like interface, but `ResolutionCache` uses `.get()`/`.set()` methods. → A: **Update Section 4.8 to use `ResolutionCache(max_size=1000, default_ttl=3600)` with `.get()`/`.set()` interface**. Imports changed to `from collections.abc import Callable, Awaitable` (PEP 585/603). All direct `._cache[key] = value` access replaced with `_ohlc_read_through_cache.set(key, value)` and `._cache[key]` reads with `.get(key)`. `OHLCReadThroughCache` exposes `.get()`, `.set()`, `.has()`, `.get_age()` methods wrapping `ResolutionCache`. Thread safety rule unchanged — all access on event loop thread only. `ResolutionCache.clear()` used for test isolation.

- Q: No handler-level hard timeout — worst-case flow (all dependencies slow): L1 miss + L2 retry (3.5s) + lock (50ms) + double-check L2 (3.5s) + Tiingo (30s!) + write-through (10s) = ~47s. API Gateway 29s limit → user sees 504 while Lambda keeps burning compute. → A: **`asyncio.wait_for()` handler-level "Emergency Brake" with 5s hard ceiling + stale fallback**. `DASHBOARD_TIMEOUT_SECONDS = 5.0` wraps entire L1→L2→Lock→L3 flow. Tiingo `httpx.Client.TIMEOUT` reduced from 30s to 4s (1s buffer for: double-check L2 ~200ms, JSON serialization ~150ms, X-Ray/EMF flush ~50ms, stale fallback logic ~100ms). On `TimeoutError`: (1) check L1 for stale data (0ms), (2) if L1 empty and CB closed, "last gasp" L2 read with 100ms timeout + no retries + eventual consistency, (3) if any data found, return 200 OK with `X-Cache-Source: stale` + `X-Cache-Age: <seconds>`, (4) if total failure (cold start + L2 unavailable), return 503 + `Retry-After: 5`. `X-Cache-Age` header enables frontend "Last updated Xm ago" display. CloudWatch Synthetics alert on stale percentage >5%. P99 latency deterministically capped at 5s. New section 4.10 added. Add tests: D25 `test_handler_timeout_serves_stale_l1_data`, D26 `test_handler_timeout_last_gasp_l2_read`, D27 `test_handler_timeout_total_failure_returns_503`, E31 `test_tiingo_4s_timeout_within_handler_5s_budget`.

### Session 2026-02-07 (Round 19 - Source Code Blind Spots)

- Q: `CircuitBreakerManager` persists state TO DynamoDB — when DynamoDB is down, `record_failure("dynamodb_cache")` calls `self.table.put_item()` which also fails, creating a circular dependency where the circuit never opens. → A: **Use in-memory-only `LocalCircuitBreaker` for DynamoDB cache** — NOT the DynamoDB-persisted `CircuitBreakerManager`. Implemented as a `@protect_me` decorator (module-level singleton `_DDB_BREAKER = LocalCircuitBreaker(threshold=3, timeout=30)`). `is_open()` costs nanoseconds (dict lookup), no network I/O. Protects BOTH reads and writes — if DynamoDB is degraded, skip writes too (prevents "zombie writes" wasting Lambda duration and thread pool resources). Existing `CircuitBreakerManager` remains for Tiingo/Finnhub/SendGrid (distributed, DynamoDB-persisted). **Supersedes Round 18 Q4** — `"dynamodb_cache"` is NOT added to `CircuitBreakerManager`.

- Q: Resolution fallback creates orphaned lock + cache key mismatch — lock acquired for `LOCK#ohlc:AAPL:5:1M:...` but data written under `ohlc:AAPL:D:1M:...` (different key). Waiters polling the "5" key never find data, all timeout after 3000ms, all call Tiingo. → A: **Cache aliasing (double write)** — on resolution fallback, write data under BOTH the original resolution key AND the actual resolution key. Alias key (`ohlc:AAPL:5:...`) gets shorter TTL (5 minutes) so it expires quickly if high-res data becomes available later. Actual key (`ohlc:AAPL:D:...`) gets standard TTL. Add `res_a` (Resolution Actual) metadata field to DynamoDB items — completeness check validates against `res_a` (not requested resolution), so 5 daily candles pass validation when stored under a 5-min alias. Frontend already handles `resolution_fallback: true` in `OHLCResponse`.

- Q: `_tiingo_cache` in tiingo.py caches BOTH OHLC and News API responses (shared dict, 1hr OHLC TTL, 30min News TTL). Removing it entirely breaks News/Sentiment endpoint caching (~1ms → ~500-800ms regression). → A: **Surgical bypass for OHLC only** — OHLC adapter methods (`get_ohlc`, `get_intraday_ohlc`) pass `use_cache=False` to skip adapter-level dict. News/Sentiment methods continue using `_tiingo_cache` with existing TTLs. DynamoDB + `OHLCReadThroughCache` handle OHLC caching exclusively. Adapter becomes stateless for OHLC calls only. **Extends Round 18 Q2 scope** — was "remove `_ohlc_cache`", now also "bypass adapter cache for OHLC path".

- Q: `@dynamodb_retry` (tenacity, 3 attempts) + `dynamodb_batch_write_with_retry` (3 retries) can nest, causing 9 retries × exponential backoff = up to 180s blocking. → A: **Strict retry boundary — never nest**. `@dynamodb_retry` for single-item ops ONLY (lock PutItem, single Query). `dynamodb_batch_write_with_retry` for BatchWriteItem ONLY — includes 10-second `MAX_BATCH_RETRY_DURATION_SECONDS` hard cap, returns structured `BatchWriteStats(written, failed, retries, duration_ms)` dict. Uses EMF (`print(json.dumps(...))`) for metrics inside worker thread (thread-safe, no X-Ray context needed). X-Ray subsegments created on event loop thread BEFORE `asyncio.to_thread()`, enriched with annotations AFTER await returns (avoids orphaned segments from thread-local storage gap).

- Q: Spec introduces `from cachetools import TTLCache` but `cachetools` not in any requirements file. Also `from typing import Callable` violates Ruff UP035. → A: **Skip `cachetools` entirely** — reuse existing `ResolutionCache` from `lib/timeseries/cache.py` (battle-tested `OrderedDict`-based LRU). Modify `ResolutionCache` constructor to accept optional `default_ttl: int | None = None` parameter (~3-5 line delta). When `default_ttl` is set, all entries use fixed TTL; when `None`, falls back to existing per-resolution TTL logic. `OHLCReadThroughCache` wraps `ResolutionCache(default_ttl=3600, max_size=1000)`. All new code uses `from collections.abc import Callable, Awaitable` (modern PEP 585/603). **Rolls back Round 15 SLRU decision** — simple LRU sufficient when backing store is DynamoDB (~20ms miss penalty); Lambda lifecycle too short for SLRU frequency tracking to provide meaningful benefit.

### Session 2026-02-06 (Round 18 - Architecture Reconciliation)

- Q: BatchWriteItem (Section 4.2 write-through, 25-item batches) vs ConditionExpression (`updated_at` from Round 16) are architecturally incompatible — DynamoDB BatchWriteItem does NOT support ConditionExpression. How do we reconcile? → A: **Drop `updated_at` ConditionExpression for cache writes** — accept that frozen Lambda can overwrite newer data (rare edge case). OHLC candle data is immutable historical data; the only risk is a frozen Lambda writing the same candle with a slightly different timestamp, which is idempotent. Lock acquisition (single PutItem) retains its ConditionExpression. Tests D15/D16 (`test_frozen_lambda_stale_write_rejected`, `test_conditional_write_newer_wins`) removed — candle writes are idempotent, no stale-write protection needed.

- Q: Codebase has 4 cache layers (not 3): Layer 0 `_tiingo_cache` (raw API, 1h TTL), Layer 1 `_ohlc_cache` dict (JSON response, 5-60min TTL), Layer 2 `OHLCReadThroughCache._cache` (PriceCandle list, 1h TTL), Layer 3 DynamoDB. Layers 1 and 2 store different types with different TTLs — dual in-memory caches cause invalidation risk and doubled heap usage. How do we consolidate? → A: **Replace `_ohlc_cache` dict with `OHLCReadThroughCache`** — single in-memory layer storing PriceCandle objects. Refactor `get_ohlc_data()` to use `OHLCReadThroughCache.get_or_fetch()` exclusively. Remove `_ohlc_cache`, `_get_cached_ohlc()`, `_set_cached_ohlc()`, `_ohlc_cache_stats`, `invalidate_ohlc_cache()`. Unified invalidation — one cache to clear, not two. Memory-efficient — no duplicate storage of same data in different formats. Return frozen/immutable copies from cache to prevent mutation on shared event loop.

- Q: `_calculate_ttl()` uses `date.today()` which returns UTC date. Between 4PM ET (market close) and midnight UTC (~3 hours/day), finalized daily data incorrectly gets 5-minute TTL instead of 90-day TTL because UTC date still equals "today" even though the market day is over. → A: **Use `datetime.now(ZoneInfo("America/New_York")).date()`** in `_calculate_ttl()`. `zoneinfo` is stdlib (Python 3.9+). Reuse existing `ET = ZoneInfo("America/New_York")` from `shared/utils/market.py`. Also use market-timezone-aware date for the `is_today` check. Covers DST transitions automatically.

- Q: Existing `circuit_breaker.py` (474 lines, DynamoDB-persisted, thread-safe, Pydantic models, per-service locks, half-open state) vs spec's simple dict-based circuit breaker (Section 11.16) — two incompatible CB implementations in the same codebase. → A: ~~**Reuse existing `CircuitBreakerManager`** — register `"dynamodb_cache"` as a new service.~~ (SUPERSEDED by Round 19 Q1: **Use in-memory-only `LocalCircuitBreaker`** with `@protect_me` decorator — avoids circular dependency where DynamoDB-persisted CB can't record DynamoDB failures when DynamoDB is down. `CircuitBreakerManager` remains for Tiingo/Finnhub/SendGrid only.)

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

    # Clear in-memory cache to force DDB read (Round 23: use public .clear() method)
    from src.lambdas.dashboard.ohlc import invalidate_ohlc_cache
    invalidate_ohlc_cache()  # Clears all L1 entries via public API (Round 22/23)

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

async def _read_from_dynamodb(
    ctx: OHLCRequestContext,  # Round 24: frozen context, thread-safe
    consistent_read: bool = False,
) -> list[PriceCandle] | None:
    """Non-blocking DynamoDB cache read.

    THREAD BOUNDARY (Clarified 2026-02-06): asyncio.to_thread() wraps
    ONLY the DynamoDB I/O. The returned data is handled on the event loop
    thread. Never touch TTLCache or module-level dicts inside to_thread().
    """
    if _DDB_BREAKER.is_open():
        return None

    try:
        result = await asyncio.to_thread(
            _read_from_dynamodb_sync, ctx, consistent_read
        )
        _DDB_BREAKER.record_success()
        return result
    except ClientError:
        _DDB_BREAKER.record_failure()
        return None

async def _write_through_to_dynamodb(
    ctx: OHLCRequestContext,  # Round 24: frozen context, thread-safe
    candles: list[PriceCandle],
) -> None:
    """Non-blocking DynamoDB cache write (Phase 2 Awaited).

    Same thread boundary rule: only DynamoDB I/O inside to_thread().
    See Section 4.2 for full implementation (Round 23: async def + to_thread).
    Round 24 Q2: contributes to _DDB_BREAKER health.
    """
    if _DDB_BREAKER.is_open():
        return

    try:
        cached_candles = candles_to_cached(candles, ctx.source, ctx.resolution)
        if not cached_candles:
            return
        await asyncio.to_thread(
            put_cached_candles,
            ticker=ctx.ticker, source=ctx.source, resolution=ctx.resolution,
            candles=cached_candles, end_date=ctx.end_date,
        )
        _DDB_BREAKER.record_success()
    except Exception:
        _DDB_BREAKER.record_failure()
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

**Required Fix (Round 26 Q2 — aligned to source ohlc.py:328):**

Update `src/lambdas/dashboard/ohlc.py` line 353. The source code signature
`(start_date: date, end_date: date, resolution: OHLCResolution)` is canonical.
Section 4.3 line 428 calls as `(ctx.start_date, ctx.end_date, ctx.resolution)` —
caller must pass `OHLCResolution(ctx.resolution)` if `ctx.resolution` is str.

```python
def _estimate_expected_candles(
    start_date: date, end_date: date, resolution: OHLCResolution,
) -> int:
    """Estimated count for the 100% completeness gate.

    Round 26 Q2: Signature preserved from source (ohlc.py:328). Uses date
    range (not days int) for accurate trading-day calculation. Uses
    OHLCResolution enum (not str) for type-safe bars_per_day lookup.

    Known Limitation (Clarified 2026-02-08 Round 21 — DST Transition):
    May drift by 1 candle on US DST transition days (2 days/year: March,
    November). This results in a safe cache-miss/re-fetch, not data corruption.
    Cost: ~100 extra Tiingo API calls/year across ~50 active tickers.
    Self-correcting: fresh fetch populates cache with actual candle count.
    Not worth fixing: exchange_calendars adds maintenance tax to hot path,
    and a 1-candle tolerance (Option C) weakens the data contract for all
    363 normal days just to handle 2 edge-case days.
    """
    total_days = (end_date - start_date).days
    trading_days = int(total_days * 5 / 7)  # Approximate weekday filter
    return trading_days * resolution.bars_per_day
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
2. OHLC response in-memory cache (`_ohlc_read_through_cache` — `OHLCReadThroughCache` instance, Round 18)
3. DynamoDB persistent cache (new)

No unified invalidation exists. Callers might think they've invalidated all caches but layer 1 still serves stale data.

**Impact:** Subtle bugs where cache appears invalidated but stale data is still served. Integration tests may pass incorrectly.

**Decision (Clarified 2026-02-03, updated Round 22):** Add unified `invalidate_all_caches(ticker)` that clears all layers. Each module exports a **public invalidation function** — consumers import functions, never private instances.

**Required Fix:**

1. Export public invalidation API from `ohlc.py` (Round 22 — encapsulation boundary):
```python
# src/lambdas/dashboard/ohlc.py

_ohlc_read_through_cache = OHLCReadThroughCache(...)

def invalidate_ohlc_cache(ticker: str | None = None) -> int:
    """Public API for L2 cache invalidation.

    Args:
        ticker: Stock symbol, or None to clear the entire L1 in-memory cache.

    Returns:
        Count of invalidated entries.
    """
    if ticker:
        return _ohlc_read_through_cache.invalidate(ticker)
    else:
        return _ohlc_read_through_cache.clear()
```

2. Create `src/lambdas/shared/cache/cache_manager.py`:
```python
"""Unified cache management for OHLC data."""

from src.lambdas.shared.adapters.tiingo import invalidate_tiingo_cache
from src.lambdas.dashboard.ohlc import invalidate_ohlc_cache  # Round 22: public API, not private instance

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

    # Layer 2: OHLC response cache (via public API — encapsulation preserved)
    results["ohlc_response"] = invalidate_ohlc_cache(ticker)

    # Layer 3: DynamoDB (optional - usually not needed, data is immutable)
    # Don't delete from DDB by default - historical data doesn't go stale

    return results
```

3. Add `invalidate_tiingo_cache()` to Tiingo adapter if not exists

4. Ensure `OHLCReadThroughCache` exposes `.invalidate(ticker) -> int` and `.clear() -> int` methods (return count of evicted entries)

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

**Decision (Clarified 2026-02-03, updated 2026-02-07 Round 19+20):** Use in-memory-only `LocalCircuitBreaker` with `@protect_me` decorator — NOT the DynamoDB-persisted `CircuitBreakerManager` (which has circular dependency: can't record DynamoDB failure when DynamoDB is down). See Round 19 Q1 for full rationale.

**Degraded Mode (Clarified 2026-02-07 Round 20):** When `LocalCircuitBreaker` is open, skip the entire lock+poll path and fetch directly from Tiingo. The lock is a luxury provided by DynamoDB as coordination service — if the coordinator is down, waiting on a broken lock wastes 3 seconds for zero gain. See Section 4.8 updated flow.

**Half-Open Recovery Behavior (Clarified 2026-02-08 Round 21):**

Single-probe model — matches existing `CircuitBreakerManager` pattern for SRE consistency:

| State | Behavior | Transition |
|-------|----------|------------|
| **CLOSED** | All requests pass through. Failure count tracked. | → OPEN when `failure_count >= threshold` (3) |
| **OPEN** | All requests short-circuited (return None). | → HALF_OPEN when `time.time() > next_probe_time` (30s) |
| **HALF_OPEN** | Exactly 1 probe request allowed through. | Success → CLOSED (reset failures). Failure → OPEN (another 30s). |

**Why single-probe:** In Lambda's short lifecycle, multi-probe (Option B) adds 2 extra ~200ms penalties before giving up. Gradual ramp (Option C) is designed for long-lived 100-node clusters, not ephemeral containers. Single-probe provides instant recovery detection with zero flapping risk — the first failure during half-open immediately re-opens for another protection window.

**Implementation:**

```python
import time

class LocalCircuitBreaker:
    """In-memory-only circuit breaker for DynamoDB cache.

    States: CLOSED → OPEN → HALF_OPEN → CLOSED (or back to OPEN).
    Single-probe half-open: exactly 1 request probes after timeout.
    No network I/O. No external state. Nanosecond checks.
    """

    def __init__(self, threshold: int = 3, timeout: int = 30):
        self.threshold = threshold
        self.timeout = timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self.next_probe_time = 0.0

    def is_open(self) -> bool:
        """Check if circuit is open (should skip DynamoDB)."""
        if self.state == "CLOSED":
            return False
        if self.state == "OPEN" and time.time() > self.next_probe_time:
            self.state = "HALF_OPEN"
            logger.info("Circuit HALF_OPEN — allowing single probe request")
            return False  # Allow probe through
        if self.state == "HALF_OPEN":
            return True  # Block all requests except the one probe already in flight
        return True  # OPEN and timeout not reached

    def record_success(self):
        """Record successful DynamoDB operation."""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit RECOVERED — DynamoDB healthy, lock re-enabled")
        elif self.state == "CLOSED":
            # Reset failure count on any success (prevent slow accumulation)
            self.failure_count = 0

    def record_failure(self):
        """Record failed DynamoDB operation."""
        self.failure_count += 1
        if self.state == "HALF_OPEN" or self.failure_count >= self.threshold:
            self.state = "OPEN"
            self.next_probe_time = time.time() + self.timeout
            logger.warning(
                "Circuit OPENED — DynamoDB degraded, entering bypass mode",
                extra={"failures": self.failure_count, "probe_in": self.timeout},
            )

    def reset(self):
        """Reset to CLOSED. FOR TESTING ONLY."""
        self.state = "CLOSED"
        self.failure_count = 0
        self.next_probe_time = 0.0

# Module-level singleton — nanosecond is_open() check, no network I/O
_DDB_BREAKER = LocalCircuitBreaker(threshold=3, timeout=30)
```

**Integration in async wrapper layer:**

Circuit breaker checks MUST run on the event loop thread (async wrappers), NOT inside the sync functions that run in `asyncio.to_thread()`. This preserves the thread-boundary rule from Section 4.8.

```python
# In the async wrapper (event loop thread)
# Round 24: ctx replaces individual params; frozen for thread safety
async def _read_from_dynamodb(
    ctx: OHLCRequestContext,
    consistent_read: bool = False,
) -> list[PriceCandle] | None:
    if _DDB_BREAKER.is_open():
        logger.debug("DynamoDB circuit open, skipping cache read")
        return None

    try:
        result = await asyncio.to_thread(
            _read_from_dynamodb_sync, ctx, consistent_read
        )
        _DDB_BREAKER.record_success()  # Event loop thread — safe
        return result
    except ClientError as e:
        _DDB_BREAKER.record_failure()  # Event loop thread — safe
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
| `CircuitBreakerOpenCount` | Sum >10 in 1 min | PagerDuty | Critical | Correlated DynamoDB brownout — multiple instances opened breakers (Round 20 Q5) |
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

# Usage in handler (Round 25: ctx.* accessors replace bare variables)
@logger.inject_lambda_context(log_event=True)
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handler(event, context):
    # ctx constructed per Section 4.0/4.0.1 (Round 24+25)
    logger.info("Cache lookup", extra={
        "ticker": ctx.ticker,
        "cache_key": ctx.cache_key,
        "resolution": ctx.resolution,
        "source": ctx.source,
    })
    # request_id, function_name, cold_start automatically injected
```

**Cache-Specific Logging (Round 25: post-await instrumentation pattern):**

X-Ray subsegments MUST be created on the event loop thread (async wrapper), NOT inside `asyncio.to_thread()` worker threads. Worker threads lack X-Ray context — subsegments created there become orphaned segments. This follows the "Clean Room" pattern from Round 19 Q4: sync function = pure I/O, async wrapper = orchestration + tracing.

```python
# In the async wrapper (Section 11.7) — event loop thread
# Round 25: replaces pre-Round-24 @tracer.capture_method on sync function
async def _read_from_dynamodb(
    ctx: OHLCRequestContext,
    consistent_read: bool = False,
) -> list[PriceCandle] | None:
    if _DDB_BREAKER.is_open():
        return None

    # X-Ray subsegment on event loop thread (safe)
    with tracer.provider.in_subsegment("dynamodb_cache_read") as subsegment:
        subsegment.put_annotation("ticker", ctx.ticker)
        subsegment.put_annotation("cache_key", ctx.cache_key)
        subsegment.put_annotation("consistent_read", consistent_read)

        try:
            # Blocking I/O offloaded to worker thread (Section 4.3 sync inner)
            result = await asyncio.to_thread(
                _read_from_dynamodb_sync, ctx, consistent_read
            )

            # Post-await enrichment — back on event loop thread
            subsegment.put_annotation("status", "hit" if result else "miss")
            _DDB_BREAKER.record_success()

            if not result:
                logger.info("Cache miss", extra={
                    "ticker": ctx.ticker,
                    "cache_key": ctx.cache_key,
                    "reason": "no_items_or_incomplete",
                })

            return result
        except ClientError as e:
            subsegment.put_annotation("status", "error")
            subsegment.add_exception(e)
            _DDB_BREAKER.record_failure()
            return None
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

**CloudWatch Logs Insights Query (for debugging, Round 25: ctx-aware field names):**
```sql
fields @timestamp, @message, ticker, cache_key, source, request_id
| filter @message like /Cache miss/
| sort @timestamp desc
| limit 100
```

---

## 15. Canonical Test Plan (Backwards-Engineered)

**Full Test Plan:** See [ohlc-cache-remediation-tests.md](ohlc-cache-remediation-tests.md) (180 tests across 11 categories; D15/D16 removed R18; D21-D27, E31 added R20; D28-D31 added R21; D32-D35 added R23; D36-D39 added R24). R25 helper function tests (`_resolve_date_range`, `_get_default_source`) to be formally numbered during `/speckit.plan`.

### Quick Reference

| Category | Tests | Focus |
|----------|-------|-------|
| A: Cache Keys | 10 | Stale data, key collisions |
| B: Data Integrity | 14 | Corruption, precision, truncation |
| C: Timing & TTL | 15 | Expiry, freshness, clock drift |
| D: Race Conditions | 36 | Thundering herd, locks, dirty reads, degraded mode, handler timeout, two-phase persistence, half-open probing, breaker write visibility, OHLCRequestContext (D15/D16 removed R18; D21-D27 added R20; D28-D31 added R21; D32-D35 added R23; D36-D39 added R24) |
| E: Dependencies | 31 | DynamoDB, Tiingo, CloudWatch outages, Tiingo 4s timeout (E31 added R20) |
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
