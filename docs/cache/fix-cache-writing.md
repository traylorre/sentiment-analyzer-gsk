# Fix: Cache Writing (Write-Through to DynamoDB)

**Parent:** [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md)
**Priority:** P1 (After cache key fix)
**Status:** [ ] TODO
**Depends On:** [fix-cache-key.md](./fix-cache-key.md)

---

## Problem Statement

After fetching OHLC data from Tiingo, the data is cached **only in-memory**. It is never persisted to DynamoDB, so:
- Lambda cold starts lose all cached data
- Same data is re-fetched from Tiingo repeatedly
- DynamoDB table exists but remains empty (wasted infrastructure)

---

## Current Flow (Broken)

```python
# src/lambdas/dashboard/ohlc.py:364-481

# 1. Fetch from Tiingo
ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)

# 2. Build response
response = OHLCResponse(...)

# 3. Cache in-memory ONLY
_set_cached_ohlc(cache_key, response.model_dump(mode="json"))

# 4. Return
return response

# MISSING: Write to DynamoDB!
```

---

## Solution: Add Write-Through

After successful Tiingo fetch, write candles to DynamoDB using existing `put_cached_candles()`.

### Implementation

```python
# src/lambdas/dashboard/ohlc.py

from src.lambdas.shared.cache.ohlc_cache import (
    put_cached_candles,
    candles_to_cached,
)

async def get_ohlc_data(...) -> OHLCResponse:
    # ... existing validation and cache check ...

    # Fetch from Tiingo
    source = "tiingo"
    candles = []

    if resolution == OHLCResolution.DAILY:
        try:
            ohlc_candles = tiingo.get_ohlc(ticker, start_date, end_date)
            if ohlc_candles:
                candles = [PriceCandle.from_ohlc_candle(c, resolution) for c in ohlc_candles]

                # NEW: Write-through to DynamoDB
                _write_through_to_dynamodb(
                    ticker=ticker,
                    source=source,
                    resolution=resolution.value,
                    ohlc_candles=ohlc_candles,
                )
        except Exception as e:
            logger.warning("Tiingo daily OHLC fetch failed", extra=get_safe_error_info(e))

    # ... rest of function ...


def _write_through_to_dynamodb(
    ticker: str,
    source: str,
    resolution: str,
    ohlc_candles: list,
) -> None:
    """Persist OHLC candles to DynamoDB for cross-invocation caching.

    This is fire-and-forget - errors are logged but don't fail the request.
    Historical data is immutable, so overwrites are safe.

    Args:
        ticker: Stock symbol (e.g., "AAPL")
        source: Data provider ("tiingo" or "finnhub")
        resolution: Candle resolution ("D", "1", "5", etc.)
        ohlc_candles: List of OHLCCandle from adapter
    """
    try:
        # Convert adapter candles to cache format
        cached_candles = candles_to_cached(ohlc_candles, source, resolution)

        if not cached_candles:
            logger.debug("No candles to cache", extra={"ticker": ticker})
            return

        # Write to DynamoDB (batched, max 25 per request)
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
        # Log but don't fail - write-through is best-effort
        logger.warning(
            "OHLC write-through failed",
            extra=get_safe_error_info(e),
        )
```

---

## Edge Cases

### 1. Intraday Data Freshness (Blind Spot #18)

Intraday candles for **today** may change (market still open). Should we cache them?

**Decision:** Yes, cache all fetched data. Reasons:
- Cache TTL in response cache (5-15 min) handles freshness
- DynamoDB cache is source-of-truth for historical data
- Today's incomplete data will be overwritten on next fetch
- **Key insight:** Yesterday's intraday data is immutable; today's is mutable

### 2. Partial Day Data

If market closes at 4 PM and we fetch at 2 PM, we get incomplete intraday data.

**Decision:** Cache it anyway. Next fetch will overwrite with more complete data.

### 3. Write Failures

DynamoDB write fails (throttling, network error).

**Decision:** Log and continue. Write-through is best-effort; request still succeeds with in-memory cache.

### 4. Duplicate Writes

Same candles written multiple times (user refreshes page).

**Decision:** No problem. DynamoDB PutItem is idempotent for same PK/SK. Overwrites are cheap.

### 5. Error Response Caching (Blind Spot #16)

Should we cache 404 responses (no data for ticker)?

**Decision:** NO. Never cache error responses. Reasons:
- Ticker may become valid later (new IPO, data provider adds coverage)
- Caching errors masks transient failures
- Only cache successful, non-empty responses

### 6. Data Consistency (Blind Spot #21)

Cached data must be byte-identical to fresh API data.

**Decision:** Use same serialization path:
- `candles_to_cached()` converts OHLCCandle → CachedCandle
- `PriceCandle.from_cached_candle()` converts back
- Add unit test asserting round-trip equality

---

## Implementation Checklist

### Code Changes

- [ ] Import `put_cached_candles`, `candles_to_cached` in `ohlc.py`
- [ ] Add `_write_through_to_dynamodb()` helper function
- [ ] Call write-through after daily OHLC fetch (line ~376)
- [ ] Call write-through after intraday OHLC fetch (line ~391)
- [ ] Call write-through after fallback daily fetch (line ~417)

### Error Handling

- [ ] Wrap write-through in try/except
- [ ] Log failures with `get_safe_error_info()`
- [ ] Never raise from write-through (fire-and-forget)

### Logging

- [ ] Log successful writes with count
- [ ] Log failed writes with error info
- [ ] Include ticker, source, resolution in log context

### Testing

- [ ] Unit test: Mock `put_cached_candles`, verify called after fetch
- [ ] Unit test: Write failure doesn't fail request
- [ ] Unit test: Empty candles list doesn't call put
- [ ] Integration test: Verify data appears in DynamoDB after request

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | 18-40 | Add imports |
| `src/lambdas/dashboard/ohlc.py` | 376 | Add write-through for daily |
| `src/lambdas/dashboard/ohlc.py` | 391 | Add write-through for intraday |
| `src/lambdas/dashboard/ohlc.py` | 417 | Add write-through for fallback |
| `src/lambdas/dashboard/ohlc.py` | NEW | Add `_write_through_to_dynamodb()` |
| `tests/unit/dashboard/test_ohlc.py` | NEW | Add write-through tests |

---

## DynamoDB Write Pattern

### Batch Write Behavior

`put_cached_candles()` uses `BatchWriteItem`:
- Max 25 items per batch
- Automatic batching in function
- Unprocessed items logged (no retry for now)

### Item Structure

```json
{
  "PK": {"S": "AAPL#tiingo"},
  "SK": {"S": "D#2025-12-23T00:00:00Z"},
  "open": {"N": "150.0000"},
  "high": {"N": "152.5000"},
  "low": {"N": "149.0000"},
  "close": {"N": "151.2500"},
  "volume": {"N": "50000000"},
  "fetched_at": {"S": "2025-12-23T16:30:00Z"}
}
```

### Cost Estimate

- Daily candles: ~252 trading days/year × 1 WCU each = 252 WCU/ticker/year
- Intraday 5-min: ~78 candles/day × 252 days = ~19,656 WCU/ticker/year
- On-demand pricing: $1.25 per million WCU
- **Estimate:** < $0.10/ticker/year for writes

---

## Verification Steps

After implementation:

```bash
# 1. Run unit tests
pytest tests/unit/dashboard/test_ohlc.py -v -k "write_through"

# 2. Manual verification with local API
python scripts/run-local-api.py
# Make OHLC request
curl "http://localhost:8000/api/v2/tickers/AAPL/ohlc?range=1M&resolution=D"
# Check DynamoDB (requires local-ohlc-cache table - see fix-local-api-tables.md)

# 3. Check logs for write confirmation
# Look for: "OHLC write-through complete"
```

---

## Related

- [fix-cache-key.md](./fix-cache-key.md) - Must be done first (key format)
- [fix-cache-reading.md](./fix-cache-reading.md) - Next step (read from DDB)
- [fix-local-api-tables.md](./fix-local-api-tables.md) - Required for local testing
