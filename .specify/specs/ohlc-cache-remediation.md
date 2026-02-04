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
4. **Add `PriceCandle.from_cached_candle()`** - Converter method for cached data
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
) -> None:
    """Persist OHLC candles to DynamoDB for cross-invocation caching.

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
**New Method:** `PriceCandle.from_cached_candle()`

**Implementation:**
```python
@classmethod
def from_cached_candle(
    cls,
    cached: "CachedCandle",
    resolution: OHLCResolution,
) -> "PriceCandle":
    """Create PriceCandle from DynamoDB cached candle."""
    # Import here to avoid circular dependency
    from src.lambdas.shared.cache.ohlc_cache import CachedCandle

    # Format date based on resolution
    if resolution == OHLCResolution.DAILY:
        date_value = cached.timestamp.date()
    else:
        date_value = cached.timestamp

    return cls(
        date=date_value,
        open=cached.open,
        high=cached.high,
        low=cached.low,
        close=cached.close,
        volume=cached.volume,
    )
```

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

---

## 5. Data Flow (After Implementation)

```
Request: GET /api/v2/tickers/AAPL/ohlc?range=1M&resolution=D

1. Check Response Cache (in-memory, 1hr TTL)
   ├─ HIT → Return cached OHLCResponse
   └─ MISS ↓

2. Check DynamoDB Cache (persistent)
   ├─ HIT → Build response, cache in-memory, return
   └─ MISS ↓

3. Call Tiingo API
   ├─ SUCCESS → Write-through to DynamoDB, cache in-memory, return
   └─ FAILURE → Return 503/404 error
```

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
**Decision:** Acceptable for now; DynamoDB queries are fast (<50ms)
**Future:** Wrap in `asyncio.to_thread()` if latency becomes issue

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

### 7.1 Unit Tests
| Test | Description |
|------|-------------|
| `test_cache_key_includes_end_date` | Predefined ranges include end_date |
| `test_different_days_different_keys` | Same range on different days → different keys |
| `test_custom_range_includes_both_dates` | Custom ranges include start and end |
| `test_write_through_calls_put_cached_candles` | Write-through invokes DynamoDB |
| `test_write_through_failure_does_not_raise` | Write failure doesn't fail request |
| `test_read_returns_candles_on_hit` | Cache hit returns converted candles |
| `test_read_returns_none_on_miss` | Cache miss returns None |
| `test_read_returns_none_on_incomplete_data` | <100% expected candles treated as miss |
| `test_from_cached_candle_daily` | Daily candles convert timestamp to date |
| `test_from_cached_candle_intraday` | Intraday candles preserve datetime |
| `test_round_trip_preserves_data` | OHLCCandle → CachedCandle → PriceCandle equality |

### 7.2 Integration Tests
| Test | Description |
|------|-------------|
| `test_first_request_populates_dynamodb` | Tiingo fetch writes to DDB |
| `test_second_request_reads_from_dynamodb` | Cached data served from DDB |

### 7.3 E2E Tests (Playwright)
| Test | Description |
|------|-------------|
| `test_chart_loads_data_on_first_visit` | Chart displays price data |
| `test_chart_loads_quickly_on_repeat_visit` | Cache hit is fast (<2s) |
| `test_time_range_change_loads_without_error` | Range switching works |

---

## 8. Implementation Order

| # | Task | File | Priority | Depends On |
|---|------|------|----------|------------|
| 1 | Fix cache key design | `ohlc.py` | P0 | - |
| 2 | Add write-through | `ohlc.py` | P1 | #1 |
| 3 | Add cache reading | `ohlc.py` | P2 | #1, #2 |
| 4 | Add `from_cached_candle()` | `models/ohlc.py` | P2 | - |
| 5 | Add local OHLC table | `run-local-api.py` | P3 | - |
| 6 | Add unit tests | `tests/unit/` | P4 | #1-5 |
| 7 | Add integration tests | `tests/integration/` | P4 | #1-5 |
| 8 | Add E2E tests | `frontend/tests/e2e/` | P4 | #1-5 |

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
| DDB throttling | Low | Medium | On-demand billing mode, backoff |
| Stale data served | Medium | Low | Document TTL, market hours logic |
| Timezone bugs | Medium | High | All timestamps UTC, unit tests |
| Circular imports | Low | Medium | Local imports in functions |

---

## Clarifications

### Session 2026-02-03
- Q: Env var fallback policy for `_get_table_name()` when `OHLC_CACHE_TABLE` is not set? → A: Remove fallback, raise ValueError if env var missing (fail-fast)
- Q: Resolution format mismatch - docstring shows "5m" but code passes "5"? → A: Use OHLCResolution enum values as-is ("5", "60", "D") - fix misleading docstring
- Q: Distinguishing cache miss vs cache error? → A: Log at ERROR level for failures, add CloudWatch metric for cache errors, add alarm that fires once on non-zero then mutes for 1 hour
- Q: Async/sync event loop blocking from sync DynamoDB calls in async endpoint? → A: Wrap sync DynamoDB calls in `asyncio.to_thread()` now
- Q: Integration test to prevent regression of cache not being called? → A: Functional test - first request writes to mock DDB, second request reads from it (verify actual data round-trip)

### Session 2026-02-03 (Round 2)
- Q: Volume=None from Tiingo IEX crashes cache write with int(None) - how to handle? → A: Fix at adapter layer - Tiingo adapter should return volume=0 when unavailable, not None. Normalize data at system boundary.
- Q: DynamoDB query pagination not handled - silent truncation if >1MB? → A: Add warning log if LastEvaluatedKey present, but don't paginate (detect before it bites)
- Q: Estimate function has math error - line 353 multiplies by 7 instead of 6.5? → A: Fix math to `return int(days * 5 / 7 * 6.5)` to match comment
- Q: 80% coverage threshold allows serving incomplete/stale data - acceptable? → A: Remove 80% threshold entirely - require 100% expected candles for cache hit. User always gets complete data.
- Q: Three cache layers with separate invalidation - risk of partial invalidation bugs? → A: Add unified `invalidate_all_caches(ticker)` that clears all layers. Remove/replace obsolete partial invalidate functions - ONE function clears ALL layers.

### Session 2026-02-03 (Round 3)
- Q: Unprocessed BatchWriteItems logged but NOT retried - data silently lost? → A: Add retry loop with exponential backoff (max 3 retries) + CloudWatch metric for unprocessed items
- Q: DynamoDB client created fresh every call - connection overhead? → A: Cache client at module level (singleton pattern) + audit ALL cache clients across codebase are singletons
- Q: Finnhub adapter also has volume=None bug (line 378) - fix for consistency? → A: Fix Finnhub adapter to return volume=0 when unavailable (same as Tiingo fix)
- Q: No circuit breaker for DynamoDB failures - latency penalty during outages? → A: Add simple circuit breaker (skip DDB for 60s after 3 consecutive failures) + CloudWatch metric that triggers alarm then mutes for 1 hour
- Q: No production verification of cache effectiveness - mocked tests don't catch deployment issues? → A: Add post-deployment smoke test that fetches ticker twice and verifies cache hit in logs

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

    # Clear in-memory cache to force DDB read
    from src.lambdas.dashboard.ohlc import invalidate_ohlc_cache
    invalidate_ohlc_cache("AAPL")

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
def _read_from_dynamodb(...):
    # ... query logic ...

    # Emit CloudWatch metric
    try:
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
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
    """Non-blocking DynamoDB cache read."""
    return await asyncio.to_thread(
        _read_from_dynamodb_sync,
        ticker, source, resolution, start_date, end_date
    )

async def _write_through_to_dynamodb(...) -> None:
    """Non-blocking DynamoDB cache write."""
    await asyncio.to_thread(
        _write_through_to_dynamodb_sync,
        ticker, source, resolution, ohlc_candles
    )
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
# In _read_from_dynamodb() exception handler:
except Exception as e:
    logger.error(  # Changed from warning
        "DynamoDB cache read failed, falling back to API",
        extra=get_safe_error_info(e),
    )
    # Emit CloudWatch metric for alerting
    try:
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
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
    # Emit CloudWatch metric for alerting
    try:
        cloudwatch = boto3.client('cloudwatch')
        cloudwatch.put_metric_data(
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

**Decision (Clarified 2026-02-03):** Add retry loop with exponential backoff (max 3 retries) + CloudWatch metric for unprocessed items.

**Required Fix:**
Update `src/lambdas/shared/cache/ohlc_cache.py` `put_cached_candles()`:
```python
import time

# Inside the batch loop:
for i in range(0, len(write_requests), 25):
    batch = write_requests[i : i + 25]
    unprocessed = batch
    retries = 0
    max_retries = 3

    while unprocessed and retries < max_retries:
        response = client.batch_write_item(
            RequestItems={table_name: unprocessed if retries > 0 else batch},
        )
        unprocessed = response.get("UnprocessedItems", {}).get(table_name, [])

        if unprocessed:
            retries += 1
            if retries < max_retries:
                # Exponential backoff: 100ms, 200ms, 400ms
                time.sleep(0.1 * (2 ** (retries - 1)))

    written += len(batch) - len(unprocessed)

    if unprocessed:
        logger.error(
            "OHLC cache writes failed after retries",
            extra={"count": len(unprocessed), "retries": max_retries},
        )
        # Emit CloudWatch metric
        try:
            cloudwatch = boto3.client('cloudwatch')
            cloudwatch.put_metric_data(
                Namespace='SentimentAnalyzer/OHLCCache',
                MetricData=[{
                    'MetricName': 'UnprocessedWriteItems',
                    'Value': len(unprocessed),
                    'Unit': 'Count',
                }]
            )
        except Exception:
            pass
```

### 11.13 DynamoDB Client Created Fresh Every Call

**Problem:** `_get_dynamodb_client()` creates a new boto3 client on every call, adding ~50-100ms connection overhead per operation.

**Impact:** Cache operations that should be fast (~20ms) become slow (~70-120ms), negating performance benefits.

**Decision (Clarified 2026-02-03):** Cache client at module level (singleton pattern) + audit ALL cache clients across codebase.

**Audit Findings (boto3 client patterns in codebase):**

| Pattern | Files | Status |
|---------|-------|--------|
| Singleton (good) | `chaos_injection.py`, `chaos.py`, `analysis/handler.py` | ✓ |
| Fresh each call (bad) | `ohlc_cache.py`, `ticker_cache.py`, `sse_streaming/config.py`, `auth.py` | FIX |
| Dependency injection (good) | `notification.py`, `metrics.py` | ✓ |

**Required Fix for ohlc_cache.py:**
```python
# Module-level singleton
_dynamodb_client = None

def _get_dynamodb_client():
    """Get or create DynamoDB client (singleton)."""
    global _dynamodb_client
    if _dynamodb_client is None:
        region = os.environ.get("AWS_REGION") or os.environ.get(
            "AWS_DEFAULT_REGION", "us-east-1"
        )
        _dynamodb_client = boto3.client("dynamodb", region_name=region)
    return _dynamodb_client
```

**Follow-up task:** Audit and fix other fresh-client patterns in `ticker_cache.py`, `sse_streaming/config.py`, `auth.py`, etc.

### 11.14 Volume=None Crashes Cache Write for Intraday Data

**Problem:** `candles_to_cached()` line 374 calls `int(getattr(candle, "volume", 0))`. Both Tiingo IEX and Finnhub can return `volume=None`. `int(None)` raises TypeError.

**Affected Adapters:**
- `tiingo.py` line 446: `volume=None,  # IEX doesn't include volume`
- `finnhub.py` line 378: `volume=int(volumes[i]) if i < len(volumes) else None`

**Impact:** Cache writes silently fail for intraday data from either adapter.

**Decision (Clarified 2026-02-03):** Fix at adapter layer - ALL adapters should return `volume=0` when unavailable, not `None`. Normalize data at system boundary.

**Required Fix:**
1. Update `src/lambdas/shared/adapters/tiingo.py` line 446:
   ```python
   # Before (broken)
   volume=None,  # IEX doesn't include volume in resampled data

   # After (fixed)
   volume=0,  # IEX doesn't include volume in resampled data
   ```

2. Update `src/lambdas/shared/adapters/finnhub.py` line 378:
   ```python
   # Before (broken)
   volume=int(volumes[i]) if i < len(volumes) else None,

   # After (fixed)
   volume=int(volumes[i]) if i < len(volumes) else 0,
   ```

3. Add defensive check in `candles_to_cached()` as belt-and-suspenders:
   ```python
   volume=int(getattr(candle, "volume", 0) or 0),
   ```

### 11.15 No Production Verification of Cache Effectiveness

**Problem:** Integration tests use moto (mocked DynamoDB), not real AWS. Deployments could fail due to IAM permissions, missing tables, or network issues that mocked tests don't catch.

**Impact:** Cache could be broken in production while all tests pass green.

**Decision (Clarified 2026-02-03):** Add post-deployment smoke test that fetches ticker twice and verifies cache hit in logs.

**Required Fix:**
Add `scripts/smoke-test-cache.py`:
```python
#!/usr/bin/env python3
"""Post-deployment smoke test for OHLC cache.

Run after deployment to verify cache is working in production.
Usage: python scripts/smoke-test-cache.py --env preprod
"""
import argparse
import json
import subprocess
import time

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True, choices=["dev", "preprod", "prod"])
    args = parser.parse_args()

    api_url = f"https://api.{args.env}.sentiment-analyzer.example.com"
    ticker = "AAPL"
    endpoint = f"{api_url}/api/v2/tickers/{ticker}/ohlc?range=1W&resolution=D"

    print(f"Testing cache on {args.env}...")

    # Request 1: Should write to DynamoDB cache
    print(f"Request 1: Fetching {ticker}...")
    result1 = subprocess.run(
        ["curl", "-s", "-w", "%{http_code}", endpoint],
        capture_output=True, text=True
    )
    assert result1.returncode == 0, "Request 1 failed"

    # Wait for write-through to complete
    time.sleep(2)

    # Request 2: Should read from DynamoDB cache
    print(f"Request 2: Fetching {ticker} again...")
    result2 = subprocess.run(
        ["curl", "-s", "-w", "%{http_code}", endpoint],
        capture_output=True, text=True
    )
    assert result2.returncode == 0, "Request 2 failed"

    # Verify cache hit in CloudWatch logs
    print("Checking CloudWatch logs for cache hit...")
    log_check = subprocess.run(
        [
            "aws", "logs", "filter-log-events",
            "--log-group-name", f"/aws/lambda/{args.env}-dashboard",
            "--filter-pattern", '"OHLC cache hit (DynamoDB)"',
            "--start-time", str(int((time.time() - 60) * 1000)),
        ],
        capture_output=True, text=True
    )

    if "OHLC cache hit (DynamoDB)" in log_check.stdout:
        print("✅ PASS: Cache hit detected in logs")
    else:
        print("❌ FAIL: No cache hit in logs - cache may not be working")
        exit(1)

if __name__ == "__main__":
    main()
```

**Integration with CI/CD:**
Add to deployment pipeline after `terraform apply`:
```yaml
- name: Smoke test cache
  run: python scripts/smoke-test-cache.py --env ${{ env.ENVIRONMENT }}
```

### 11.16 No Circuit Breaker for DynamoDB Failures

**Problem:** If DynamoDB is unavailable, every request attempts read + write, adding ~100-200ms latency with no mechanism to skip failing operations.

**Impact:** During DynamoDB outages, all OHLC requests are slower even though graceful degradation works.

**Decision (Clarified 2026-02-03):** Add simple circuit breaker (skip DDB for 60s after 3 consecutive failures) + CloudWatch metric with alarm (1-hour mute).

**Required Fix:**
Add to `src/lambdas/shared/cache/ohlc_cache.py`:
```python
import time

# Circuit breaker state (module-level)
_circuit_breaker = {
    "failures": 0,
    "open_until": 0,  # Unix timestamp when circuit closes
    "threshold": 3,   # Failures before opening
    "timeout": 60,    # Seconds to keep circuit open
}

def _is_circuit_open() -> bool:
    """Check if circuit breaker is open (skip DynamoDB)."""
    if _circuit_breaker["open_until"] > time.time():
        return True
    return False

def _record_failure():
    """Record a DynamoDB failure, potentially opening circuit."""
    _circuit_breaker["failures"] += 1
    if _circuit_breaker["failures"] >= _circuit_breaker["threshold"]:
        _circuit_breaker["open_until"] = time.time() + _circuit_breaker["timeout"]
        _circuit_breaker["failures"] = 0
        logger.error(
            "DynamoDB circuit breaker OPEN - skipping cache for 60s",
            extra={"timeout": _circuit_breaker["timeout"]},
        )
        # Emit CloudWatch metric for alerting
        try:
            cloudwatch = boto3.client('cloudwatch')
            cloudwatch.put_metric_data(
                Namespace='SentimentAnalyzer/OHLCCache',
                MetricData=[{
                    'MetricName': 'CircuitBreakerOpen',
                    'Value': 1,
                    'Unit': 'Count',
                }]
            )
        except Exception:
            pass

def _record_success():
    """Record a DynamoDB success, resetting failure count."""
    _circuit_breaker["failures"] = 0
```

**Integration in get_cached_candles():**
```python
def get_cached_candles(...) -> OHLCCacheResult:
    if _is_circuit_open():
        logger.debug("DynamoDB circuit open, skipping cache read")
        return OHLCCacheResult(cache_hit=False)

    try:
        # ... existing query logic ...
        _record_success()
        return result
    except ClientError as e:
        _record_failure()
        return OHLCCacheResult(cache_hit=False)
```

---

## 12. References

- [HL-cache-remediation-checklist.md](docs/cache/HL-cache-remediation-checklist.md)
- [fix-cache-key.md](docs/cache/fix-cache-key.md)
- [fix-cache-writing.md](docs/cache/fix-cache-writing.md)
- [fix-cache-reading.md](docs/cache/fix-cache-reading.md)
- [fix-local-api-tables.md](docs/cache/fix-local-api-tables.md)
- [fix-cache-tests.md](docs/cache/fix-cache-tests.md)
- Feature 1087: OHLC Persistent Cache (original spec)
- Feature 1076/1078: Response cache improvements
