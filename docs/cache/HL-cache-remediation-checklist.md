# High-Level Cache Remediation Checklist

**Created:** 2026-02-03
**Status:** In Progress
**Branch:** TBD (create from `B-chart-persistence-fixes`)

---

## Executive Summary

The OHLC caching infrastructure is **partially implemented but non-functional**:
- DynamoDB table exists (`{env}-ohlc-cache`)
- IAM permissions granted (Query, PutItem, BatchWriteItem)
- Cache functions defined (`get_cached_candles`, `put_cached_candles`)
- **BUT:** Functions are never called from the OHLC endpoint

This results in:
- Every Lambda cold start = redundant Tiingo API call
- Historical data lost across invocations
- Playwright tests flaky due to external API dependency
- ~$5-10/month wasted on unused DynamoDB table

---

## Work Order

| # | Task | File | Status | Priority | Code Location |
|---|------|------|--------|----------|---------------|
| 1 | Fix cache key design | [fix-cache-key.md](./fix-cache-key.md) | [x] DONE | P0 | `ohlc.py:75-109` (`_get_ohlc_cache_key` includes end_date) |
| 2 | Fix cache writing (write-through) | [fix-cache-writing.md](./fix-cache-writing.md) | [x] DONE | P1 | `ohlc.py:185-237` (`_write_through_to_dynamodb`, called at 717, 749, 792) |
| 3 | Fix cache reading (query DDB first) | [fix-cache-reading.md](./fix-cache-reading.md) | [x] DONE | P2 | `ohlc.py:239-314` (`_read_from_dynamodb`, called at 650) |
| 4 | Local API table setup | [fix-local-api-tables.md](./fix-local-api-tables.md) | [x] DONE | P3 | `run-local-api.py:79,132` |
| 5 | Add tests | [fix-cache-tests.md](./fix-cache-tests.md) | [x] DONE | P4 | `tests/unit/shared/cache/test_ohlc_persistent_cache.py` (16 tests), `tests/unit/dashboard/test_ohlc.py` (33 tests) |

**Rationale for order:**
1. **Key first** - If cache key is wrong, reads/writes will miss even after fix
2. **Write second** - Populate DDB so reads have data to find
3. **Read third** - Query DDB before Tiingo
4. **Local API fourth** - Enables local testing of above fixes
5. **Tests last** - Verify all fixes work together

---

## Data Categories Affected

| Category | In-Memory | DynamoDB | Current State | After Fix |
|----------|-----------|----------|---------------|-----------|
| News | ✓ 30min | ❌ None | Working | No change |
| Daily OHLC | ✓ 1hr | ✓ Exists | **BROKEN** | Cache → DDB → Tiingo |
| Intraday OHLC | ✓ 5min | ✓ Exists | **BROKEN** | Cache → DDB → Tiingo |
| Ticker | ✓ LRU | ❌ S3 only | Working | No change |

---

## Expected Data Flow (After Fix)

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

## Files to Modify

### Primary Changes
| File | Change |
|------|--------|
| `src/lambdas/dashboard/ohlc.py` | Add DDB read/write calls |
| `src/lambdas/shared/cache/ohlc_cache.py` | May need helper functions |
| `src/lambdas/shared/models/ohlc.py` | Add `PriceCandle.from_cached()` |
| `scripts/run-local-api.py` | Add `local-ohlc-cache` table |

### Test Files
| File | Change |
|------|--------|
| `tests/unit/dashboard/test_ohlc.py` | Mock DDB cache calls |
| `tests/unit/shared/cache/test_ohlc_cache.py` | May exist, verify coverage |
| `tests/integration/test_ohlc_cache.py` | New: end-to-end cache test |

---

## Blind Spots Identified

### Already Documented
1. DynamoDB cache never queried before Tiingo
2. Write-through never implemented
3. Local API missing OHLC table
4. Cache key ignores actual dates for predefined ranges

### Additional Considerations
5. **`PriceCandle.from_cached()` doesn't exist** - Need to create converter
6. **Resolution format consistency** - Verify "D", "1", "5" match across layers
7. **Timezone handling** - Cache expects UTC, ensure all timestamps are UTC
8. **Partial cache hits** - What if DDB has 20 of 30 requested days?
9. **Error handling** - DDB query failure should fall through to Tiingo (not 500)
10. **Cache TTL for intraday** - Today's intraday data changes; yesterday's doesn't
11. **Environment variable `OHLC_CACHE_TABLE`** - Must be set in local API
12. **Metrics/observability** - Add CloudWatch metrics for cache hit/miss rates

### Deep-Dive Considerations (Principal Engineer Level)
13. **Circular import risk** - Importing `ohlc_cache` in `ohlc.py` may cause issues; verify import order
14. **Async/sync mismatch** - `get_cached_candles()` is sync, endpoint is async; may block event loop
15. **Cold start latency budget** - DDB query adds ~20ms; acceptable vs 500ms+ Tiingo call
16. **Error response caching** - Should NOT cache 404s (ticker may become valid later)
17. **Cache warming strategy** - Consider pre-populating cache for popular tickers (AAPL, MSFT, GOOG)
18. **Intraday data freshness** - Today's data changes; yesterday's is immutable
19. **Weekend/holiday handling** - No trading data; cache should still hit for last trading day
20. **Rate limit protection** - DDB cache prevents Tiingo 429 on high traffic
21. **Data consistency** - Same candle from cache vs API should be byte-identical

---

## Success Criteria

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

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Cache key mismatch | Medium | High | Thorough testing, log cache keys |
| DDB throttling | Low | Medium | On-demand billing mode, backoff |
| Stale data served | Medium | Low | Document TTL, market hours logic |
| Timezone bugs | Medium | High | All timestamps UTC, unit tests |

---

## References

- Feature 1087: OHLC Persistent Cache (original spec)
- Feature 1076/1078: Response cache improvements
- `src/lambdas/shared/cache/ohlc_cache.py` - Existing (unused) cache module
- `infrastructure/terraform/modules/dynamodb/main.tf:521-564` - Table definition

---

## Progress Log

| Date | Update |
|------|--------|
| 2026-02-03 | Document created from audit findings |
