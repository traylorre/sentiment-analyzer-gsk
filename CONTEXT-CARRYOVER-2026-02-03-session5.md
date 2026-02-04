# Context Carryover Document - 2026-02-03 Session 5

**Session Date:** 2026-02-03
**Repository:** traylorre/sentiment-analyzer-gsk
**Working Directory:** /home/zeebo/projects/sentiment-analyzer-gsk
**Branch:** B-chart-persistence-fixes

---

## Session Summary

This session conducted **3 rounds of /speckit.clarify** on the OHLC cache remediation spec, identifying and documenting **16 blind spots** with confirmed fixes for each. The principal engineer deep-dive approach uncovered critical bugs and architectural gaps.

### Commits Made This Session
```
5061ff1 spec(cache): Add clarifications for OHLC cache blind spots
0f75800 spec(cache): Add clarifications from rounds 2-3 (11 more blind spots)
```

---

## Clarifications Summary (15 Total)

### Round 1 (5 clarifications)
1. **Env var fallback** → Remove fallback, raise ValueError (fail-fast)
2. **Resolution format mismatch** → Use enum values as-is ("5", "60", "D"), fix docstring
3. **Cache miss vs error** → ERROR logging + CloudWatch metric + alarm (1hr mute)
4. **Async/sync blocking** → Wrap DynamoDB calls in `asyncio.to_thread()`
5. **Integration test** → Functional round-trip test (write → read)

### Round 2 (5 clarifications)
6. **Volume=None bug (Tiingo)** → Fix at adapter layer, return volume=0
7. **DynamoDB pagination** → Add warning log if LastEvaluatedKey present
8. **Estimate function math** → Fix `days * 5 / 7 * 7` to `days * 5 / 7 * 6.5`
9. **80% coverage threshold** → Remove, require 100% expected candles
10. **Three-layer cache** → Unified `invalidate_all_caches()` function

### Round 3 (5 clarifications)
11. **Unprocessed BatchWrite** → Retry with exponential backoff + CloudWatch metric
12. **DynamoDB client** → Singleton pattern + audit all cache clients
13. **Volume=None bug (Finnhub)** → Same fix as Tiingo
14. **Circuit breaker** → Skip DDB for 60s after 3 failures + alarm
15. **Production verification** → Post-deployment smoke test

---

## All Documented Blind Spots (11.1 - 11.16)

| # | Blind Spot | Fix Required |
|---|------------|--------------|
| 11.1 | Tests give false confidence | Functional round-trip test |
| 11.2 | Env var fallback masks misconfiguration | Remove fallback, raise ValueError |
| 11.3 | No observability for cache effectiveness | CloudWatch metrics (documented, not clarified) |
| 11.4 | Async/sync event loop blocking | `asyncio.to_thread()` wrapper |
| 11.5 | Timezone edge case: naive datetime | Warning log (documented, not clarified) |
| 11.6 | Resolution format mismatch | Fix docstring to match enum values |
| 11.7 | Graceful degradation = silent failure | ERROR logging + CloudWatch metric + alarm |
| 11.8 | DynamoDB pagination not handled | Warning log if LastEvaluatedKey present |
| 11.9 | Estimate function math error | Fix `* 7` to `* 6.5` |
| 11.10 | 80% threshold serves incomplete data | Require 100% coverage |
| 11.11 | Three-layer cache partial invalidation | Unified `invalidate_all_caches()` |
| 11.12 | Unprocessed BatchWriteItems silently lost | Retry with backoff + metric |
| 11.13 | DynamoDB client created fresh every call | Singleton pattern |
| 11.14 | Volume=None crashes cache write | Fix both Tiingo + Finnhub adapters |
| 11.15 | No production verification | Post-deployment smoke test |
| 11.16 | No circuit breaker for DynamoDB failures | Simple circuit breaker + alarm |

---

## Files to Modify (Implementation)

### High Priority (P0-P1)
| File | Changes |
|------|---------|
| `src/lambdas/shared/cache/ohlc_cache.py` | Singleton client, remove fallback, retry unprocessed, pagination warning, circuit breaker |
| `src/lambdas/dashboard/ohlc.py` | asyncio.to_thread wrappers, 100% threshold, estimate math fix |
| `src/lambdas/shared/adapters/tiingo.py` | volume=0 instead of None (line 446) |
| `src/lambdas/shared/adapters/finnhub.py` | volume=0 instead of None (line 378) |

### Medium Priority (P2-P3)
| File | Changes |
|------|---------|
| `src/lambdas/shared/cache/cache_manager.py` | NEW: unified invalidate_all_caches() |
| `scripts/smoke-test-cache.py` | NEW: post-deployment verification |
| `tests/integration/test_ohlc_cache_integration.py` | Functional round-trip test |

### Low Priority (P4)
| File | Changes |
|------|---------|
| Other cache clients | Audit and fix singleton pattern |

---

## User's High-Level Goal

From `/dev-loop` context:
> "get playwright tests working and ultimately to get customer-facing dashboard working"
> "get caching layer to work for writes and reads on all categories of data from external Tiingo and Finnhub"

### Key Principles (User Emphasized)
- **No shortcuts, no quick fixes** - dive deep for blind spots
- **No fallbacks as safe havens** - "either something exists or throw an error"
- **No backwards compatibility hacks** - clean implementations only
- **User gets latest data** - no "good enough" thresholds

---

## Next Steps

1. **Run `/speckit.plan`** to generate implementation plan from the comprehensive spec
2. **Or implement directly** - the spec is detailed enough with code examples
3. **Priority order:**
   - Fix volume=None bugs (Tiingo + Finnhub) - blocks all intraday caching
   - Add singleton client pattern
   - Remove env var fallback (fail-fast)
   - Add retry + circuit breaker
   - Change 80% → 100% threshold
   - Add asyncio.to_thread wrappers
   - Create unified invalidate function
   - Add smoke test

---

## Commands for Next Session

```bash
# Continue from this branch
cd /home/zeebo/projects/sentiment-analyzer-gsk
git checkout B-chart-persistence-fixes

# Read the comprehensive spec
cat .specify/specs/ohlc-cache-remediation.md

# Start implementation
/speckit.plan
# or
/speckit.implement
```

---

## Reference Documents

- `.specify/specs/ohlc-cache-remediation.md` - Full specification with 16 blind spots
- `docs/cache/HL-cache-remediation-checklist.md` - Original checklist
- `CONTEXT-CARRYOVER-2026-02-03-session4.md` - Previous session context
