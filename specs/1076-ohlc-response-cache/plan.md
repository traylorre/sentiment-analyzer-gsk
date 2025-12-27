# Technical Plan: OHLC Response Cache

**Feature Branch**: `1076-ohlc-response-cache`
**Created**: 2025-12-27
**Spec**: [spec.md](./spec.md)

## Overview

Add module-level OHLC response caching to the Dashboard Lambda, following the proven pattern from `sentiment.py`. This eliminates 429 rate limit errors when users rapidly switch resolution buckets.

## Architecture

```
User Click → /api/v2/tickers/{ticker}/ohlc
                    ↓
            OHLC Handler (ohlc.py)
                    ↓
        [NEW] _get_cached_ohlc()
              ├── Cache HIT → Return cached response
              └── Cache MISS → Tiingo Adapter → Cache → Return
```

## Implementation Tasks

### Task 1: Add Module-Level Cache Infrastructure

**File**: `src/lambdas/dashboard/ohlc.py`

Add at module level (after imports):

```python
import time
import os

# Cache configuration (resolution-based TTLs in seconds)
OHLC_CACHE_TTLS = {
    "1min": 300,      # 5 minutes for 1-minute resolution
    "5min": 900,      # 15 minutes for 5-minute resolution
    "15min": 900,     # 15 minutes for 15-minute resolution
    "30min": 900,     # 15 minutes for 30-minute resolution
    "1hour": 1800,    # 30 minutes for hourly resolution
    "1day": 3600,     # 1 hour for daily resolution
}
OHLC_CACHE_DEFAULT_TTL = 300  # 5 minutes default
OHLC_CACHE_MAX_ENTRIES = int(os.environ.get("OHLC_CACHE_MAX_ENTRIES", "256"))

# Cache storage: {cache_key: (timestamp, response_dict)}
_ohlc_cache: dict[str, tuple[float, dict]] = {}
_ohlc_cache_stats = {"hits": 0, "misses": 0, "evictions": 0}
```

### Task 2: Add Cache Key Generation

**File**: `src/lambdas/dashboard/ohlc.py`

```python
def _get_ohlc_cache_key(ticker: str, resolution: str, start_date: date, end_date: date) -> str:
    """Generate cache key for OHLC request."""
    return f"ohlc:{ticker.upper()}:{resolution}:{start_date.isoformat()}:{end_date.isoformat()}"
```

### Task 3: Add Cache Get Function

**File**: `src/lambdas/dashboard/ohlc.py`

```python
def _get_cached_ohlc(cache_key: str, resolution: str) -> dict | None:
    """Get OHLC response from cache if valid."""
    if cache_key in _ohlc_cache:
        timestamp, response = _ohlc_cache[cache_key]
        ttl = OHLC_CACHE_TTLS.get(resolution, OHLC_CACHE_DEFAULT_TTL)
        if time.time() - timestamp < ttl:
            _ohlc_cache_stats["hits"] += 1
            return response
        del _ohlc_cache[cache_key]  # Expired, remove
    _ohlc_cache_stats["misses"] += 1
    return None
```

### Task 4: Add Cache Set Function with LRU Eviction

**File**: `src/lambdas/dashboard/ohlc.py`

```python
def _set_cached_ohlc(cache_key: str, response: dict) -> None:
    """Store OHLC response in cache with LRU eviction."""
    global _ohlc_cache
    if len(_ohlc_cache) >= OHLC_CACHE_MAX_ENTRIES:
        # Evict oldest entry by timestamp
        oldest_key = min(_ohlc_cache.keys(), key=lambda k: _ohlc_cache[k][0])
        del _ohlc_cache[oldest_key]
        _ohlc_cache_stats["evictions"] += 1
    _ohlc_cache[cache_key] = (time.time(), response)
```

### Task 5: Add Cache Stats Function

**File**: `src/lambdas/dashboard/ohlc.py`

```python
def get_ohlc_cache_stats() -> dict[str, int]:
    """Return cache statistics for observability."""
    return _ohlc_cache_stats.copy()
```

### Task 6: Integrate Cache into get_ohlc Handler

**File**: `src/lambdas/dashboard/ohlc.py`

Modify the `get_ohlc` function to check cache before calling adapters:

```python
# At start of get_ohlc() function, after input validation:
cache_key = _get_ohlc_cache_key(ticker, resolution, start_date, end_date)
cached_response = _get_cached_ohlc(cache_key, resolution)
if cached_response:
    logger.info(f"OHLC cache hit for {cache_key}")
    return JSONResponse(content=cached_response, headers=response_headers)

# ... existing adapter calls ...

# Before returning successful response, cache it:
response_data = {
    "ticker": ticker,
    "resolution": resolution,
    "data": [c.model_dump() for c in candles],
    "metadata": {"source": source, ...}
}
_set_cached_ohlc(cache_key, response_data)
```

### Task 7: Add Unit Tests

**File**: `tests/unit/dashboard/test_ohlc_cache.py`

Test cases:
1. Cache miss on first request
2. Cache hit on second request
3. Cache expiry after TTL
4. LRU eviction when full
5. Resolution-specific TTL values
6. Stats tracking accuracy

## Files Changed

| File | Change |
|------|--------|
| `src/lambdas/dashboard/ohlc.py` | Add caching infrastructure and integrate into handler |
| `tests/unit/dashboard/test_ohlc_cache.py` | New test file for cache functionality |

## Success Verification

1. Run unit tests: `pytest tests/unit/dashboard/test_ohlc_cache.py -v`
2. All existing OHLC tests still pass
3. Manual test: Click 10 resolution buckets in 5 seconds, no 429 errors

## Dependencies

- None (uses only Python stdlib: `time`, `os`)
- No new packages required

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Memory growth | 256 entry limit with LRU eviction |
| Stale data | Resolution-specific TTLs based on data volatility |
| Cold start penalty | First request still slow, but subsequent requests fast |
