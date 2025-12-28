# Tasks: Persistent OHLC Cache

**Feature**: 1087-persistent-ohlc-cache
**Generated**: 2025-12-28
**Total Tasks**: 15

## Summary

| Phase | Description | Tasks | Parallel |
|-------|-------------|-------|----------|
| 1 | Setup | 2 | 0 |
| 2 | Foundational (Terraform) | 3 | 2 |
| 3 | User Story 1: Fast Historical Data | 4 | 2 |
| 4 | User Story 2: Efficient Range Queries | 3 | 1 |
| 5 | User Story 3: Write-Through Fresh Data | 2 | 0 |
| 6 | Polish & Testing | 1 | 0 |

---

## Phase 1: Setup

- [X] T001 Create cache module directory at `src/lambdas/shared/cache/` if not exists
- [X] T002 Create test directory at `tests/unit/shared/cache/` if not exists

---

## Phase 2: Foundational (Terraform Infrastructure)

**Goal**: Create DynamoDB table and IAM permissions before any Python implementation.

- [X] T003 [P] Add `ohlc-cache` DynamoDB table in `infrastructure/terraform/modules/dynamodb/main.tf`
  - Table name: `${var.environment}-ohlc-cache`
  - Billing: PAY_PER_REQUEST (on-demand)
  - PK: `PK` (S), SK: `SK` (S)
  - Enable PITR and encryption
  - Add tags with Feature = "1087-persistent-ohlc-cache"

- [X] T004 [P] Add table outputs in `infrastructure/terraform/modules/dynamodb/outputs.tf`
  - Output: `ohlc_cache_table_name`
  - Output: `ohlc_cache_table_arn`

- [X] T005 Add Dashboard Lambda IAM permissions in `infrastructure/terraform/modules/iam/main.tf`
  - Allow `dynamodb:Query`, `dynamodb:PutItem`, `dynamodb:BatchWriteItem`
  - Resource: `${var.environment}-ohlc-cache` table ARN
  - Add `OHLC_CACHE_TABLE` environment variable to Dashboard Lambda in `main.tf`

---

## Phase 3: User Story 1 - Fast Historical Data (P1)

**Goal**: Implement persistent cache lookup so repeat requests serve from DynamoDB in <100ms.

**Independent Test**: Request AAPL 1-month data, verify API called once. Request same data again, verify served from cache with no API call.

- [X] T006 [P] [US1] Create pydantic models in `src/lambdas/shared/cache/ohlc_cache.py`
  - `CachedCandle` model with timestamp, open, high, low, close, volume, source, resolution
  - `OHLCCacheQuery` model with ticker, source, resolution, start_time, end_time
  - `OHLCCacheResult` model with candles, cache_hit, missing_ranges

- [X] T007 [P] [US1] Implement `get_cached_candles()` in `src/lambdas/shared/cache/ohlc_cache.py`
  - Build PK from `{ticker}#{source}`
  - Build SK range from `{resolution}#{start_time}` to `{resolution}#{end_time}`
  - Query DynamoDB with BETWEEN on SK
  - Return `OHLCCacheResult` with cache_hit flag

- [X] T008 [US1] Implement `put_cached_candles()` in `src/lambdas/shared/cache/ohlc_cache.py`
  - Convert candles to DynamoDB items
  - Use `BatchWriteItem` for efficiency
  - Use conditional writes to skip duplicates
  - Return count of items written

- [ ] T009 [US1] Integrate cache in `src/lambdas/dashboard/ohlc.py`
  - After L1 cache miss, check L2 (DynamoDB) before adapters
  - On L2 hit: return data, populate L1
  - On L2 miss: fetch from adapter, write-through to L2, populate L1

---

## Phase 4: User Story 2 - Efficient Range Queries (P1)

**Goal**: Enable efficient pan/zoom with DynamoDB range queries returning <100 records in <100ms.

**Independent Test**: Load 1-month of 5m candles (~2000 records), query 2-hour range, verify only ~24 records returned with single DynamoDB Query operation.

- [X] T010 [P] [US2] Add `__init__.py` exports in `src/lambdas/shared/cache/__init__.py`
  - Export `get_cached_candles`, `put_cached_candles`, `CachedCandle`, `OHLCCacheResult`

- [X] T011 [US2] Add `ProjectionExpression` optimization to `get_cached_candles()`
  - Only retrieve: SK, open, high, low, close, volume
  - Skip metadata fields (fetched_at) for performance
  - Handle reserved words with ExpressionAttributeNames

- [X] T012 [US2] Add unit tests in `tests/unit/shared/cache/test_ohlc_persistent_cache.py`
  - Test cache miss returns empty result
  - Test cache hit returns candles
  - Test range query returns subset
  - Test write-through stores candles
  - Test duplicate writes are idempotent
  - Use moto for DynamoDB mocking

---

## Phase 5: User Story 3 - Write-Through Fresh Data (P2)

**Goal**: During market hours, current candle fetches fresh data and writes through to cache.

**Independent Test**: During market hours, request current 1m candle twice with 30s gap, verify second request shows updated close price.

- [X] T013 [US3] Implement `is_market_open()` in `src/lambdas/shared/cache/ohlc_cache.py`
  - NYSE hours: 9:30 AM - 4:00 PM Eastern
  - Weekdays only (Monday-Friday)
  - Return True if within trading hours

- [ ] T014 [US3] Add freshness logic in `src/lambdas/dashboard/ohlc.py`
  - If requesting current candle (within resolution window) AND market is open:
    - Always fetch fresh from API
    - Write-through to L2
  - Else: serve from cache

---

## Phase 6: Polish & Testing

- [X] T015 Run full test suite and verify all unit tests pass
  - `pytest tests/unit/shared/cache/test_ohlc_persistent_cache.py -v`
  - `pytest tests/unit/dashboard/test_ohlc.py -v`
  - Verify no regressions in existing tests

---

## Dependencies

```
T001 → T006, T007
T002 → T012
T003 → T005 → T009
T004 → T005
T006 → T007, T008
T007 → T009
T008 → T009
T009 → T010, T011
T013 → T014
T012, T014 → T015
```

## Parallel Execution

**Batch 1** (Infrastructure):
- T003 and T004 can run in parallel

**Batch 2** (Models):
- T006 and T007 can run in parallel after T003-T005

**Batch 3** (Integration):
- T010 can run in parallel with T011

## MVP Scope

**Minimum Viable**: Phases 1-3 (Setup + Foundational + US1)
- Creates table, cache module, basic lookup
- Demonstrates 90%+ API call reduction

**Full Feature**: All phases
- Adds range query optimization and market hours freshness

## Implementation Notes

**Completed 2025-12-28**:
- T009 (ohlc.py integration) and T014 (freshness logic) deferred to follow-up PR
- Core cache infrastructure and module complete
- 14/14 unit tests passing
- Terraform validated
