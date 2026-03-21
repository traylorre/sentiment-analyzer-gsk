# Tasks: Fix Sentiment Overview & History Endpoints

**Input**: Design documents from `/specs/1229-fix-sentiment-overview/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included per constitution requirement (Amendment 1.1: all implementation code must be accompanied by unit tests).

**Organization**: Tasks grouped by user story. US1 and US2 are both P1 but can be implemented in parallel (different functions in the same file).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Foundational — Resolution Alignment (BLOCKS ALL)

**Purpose**: Change Resolution enum from 8→6 values aligned 1:1 with OHLC, then fix all hardcoded references. Every subsequent task depends on this phase.

- [x] T001 Update Resolution enum in `src/lib/timeseries/models.py`: remove `TEN_MINUTES="10m"`, `THREE_HOURS="3h"`, `SIX_HOURS="6h"`, `TWELVE_HOURS="12h"`; add `FIFTEEN_MINUTES="15m"` (duration=900, ttl=24h), `THIRTY_MINUTES="30m"` (duration=1800, ttl=3 days); update `duration_seconds` and `ttl_seconds` property mappings
- [x] T002 [P] Update `valid_resolutions` set in `src/lambdas/sse_streaming/handler.py:215` — replace hardcoded set with `{r.value for r in Resolution}` to derive from enum
- [x] T003 [P] Update error messages in `src/lambdas/dashboard/router_v2.py:1551,1621` — derive valid resolution list from `Resolution` enum instead of hardcoded string
- [x] T004 [P] Update `DEFAULT_LIMITS` dict in `src/lambdas/dashboard/timeseries.py:227-236` — remove 10m/3h/6h/12h entries, add `FIFTEEN_MINUTES: 4` and `THIRTY_MINUTES: 48` entries
- [x] T005 [P] Update `RESOLUTION_ORDER` list in `src/lib/timeseries/preload.py:24-33` — rebuild with 6 new enum values in ascending order, verify adjacency logic still works
- [x] T006 [P] Update docstring in `src/lib/timeseries/fanout.py:10` — change "8 resolution buckets" to "6 resolution buckets" and update resolution list in comment
- [x] T007 [P] Update `src/dashboard/config.js` — three changes in one file: (1) `RESOLUTIONS` (lines 68-117): remove 10m/3h/6h/12h entries, add 15m (`displayName: "15 min"`, duration=900, ttl=86400) and 30m (`displayName: "30 min"`, duration=1800, ttl=259200); (2) `RESOLUTION_ORDER` (line 120): set to `['1m', '5m', '15m', '30m', '1h', '24h']`; (3) `UNIFIED_RESOLUTIONS` (lines 194-205): replace entire array with 6 entries where each has `exact: true` (all 1:1 now): 1m↔1, 5m↔5, 15m↔15, 30m↔30, 1h↔60, 24h↔D
- [x] T008 [P] Update resolution list in `README.md:416` — change "8 timeseries buckets (1m, 5m, 10m, 1h, 3h, 6h, 12h, 24h)" to "6 timeseries buckets (1m, 5m, 15m, 30m, 1h, 24h)"

**Checkpoint**: Resolution enum changed, all hardcoded references updated. Run `make test-local` — expect failures only in resolution-specific test assertions (fixed in Phase 2).

---

## Phase 2: Foundational — Fix Broken Tests

**Purpose**: Update existing tests that reference removed resolutions. Must complete before user story implementation to maintain green test suite.

- [x] T009 [P] Update `tests/unit/test_preload_strategy.py` — remove assertions referencing `Resolution.TEN_MINUTES`, `THREE_HOURS`, `SIX_HOURS`, `TWELVE_HOURS`; update hardcoded lists to 6 resolutions; fix adjacency tests for new ordering
- [x] T010 [P] Update `tests/unit/test_sse_resolution_filter.py:181-184` — remove loop over removed enum values; add test cases for `FIFTEEN_MINUTES` and `THIRTY_MINUTES`
- [x] T011 [P] Update `tests/unit/test_resolution_cache.py:149-153` — replace removed resolution TTL entries with `FIFTEEN_MINUTES: 900` and `THIRTY_MINUTES: 1800`
- [x] T012 [P] Update `tests/unit/test_timeseries_key_design.py:76` — change hardcoded resolution list to `["1m", "5m", "15m", "30m", "1h", "24h"]`
- [x] T013 [P] Update `tests/unit/test_timeseries_bucket.py:39-52` — remove alignment test cases for 10m/3h/6h/12h; add alignment tests for 15m (900s boundary) and 30m (1800s boundary)
- [x] T014 [P] Update `tests/unit/dashboard/test_config_resolution.py:52,85,102-106` — update expected resolution set to 6 values, update expected display names for 15m/30m

**Checkpoint**: `make test-local` passes with all existing tests green. Foundation ready for user story work.

---

## Phase 3: User Story 1 — Sentiment Overview Shows Real Data (Priority: P1) 🎯 MVP

**Goal**: The overview endpoint at `/api/v2/configurations/{id}/sentiment` returns real aggregated sentiment data from the timeseries table instead of empty `sentiment:{}`.

**Independent Test**: Call overview endpoint for a configuration with tickers that have timeseries data → response contains non-empty sentiment scores per ticker.

### Implementation for User Story 1

- [x] T015 [US1] Rewrite `get_sentiment_by_configuration()` in `src/lambdas/dashboard/sentiment.py:249-371` — remove `tiingo_adapter`/`finnhub_adapter` params; add `resolution` param (default `Resolution.TWENTY_FOUR_HOURS`); for each ticker call `query_timeseries(ticker, resolution)` with no start/end (fetches latest bucket at resolution); transform `SentimentBucketResponse` → `SourceSentiment` (bucket.avg→score, score_to_label→label, confidence=0.8, bucket.timestamp→updated_at); use key `"aggregated"` in sentiment dict; preserve existing cache mechanism; update cache key to include resolution; wrap `query_timeseries` calls in try/except and return `ErrorResponse(code="DB_ERROR", message="Database error")` on failure (matching existing pattern at line 649)
- [x] T016 [US1] Remove dead helper functions from `src/lambdas/dashboard/sentiment.py` — delete `_get_tiingo_sentiment()`, `_get_finnhub_sentiment()`, `_compute_our_model_sentiment()` (confirmed safe: only called within the rewritten function, never imported externally)
- [x] T017 [US1] Update overview route in `src/lambdas/dashboard/router_v2.py:1144-1163` — extract `resolution` query param from request, validate against `Resolution` enum values, pass to `get_sentiment_by_configuration()`; return 400 for invalid resolution
- [x] T018 [US1] Write unit tests in `tests/unit/test_sentiment_overview.py` — test cases: (1) overview with 2 tickers both having timeseries data returns non-empty sentiment, (2) one ticker with data + one without returns data for first and empty sentiment for second (graceful degradation), (3) aggregated score computed from bucket.avg, (4) resolution parameter passed correctly, (5) cache hit returns cached response with `cache_status: "fresh"`, (6) invalid resolution returns 400. Use moto mock for DynamoDB, mock `query_timeseries`, fixed date `2024-01-02`
- [x] T019 [US1] Update `tests/unit/dashboard/test_sentiment.py:81,98,116,130` — remove/rewrite 4 adapter parameter tests that test dead tiingo_adapter/finnhub_adapter flow; replace with tests verifying the new timeseries-based implementation

**Checkpoint**: Overview endpoint returns real data. Run `make test-local` — all tests green.

---

## Phase 4: User Story 2 — Ticker Sentiment History Shows Real Time Series (Priority: P1)

**Goal**: The history endpoint at `/api/v2/configurations/{id}/sentiment/{ticker}/history` returns real time-series data from the timeseries table instead of hardcoded stub values.

**Independent Test**: Call history endpoint for a ticker with 7 days of timeseries data → response contains real daily data points with varying scores.

### Implementation for User Story 2

- [x] T020 [US2] Rewrite `get_ticker_sentiment_history()` in `src/lambdas/dashboard/sentiment.py:608-691` — remove hardcoded mock data generation; add `resolution` param (default `Resolution.TWENTY_FOUR_HOURS`); call `query_timeseries(ticker, resolution, start_dt, end_dt)` where start_dt = now - days; transform each bucket to `TickerSentimentData` entry; apply source filtering if `source` param provided (filter `bucket.sources` by prefix match); return only buckets with data (no padding); wrap in try/except returning `ErrorResponse(code="DB_ERROR", message="Database error")` on failure
- [x] T021 [US2] Update history route in `src/lambdas/dashboard/router_v2.py:1278-1311` — extract `resolution` query param, validate against `Resolution` enum, pass to `get_ticker_sentiment_history()` along with existing `days` and `source` params
- [x] T022 [US2] Write unit tests in `tests/unit/test_sentiment_history.py` — test cases: (1) 7-day history returns real daily buckets, (2) source=tiingo filters to tiingo-only buckets, (3) ticker with only 3 days returns 3 entries (no padding), (4) ticker with no data returns empty history, (5) resolution parameter works (5m returns 5m buckets), (6) days parameter bounds query window correctly, (7) invalid source returns 400. Use moto mock, mock `query_timeseries`, fixed date `2024-01-02`

**Checkpoint**: History endpoint returns real time-series. Both US1 and US2 independently functional.

---

## Phase 5: User Story 3 — Sentiment Cache Serves Fresh Data (Priority: P2)

**Goal**: The existing cache mechanism continues to work, now caching real aggregated sentiment data instead of empty results.

**Independent Test**: Make two consecutive overview requests within 5-minute TTL → second returns `cache_status: "fresh"` with identical data.

### Implementation for User Story 3

- [x] T023 [US3] Update cache key generation in `src/lambdas/dashboard/sentiment.py` — the existing `_get_sentiment_cache_key(config_id, tickers)` must now also include `resolution` in the key (otherwise 24h and 1h requests for the same config return the same cached response); verify `_get_cached_sentiment()` and `_set_cached_sentiment()` serialize/deserialize `SentimentResponse` with real data correctly; verify TTL unchanged at `SENTIMENT_CACHE_TTL`
- [x] T024 [US3] Write cache-specific unit tests in `tests/unit/test_sentiment_overview.py` (append to existing) — test cases: (1) first request populates cache and returns `cache_status: "fresh"`, (2) second request within TTL returns cached response without calling `query_timeseries`, (3) request after TTL expiry fetches fresh data, (4) different resolution produces different cache key (24h vs 1h are separate cache entries). Use `freezegun` for time control, fixed date `2024-01-02`

**Checkpoint**: Cache works with real data. All 3 user stories independently verified.

---

## Phase 6: Frontend Updates

**Purpose**: Update frontend types and components to render aggregated sentiment data. The existing per-source access (tiingo/finnhub/ourModel) was always dead code (returned empty) — this makes the heatmap functional for the first time.

- [x] T025 [P] Update `frontend/src/types/sentiment.ts` — change `TickerSentiment.sentiment` type from per-source interface (`tiingo: SentimentScore; finnhub: SentimentScore; ourModel: SentimentScore`) to `Record<string, SentimentScore>` (or explicit `{ aggregated: SentimentScore }`) to match new backend contract
- [x] T026 [P] Update `frontend/src/components/heatmap/heat-map-view.tsx:38,43,48,57-60` — remove hardcoded `ticker.sentiment.tiingo`, `ticker.sentiment.finnhub`, `ticker.sentiment.ourModel` access; render from `ticker.sentiment.aggregated` or iterate `Object.entries(ticker.sentiment)` for future extensibility

**Checkpoint**: Frontend renders real sentiment data from the aggregated key. Dashboard shows sentiment for the first time.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, final cleanup, validation

- [x] T027 Write integration tests in `tests/integration/test_sentiment_endpoints.py` — end-to-end tests against LocalStack: (1) create config with tickers, populate timeseries buckets in DynamoDB, call overview → verify real data, (2) call history with days/source params → verify correct filtering, (3) verify graceful degradation for missing tickers, (4) performance: call overview with 20-ticker config, assert response completes within 2 seconds (SC-004). Use synthetic data per constitution requirement
- [x] T028 Run `make validate` — verify all linting, formatting, security checks pass
- [x] T029 Run `make test-local` — verify all unit + integration tests pass (target: 0 failures)
- [ ] T030 Manual verification: call preprod overview endpoint and confirm non-empty sentiment data for configured tickers

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Foundational — Resolution Alignment
    ↓ (BLOCKS ALL)
Phase 2: Foundational — Fix Broken Tests
    ↓ (BLOCKS ALL user stories)
Phase 3: US1 — Overview  ←→  Phase 4: US2 — History  (PARALLEL — different functions)
    ↓                              ↓
Phase 5: US3 — Cache (depends on US1 overview function)
    ↓
Phase 6: Frontend (depends on backend contract being stable)
    ↓
Phase 7: Polish
```

### User Story Dependencies

- **US1 (Overview)**: Depends on Phase 1+2. No dependency on US2 or US3.
- **US2 (History)**: Depends on Phase 1+2. No dependency on US1 or US3.
- **US3 (Cache)**: Depends on US1 (cache wraps the overview function).
- **Frontend**: Depends on US1+US2 (backend contract must be stable before updating frontend types).

### Within Each Phase

- Tasks marked [P] can run in parallel
- Tasks without [P] must run sequentially in listed order
- Tests accompany their implementation (same phase)

### Parallel Opportunities

**Phase 1** (after T001): T002-T008 are all [P] — different files, can run simultaneously
**Phase 2**: T009-T014 are all [P] — different test files, can run simultaneously
**Phase 3 + Phase 4**: Can start simultaneously after Phase 2 (different functions in sentiment.py — coordinate to avoid merge conflicts)
**Phase 6**: T025 and T026 are [P] — different frontend files

---

## Parallel Example: Foundation Phase

```
# After T001 (enum change) completes, launch all blast radius fixes in parallel:
T002: SSE handler valid_resolutions → src/lambdas/sse_streaming/handler.py
T003: Router error messages → src/lambdas/dashboard/router_v2.py
T004: DEFAULT_LIMITS → src/lambdas/dashboard/timeseries.py
T005: RESOLUTION_ORDER → src/lib/timeseries/preload.py
T006: Fanout docstring → src/lib/timeseries/fanout.py
T007: Frontend config.js (RESOLUTIONS + RESOLUTION_ORDER + UNIFIED_RESOLUTIONS)
T008: README → README.md
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Resolution alignment (T001-T008)
2. Complete Phase 2: Fix broken tests (T009-T014)
3. Complete Phase 3: US1 Overview endpoint (T015-T019)
4. **STOP and VALIDATE**: Overview returns real data, all tests green
5. Deploy — users see real sentiment scores for the first time

### Full Delivery

1. Complete Foundation (Phase 1+2) → 14 tasks
2. US1 Overview + US2 History in parallel → 8 tasks
3. US3 Cache verification → 2 tasks
4. Frontend updates → 2 tasks
5. Polish → 4 tasks
6. **Total: 30 tasks**

---

## Notes

- The Resolution enum change (T001) is the single most impactful task — everything depends on it
- Dead code removal (T016) is safe per adversarial review: functions only called from rewritten function
- Frontend changes (Phase 6) make the heatmap work for the first time — existing per-source access was always dead code
- Cache (US3) is mostly "verify it still works" — the mechanism is already implemented, just cached empty data before
