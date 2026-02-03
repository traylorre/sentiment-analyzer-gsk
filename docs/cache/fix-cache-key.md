# Fix: Cache Key Design

**Parent:** [HL-cache-remediation-checklist.md](./HL-cache-remediation-checklist.md)
**Priority:** P0 (Must fix first)
**Status:** [ ] TODO

---

## Problem Statement

The current cache key for predefined time ranges (1W, 1M, 3M, 6M, 1Y) uses the **range name only**, not actual dates:

```python
# src/lambdas/dashboard/ohlc.py:92-98
def _get_ohlc_cache_key(...) -> str:
    if time_range == "custom" and start_date and end_date:
        return f"ohlc:{ticker}:{resolution}:custom:{start_date}:{end_date}"
    else:
        # BUG: Same key across different days!
        return f"ohlc:{ticker}:{resolution}:{time_range}"
```

### Example of Bug

| Day | Request | Cache Key | Actual Date Range |
|-----|---------|-----------|-------------------|
| Mon Dec 23 | AAPL 1W | `ohlc:AAPL:D:1W` | Dec 16-23 |
| Sun Dec 29 | AAPL 1W | `ohlc:AAPL:D:1W` | Dec 22-29 |

**Result:** Second request returns stale data (Dec 16-23 instead of Dec 22-29).

---

## Root Cause Analysis

Feature 1078 intentionally used range name instead of dates to improve cache hit rate:
> "Use time_range (e.g., "1M") for predefined ranges instead of actual dates. This ensures cache hits when users switch resolutions."

The **intent** was correct (users switching resolutions same day should hit cache), but the **implementation** causes stale data across days.

---

## Solution

### Option A: Include Date in Key (Recommended)

```python
def _get_ohlc_cache_key(
    ticker: str,
    resolution: str,
    time_range: str,
    start_date: date,
    end_date: date,
) -> str:
    """Generate cache key including actual dates.

    Always includes end_date to ensure cache coherency across days.
    Uses end_date only (not start_date) to allow resolution switching
    within the same day to still benefit from cache.
    """
    # Normalize ticker
    ticker_upper = ticker.upper()

    # Use end_date to anchor the cache key
    # This allows different resolutions on same day to share cache intent
    # but prevents cross-day staleness
    date_anchor = end_date.isoformat()

    if time_range == "custom":
        # Custom ranges: include both dates
        return f"ohlc:{ticker_upper}:{resolution}:custom:{start_date.isoformat()}:{end_date.isoformat()}"
    else:
        # Predefined ranges: include end_date for day-anchoring
        return f"ohlc:{ticker_upper}:{resolution}:{time_range}:{date_anchor}"
```

### Option B: Include Only Today's Date

```python
def _get_ohlc_cache_key(...) -> str:
    today = date.today().isoformat()
    return f"ohlc:{ticker.upper()}:{resolution}:{time_range}:{today}"
```

**Pros:** Simpler, always uses "today"
**Cons:** Doesn't work for historical queries with custom dates

### Recommendation: Option A

Option A handles both predefined and custom ranges correctly.

---

## DynamoDB Cache Key Alignment

The DynamoDB cache uses a different key structure:
- **PK:** `{ticker}#{source}` (e.g., `AAPL#tiingo`)
- **SK:** `{resolution}#{timestamp}` (e.g., `D#2025-12-23T00:00:00Z`)

This is **per-candle** storage, not per-response. The in-memory cache stores full responses; DynamoDB stores individual candles.

### Key Format Comparison

| Layer | Key Structure | Scope |
|-------|---------------|-------|
| Response Cache | `ohlc:AAPL:D:1M:2025-12-23` | Full response |
| DynamoDB | PK=`AAPL#tiingo`, SK=`D#2025-12-23T00:00:00Z` | Single candle |

**No conflict** - these serve different purposes.

---

## Implementation Checklist

### Code Changes

- [ ] Update `_get_ohlc_cache_key()` in `src/lambdas/dashboard/ohlc.py`
- [ ] Update call sites to pass `start_date` and `end_date` (already passed, verify)
- [ ] Verify cache lookup uses same key format
- [ ] Verify cache storage uses same key format

### Testing

- [ ] Unit test: Same ticker/range on different days → different keys
- [ ] Unit test: Same ticker/range/day with different resolution → different keys
- [ ] Unit test: Custom range → includes both dates
- [ ] Integration test: Cached response not served across days

### Logging

- [ ] Log cache key on hit (already done, verify format)
- [ ] Log cache key on miss
- [ ] Log cache key on write

---

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/lambdas/dashboard/ohlc.py` | 68-98 | Update `_get_ohlc_cache_key()` |
| `tests/unit/dashboard/test_ohlc.py` | TBD | Add cache key unit tests |

---

## Risks

| Risk | Mitigation |
|------|------------|
| Cache invalidation on deploy | Acceptable - cache rebuilds naturally |
| Increased cache misses initially | Expected - correct behavior |
| Log injection via ticker | Already sanitized (line 340-344) |

---

## Verification Steps

After implementation:

```bash
# 1. Run unit tests
pytest tests/unit/dashboard/test_ohlc.py -v -k "cache_key"

# 2. Manual verification
# Request same ticker on different days, verify different cache keys in logs

# 3. Playwright test
# Run sanity.spec.ts, verify no stale data
```

---

## Related

- [fix-cache-writing.md](./fix-cache-writing.md) - Uses same key format for DDB
- [fix-cache-reading.md](./fix-cache-reading.md) - Uses same key format for lookup
