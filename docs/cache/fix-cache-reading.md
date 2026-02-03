# Fix: Cache Reading (Query DynamoDB Before Tiingo)

**Parent:** [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md)
**Priority:** P2 (After cache writing fix)
**Status:** [ ] TODO
**Depends On:** [fix-cache-writing.md](./fix-cache-writing.md)

---

## Problem Statement

The OHLC endpoint checks in-memory cache, then **immediately calls Tiingo API**, skipping the DynamoDB persistent cache entirely.

```python
# Current flow in src/lambdas/dashboard/ohlc.py:333-376

# 1. Check in-memory cache
cached_response = _get_cached_ohlc(cache_key, resolution.value)
if cached_response:
    return OHLCResponse(**cached_response)

# 2. SKIP DynamoDB cache (BUG!)

# 3. Call Tiingo directly
ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
```

---

## Solution: Query DynamoDB Before Tiingo

Add DynamoDB cache lookup between in-memory check and Tiingo API call.

### Implementation

```python
# src/lambdas/dashboard/ohlc.py

from datetime import UTC, datetime, time as dt_time
from src.lambdas.shared.cache.ohlc_cache import get_cached_candles
from src.lambdas.shared.models.ohlc import PriceCandle

async def get_ohlc_data(...) -> OHLCResponse:
    # ... validation code ...

    # Cache check #1: In-memory response cache (fastest)
    cache_key = _get_ohlc_cache_key(...)
    cached_response = _get_cached_ohlc(cache_key, resolution.value)
    if cached_response:
        logger.info("OHLC cache hit (in-memory)")
        return OHLCResponse(**cached_response)

    # Cache check #2: DynamoDB persistent cache (survives cold starts)
    ddb_candles = _read_from_dynamodb(
        ticker=ticker,
        source="tiingo",
        resolution=resolution,
        start_date=start_date,
        end_date=end_date,
    )

    if ddb_candles:
        # Build response from DynamoDB data
        response = _build_response_from_cache(
            ticker=ticker,
            candles=ddb_candles,
            resolution=resolution,
            time_range_str=time_range_str,
        )

        # Populate in-memory cache for subsequent requests
        _set_cached_ohlc(cache_key, response.model_dump(mode="json"))

        logger.info(
            "OHLC cache hit (DynamoDB)",
            extra={"ticker": ticker, "candle_count": len(ddb_candles)},
        )
        return response

    # Cache miss: Fetch from Tiingo API
    # ... existing Tiingo fetch code ...


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
    - Query fails (graceful degradation to API)
    - Partial data (less than expected candles)

    Args:
        ticker: Stock symbol
        source: Data provider
        resolution: Candle resolution
        start_date: Range start
        end_date: Range end

    Returns:
        List of PriceCandle if cache hit, None otherwise
    """
    try:
        # Convert dates to datetime for cache query
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
            logger.debug(
                "DynamoDB cache miss",
                extra={"ticker": ticker, "resolution": resolution.value},
            )
            return None

        # Convert CachedCandle to PriceCandle
        price_candles = [
            PriceCandle.from_cached_candle(c, resolution)
            for c in result.candles
        ]

        # Validate we have reasonable coverage
        expected_candles = _estimate_expected_candles(
            start_date, end_date, resolution
        )
        if len(price_candles) < expected_candles * 0.8:
            # Less than 80% coverage - treat as miss, fetch fresh
            logger.info(
                "DynamoDB cache partial hit, fetching fresh",
                extra={
                    "ticker": ticker,
                    "found": len(price_candles),
                    "expected": expected_candles,
                },
            )
            return None

        return price_candles

    except Exception as e:
        # Graceful degradation - log and fall through to API
        logger.warning(
            "DynamoDB cache read failed, falling back to API",
            extra=get_safe_error_info(e),
        )
        return None


def _estimate_expected_candles(
    start_date: date,
    end_date: date,
    resolution: OHLCResolution,
) -> int:
    """Estimate expected candle count for cache validation.

    Used to detect partial cache hits (missing data).
    """
    days = (end_date - start_date).days + 1

    if resolution == OHLCResolution.DAILY:
        # ~252 trading days/year, ~5 per week
        return int(days * 5 / 7)
    elif resolution == OHLCResolution.ONE_HOUR:
        # 6.5 market hours/day, 5 days/week
        return int(days * 5 / 7 * 7)
    else:
        # Intraday: estimate based on resolution
        candles_per_hour = {
            OHLCResolution.ONE_MINUTE: 60,
            OHLCResolution.FIVE_MINUTES: 12,
            OHLCResolution.FIFTEEN_MINUTES: 4,
            OHLCResolution.THIRTY_MINUTES: 2,
        }
        per_hour = candles_per_hour.get(resolution, 12)
        return int(days * 5 / 7 * 6.5 * per_hour)


def _build_response_from_cache(
    ticker: str,
    candles: list[PriceCandle],
    resolution: OHLCResolution,
    time_range_str: str,
) -> OHLCResponse:
    """Build OHLCResponse from cached candles."""
    # Sort by date
    candles.sort(key=lambda c: c.date)

    # Extract dates
    first_candle_date = candles[0].date
    last_candle_date = candles[-1].date
    start_date_value = (
        first_candle_date.date()
        if isinstance(first_candle_date, datetime)
        else first_candle_date
    )
    end_date_value = (
        last_candle_date.date()
        if isinstance(last_candle_date, datetime)
        else last_candle_date
    )

    return OHLCResponse(
        ticker=ticker,
        candles=candles,
        time_range=time_range_str,
        start_date=start_date_value,
        end_date=end_date_value,
        count=len(candles),
        source="tiingo",  # Original source
        cache_expires_at=get_cache_expiration(),
        resolution=resolution.value,
        resolution_fallback=False,
        fallback_message=None,
    )
```

---

## Model Addition: PriceCandle.from_cached_candle()

Need to add a converter method to `PriceCandle`:

```python
# src/lambdas/shared/models/ohlc.py

class PriceCandle(BaseModel):
    # ... existing fields ...

    @classmethod
    def from_cached_candle(
        cls,
        cached: "CachedCandle",
        resolution: OHLCResolution,
    ) -> "PriceCandle":
        """Create PriceCandle from DynamoDB cached candle.

        Args:
            cached: CachedCandle from ohlc_cache
            resolution: Original resolution for date formatting

        Returns:
            PriceCandle instance
        """
        from src.lambdas.shared.cache.ohlc_cache import CachedCandle

        # Format date based on resolution
        if resolution == OHLCResolution.DAILY:
            # Daily: use date only
            date_value = cached.timestamp.date()
        else:
            # Intraday: use full datetime
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

---

## Edge Cases

### 1. Partial Cache Hit

DynamoDB has some but not all candles for the requested range.

**Decision:** Treat as cache miss if < 80% coverage. Fetch fresh from Tiingo.

**Rationale:** Partial data is confusing for users. Better to show complete data.

### 2. DynamoDB Query Failure

Network error, throttling, or permissions issue.

**Decision:** Log warning, fall through to Tiingo API.

**Rationale:** DynamoDB is optimization, not requirement. Graceful degradation.

### 3. Circular Import Risk (Blind Spot #13)

Importing `ohlc_cache` in `ohlc.py` may cause circular dependencies.

**Decision:** Use local imports inside functions if needed:
```python
def _read_from_dynamodb(...):
    from src.lambdas.shared.cache.ohlc_cache import get_cached_candles
    # ... rest of function
```

**Verification:** Test with `python -c "from src.lambdas.dashboard.ohlc import router"` after changes.

### 4. Async/Sync Mismatch (Blind Spot #14)

`get_cached_candles()` is synchronous; `get_ohlc_data()` is async.

**Decision:** Acceptable for now. DynamoDB queries are fast (<50ms).

**Future optimization:** If latency becomes issue, wrap in `asyncio.to_thread()`:
```python
result = await asyncio.to_thread(get_cached_candles, ticker, source, resolution, start, end)
```

### 5. Cold Start Latency Budget (Blind Spot #15)

DynamoDB query adds ~20ms to cold start.

**Decision:** Acceptable tradeoff:
- DynamoDB: ~20ms
- Tiingo API: 500-2000ms
- Net savings: 480-1980ms on cache hit

### 6. Rate Limit Protection (Blind Spot #20)

DynamoDB cache prevents Tiingo 429 errors during traffic spikes.

**Benefit:** High-traffic scenarios (many users viewing same ticker) hit cache instead of exhausting Tiingo quota.

### 3. Stale Intraday Data

DynamoDB has yesterday's intraday data, but user wants today's.

**Decision:** Cache key includes end_date (from fix-cache-key.md), so different days = different queries. No issue.

### 7. Weekend/Holiday Handling (Blind Spot #19)

User requests data on Saturday. Last trading day was Friday.

**Decision:** DynamoDB query range includes weekends; only trading day candles exist. Works correctly.

**Detail:** Query for Dec 20-22 (Sat-Mon) returns only Dec 20 (Fri) candles. This is correct behavior - no trading on weekends.

### 8. Cold Start + Empty DynamoDB

First ever request for a ticker. DynamoDB is empty.

**Decision:** Cache miss → Tiingo fetch → Write-through → Future requests hit cache.

**Key insight:** This is the expected "cache warming" path. First request populates cache for all subsequent requests.

---

## Implementation Checklist

### Code Changes

- [ ] Import `get_cached_candles` in `ohlc.py`
- [ ] Add `_read_from_dynamodb()` helper function
- [ ] Add `_estimate_expected_candles()` helper function
- [ ] Add `_build_response_from_cache()` helper function
- [ ] Add DynamoDB check after in-memory cache check (line ~351)
- [ ] Add `PriceCandle.from_cached_candle()` class method

### Error Handling

- [ ] Wrap DynamoDB read in try/except
- [ ] Return None on any error (graceful degradation)
- [ ] Log failures with `get_safe_error_info()`

### Logging

- [ ] Log cache hit with candle count
- [ ] Log cache miss
- [ ] Log partial hit with found/expected counts
- [ ] Log query failures

### Testing

- [ ] Unit test: DynamoDB hit returns cached data
- [ ] Unit test: DynamoDB miss falls through to Tiingo
- [ ] Unit test: Partial hit (< 80%) treated as miss
- [ ] Unit test: Query failure treated as miss
- [ ] Integration test: Cold start reads from DynamoDB

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | 18-40 | Add imports |
| `src/lambdas/dashboard/ohlc.py` | 351 | Add DynamoDB cache check |
| `src/lambdas/dashboard/ohlc.py` | NEW | Add helper functions |
| `src/lambdas/shared/models/ohlc.py` | NEW | Add `from_cached_candle()` |
| `tests/unit/dashboard/test_ohlc.py` | NEW | Add cache read tests |
| `tests/unit/shared/models/test_ohlc.py` | NEW | Add converter tests |

---

## Performance Considerations

### DynamoDB Query Latency

- Typical Query latency: 5-20ms
- Tiingo API latency: 500-2000ms
- **Improvement:** 25-100x faster on cache hit

### Query Efficiency

```python
# Efficient: Query with SK range
KeyConditionExpression="PK = :pk AND SK BETWEEN :start AND :end"
```

This uses the Sort Key for range filtering, which is O(log n) + O(k) where k is result size.

### Parallel Query Option

For very large ranges (1 year of intraday), could parallelize:

```python
# Future optimization: Parallel month queries
async def _read_from_dynamodb_parallel(...):
    tasks = [
        _query_month(ticker, source, resolution, month)
        for month in months_in_range
    ]
    results = await asyncio.gather(*tasks)
    return flatten(results)
```

**Not needed initially** - single query is fast enough.

---

## Verification Steps

After implementation:

```bash
# 1. Run unit tests
pytest tests/unit/dashboard/test_ohlc.py -v -k "read" -k "dynamodb"

# 2. Populate DynamoDB first (requires write-through)
curl "http://localhost:8000/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D"
# Check logs: "OHLC write-through complete"

# 3. Restart Lambda (simulate cold start)
# Kill and restart local API server

# 4. Request same data
curl "http://localhost:8000/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D"
# Check logs: "OHLC cache hit (DynamoDB)"

# 5. Verify no Tiingo call on second request
# Tiingo logs should NOT appear
```

---

## Related

- [fix-cache-key.md](./fix-cache-key.md) - Required first (key format)
- [fix-cache-writing.md](./fix-cache-writing.md) - Required second (populate DDB)
- [fix-local-api-tables.md](./fix-local-api-tables.md) - Required for local testing
