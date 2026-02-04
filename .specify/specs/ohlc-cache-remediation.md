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
    - Partial data (<80% coverage)
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

        # Validate coverage (80% threshold)
        expected = _estimate_expected_candles(start_date, end_date, resolution)
        if len(price_candles) < expected * 0.8:
            logger.info(
                "DynamoDB cache partial hit, fetching fresh",
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

### 6.1 Partial Cache Hit (<80% Coverage)
**Behavior:** Treat as cache miss, fetch fresh from Tiingo
**Rationale:** Partial data is confusing; users expect complete ranges

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
| `test_read_returns_none_on_partial_hit` | <80% coverage treated as miss |
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
