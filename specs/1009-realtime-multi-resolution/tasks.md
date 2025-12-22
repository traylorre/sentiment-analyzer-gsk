# Tasks: Real-Time Multi-Resolution Sentiment Time-Series

**Input**: Design documents from `/specs/1009-realtime-multi-resolution/`
**Prerequisites**: plan.md, spec.md (TDD mandatory), data-model.md, contracts/, research.md, quickstart.md

**TDD MANDATORY**: All tests MUST be implemented BEFORE production code per spec.md TDD Test Design section.

**Organization**: Tasks grouped by user story with TDD test-first approach. Canonical source citations required for all design decisions.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1-US5)
- Include exact file paths and canonical source references

---

## Phase 1: Setup (Infrastructure Foundation)

**Purpose**: DynamoDB table creation and Terraform configuration

- [X] T001 Create timeseries table in `infrastructure/terraform/modules/dynamodb/main.tf` with PK `{ticker}#{resolution}` and SK bucket timestamp per `[CS-002]`
- [X] T002 [P] Add timeseries table variables to `infrastructure/terraform/modules/dynamodb/variables.tf`
- [X] T003 [P] Add timeseries table outputs to `infrastructure/terraform/modules/dynamodb/outputs.tf`
- [X] T004 Wire timeseries table to Lambda environment variables in `infrastructure/terraform/main.tf`
- [X] T005 [P] Add timeseries table IAM permissions to `infrastructure/terraform/modules/iam/main.tf`

**Checkpoint**: Run `terraform validate` and `terraform plan` to verify infrastructure changes

---

## Phase 2: Foundational (Shared Library - TDD)

**Purpose**: Core time-series library that ALL user stories depend on

**⚠️ CRITICAL**: Write ALL tests FIRST, ensure they FAIL, then implement

### Tests for Foundation (MUST FAIL initially)

- [X] T006 [P] Implement `tests/unit/test_timeseries_bucket.py` with TestBucketAlignment (20+ parametrized cases) per `[CS-009, CS-010]`
- [X] T007 [P] Implement `tests/unit/test_bucket_progress.py` with TestPartialBucketProgress per `[CS-011]`
- [X] T008 [P] Implement `tests/unit/test_timeseries_aggregation.py` with TestOHLCAggregation per `[CS-011, CS-012]`
- [X] T009 [P] Implement `tests/unit/test_timeseries_key_design.py` with TestTimeseriesKeyDesign per `[CS-002, CS-004]`

**Checkpoint**: Run `pytest tests/unit/test_timeseries*.py` - ALL tests MUST FAIL

### Implementation for Foundation

- [X] T010 Create `src/lib/timeseries/__init__.py` with module exports
- [X] T011 Implement Resolution enum in `src/lib/timeseries/models.py` with duration_seconds property
- [X] T012 Implement TimeseriesKey model in `src/lib/timeseries/models.py` with pk/sk properties per `[CS-002]`
- [X] T013 Implement SentimentBucket and PartialBucket models in `src/lib/timeseries/models.py` per `[CS-011]`
- [X] T014 Implement floor_to_bucket() in `src/lib/timeseries/bucket.py` for all 8 resolutions per `[CS-009, CS-010]`
- [X] T015 Implement calculate_bucket_progress() in `src/lib/timeseries/bucket.py` per `[CS-011]`
- [X] T016 Implement aggregate_ohlc() in `src/lib/timeseries/aggregation.py` per `[CS-011, CS-012]`

**Checkpoint**: Run `pytest tests/unit/test_timeseries*.py` - ALL tests MUST PASS

---

## Phase 3: User Story 1 - View Live Sentiment Updates (Priority: P1) 🎯 MVP

**Goal**: Stream sentiment updates within 3 seconds, show partial bucket progress, auto-reconnect

**Independent Test**: Watch dashboard for 60 seconds, verify automatic updates on new data

**Canonical Sources**: `[CS-001, CS-003, CS-007]`

### Tests for User Story 1 (MUST FAIL initially)

- [X] T017 [P] [US1] Implement `tests/unit/test_timeseries_fanout.py` with TestWriteFanout per `[CS-001, CS-003]`
- [X] T018 [P] [US1] Implement `tests/unit/test_sse_resolution_filter.py` with TestSSEResolutionFilter per `[CS-007]`

**Checkpoint**: Run `pytest tests/unit/test_*fanout*.py tests/unit/test_sse*.py` - ALL tests MUST FAIL

### Implementation for User Story 1

- [X] T019 [US1] Implement generate_fanout_items() in `src/lambdas/ingestion/timeseries_fanout.py` per `[CS-001]`
- [X] T020 [US1] Implement write_fanout() with BatchWriteItem in `src/lambdas/ingestion/timeseries_fanout.py` per `[CS-003]`
- [X] T021 [US1] Implement resolution-dependent TTL calculation in `src/lambdas/ingestion/timeseries_fanout.py` per `[CS-013, CS-014]`
- [X] T022 [US1] Modify `src/lambdas/analysis/handler.py` to call write_fanout() after sentiment analysis (NOTE: Analysis Lambda has sentiment results, not Ingestion)
- [X] T023 [US1] Implement SSEConnection model with subscribed_resolutions in `src/lambdas/sse_streaming/timeseries_models.py`
- [X] T024 [US1] Implement BucketUpdateEvent and PartialBucketEvent in `src/lambdas/sse_streaming/timeseries_models.py`
- [X] T025 [US1] Implement should_send_event() in `src/lambdas/sse_streaming/resolution_filter.py` per `[CS-007]`
- [X] T026 [US1] Add resolutions query parameter to /api/v2/stream endpoint in `src/lambdas/sse_streaming/handler.py`
- [x] T027 [US1] Implement partial bucket streaming with progress_pct in `src/lambdas/sse_streaming/stream.py`
- [x] T028 [US1] Add 100ms debounce to multi-resolution updates in `src/lambdas/sse_streaming/stream.py`

**Checkpoint**: Run full test suite - fanout and SSE tests MUST PASS. Manual test: trigger ingestion, observe SSE events.

---

## Phase 4: User Story 2 - Switch Resolution Levels Instantly (Priority: P1)

**Goal**: Resolution switching in <100ms, client-side cache for instant response

**Independent Test**: Switch from 1m to 1h resolution, measure delay <100ms

**Canonical Sources**: `[CS-005, CS-006, CS-008]`

### Tests for User Story 2 (MUST FAIL initially)

- [X] T029 [P] [US2] Implement `tests/unit/test_resolution_cache.py` with TestResolutionAwareCache per `[CS-005, CS-006]`
- [X] T030 [P] [US2] Implement `tests/unit/test_timeseries_query.py` with TestTimeseriesQuery for dashboard Lambda

**Checkpoint**: Run `pytest tests/unit/test_resolution_cache.py tests/unit/test_timeseries_query.py` - ALL tests MUST FAIL

### Implementation for User Story 2

- [X] T031 [US2] Implement ResolutionCache class in `src/lambdas/sse_streaming/cache.py` with resolution-aware TTL per `[CS-005, CS-006]`
- [X] T032 [US2] Implement cache stats tracking (hits/misses/hit_rate) in `src/lambdas/sse_streaming/cache.py`
- [X] T033 [US2] Implement LRU eviction with max_entries in `src/lambdas/sse_streaming/cache.py`
- [X] T034 [US2] Implement timeseries query service in `src/lambdas/dashboard/timeseries.py`
- [X] T035 [US2] Add GET /api/v2/timeseries/{ticker} endpoint in `src/lambdas/dashboard/router_v2.py` (NOTE: router_v2.py, not api_v2.py)
- [X] T036 [US2] Implement cache integration for timeseries queries in `src/lambdas/dashboard/timeseries.py`
- [X] T037 [US2] Create client-side IndexedDB cache in `src/dashboard/cache.js` per `[CS-008]`
- [X] T038 [US2] Implement resolution selector UI component in `src/dashboard/timeseries.js` (NOTE: timeseries.js, not app.js - timeseries module handles all resolution logic)
- [X] T039 [US2] Implement instant switching with IndexedDB lookup in `src/dashboard/timeseries.js`

**Checkpoint**: Resolution switching tests PASS. Manual test: switch resolutions, verify <100ms response.

---

## Phase 5: User Story 3 - View Historical Sentiment Trends (Priority: P2)

**Goal**: Smooth historical scrolling with seamless preloading

**Independent Test**: Scroll back 24 hours of 1-minute data, no loading interruptions

**Canonical Sources**: `[CS-001, CS-008]`

### Tests for User Story 3

- [X] T040 [P] [US3] Implement `tests/unit/test_timeseries_pagination.py` for historical data queries (9 tests)
- [X] T041 [P] [US3] Implement `tests/unit/test_preload_strategy.py` for adjacent time range preloading (13 tests)

**Checkpoint**: Pagination and preload tests PASS (22 tests total)

### Implementation for User Story 3

- [X] T042 [US3] Add limit/cursor query parameters to /api/v2/timeseries/{ticker} in `src/lambdas/dashboard/router_v2.py` (NOTE: router_v2.py, not api_v2.py)
- [X] T043 [US3] Implement pagination with DynamoDB Query in `src/lambdas/dashboard/timeseries.py` (limit, cursor, next_cursor, has_more)
- [X] T044 [US3] Implement `src/lib/timeseries/preload.py` with get_adjacent_time_ranges() per `[CS-008]`
- [X] T045 [US3] Implement get_adjacent_resolutions() (±1 level) in `src/lib/timeseries/preload.py`
- [X] T046 [US3] Implement PreloadManager with bandwidth limits and priorities in `src/lib/timeseries/preload.py`
- [X] T047 [US3] Implement should_preload() cache-check utility in `src/lib/timeseries/preload.py`

**Checkpoint**: Historical scrolling works smoothly with preloading. Tests PASS (22 tests).

---

## Phase 6: User Story 4 - Compare Multiple Tickers (Priority: P2)

**Goal**: Multi-ticker view with 10 tickers loading in <1 second, independent updates

**Independent Test**: Load 5 tickers, verify all update simultaneously in real-time

**Canonical Sources**: `[CS-002, CS-006]`

### Tests for User Story 4

- [x] T048 [P] [US4] Implement `tests/unit/test_multi_ticker_query.py` for batch ticker queries
- [x] T049 [P] [US4] Implement `tests/unit/test_shared_cache.py` for cross-user cache sharing

**Checkpoint**: Multi-ticker tests MUST FAIL initially

### Implementation for User Story 4

- [x] T050 [US4] Implement batch query for multiple tickers in `src/lambdas/dashboard/timeseries.py`
- [x] T051 [US4] Add tickers query parameter to /api/v2/stream in `src/lambdas/sse_streaming/handler.py`
- [x] T052 [US4] Implement multi-ticker chart layout in `src/dashboard/app.js`
- [x] T053 [US4] Implement per-ticker independent updates in `src/dashboard/timeseries.js`
- [x] T054 [US4] Implement shared cache across users for same ticker+resolution in `src/lambdas/sse_streaming/cache.py` per `[CS-006]`

**Checkpoint**: Multi-ticker view loads in <1 second. Tests PASS.

---

## Phase 7: User Story 5 - Connectivity Resilience (Priority: P3)

**Goal**: Dashboard functional during network issues, automatic reconnection

**Independent Test**: Simulate disconnect, verify cached data accessible, auto-reconnect in <5s

**Canonical Sources**: `[CS-007, CS-008]`

### Tests for User Story 5

- [X] T055 [P] [US5] Implement `tests/e2e/test_client_cache.py` with TestClientSideCache (Playwright) per `[CS-008]`
- [X] T056 [P] [US5] Implement `tests/e2e/test_sse_reconnection.py` for auto-reconnection behavior

**Checkpoint**: E2E tests implemented with TDD structure

### Implementation for User Story 5

- [X] T057 [US5] Implement SSE auto-reconnection with exponential backoff in `src/dashboard/app.js` per `[CS-007]`
- [X] T058 [US5] Implement fallback polling when SSE unavailable in `src/dashboard/app.js`
- [X] T059 [US5] Implement offline mode with IndexedDB cache access in `src/dashboard/cache.js`
- [X] T060 [US5] Add degraded mode indicator (subtle badge) in `src/dashboard/app.js`
- [X] T061 [US5] Implement cache version validation and invalidation in `src/dashboard/cache.js`

**Checkpoint**: Disconnect/reconnect works smoothly. E2E tests PASS.

---

## Phase 8: Integration & Polish

**Purpose**: End-to-end integration, performance validation, documentation

### Integration Tests

- [ ] T062 [P] Implement `tests/integration/test_timeseries_pipeline.py` with LocalStack per `[CS-001]`
- [ ] T063 [P] Implement `tests/e2e/test_multi_resolution_dashboard.py` for full user journey

**Checkpoint**: Integration tests PASS

### Performance Validation

- [ ] T064 Validate <100ms resolution switching (SC-002) with timing metrics
- [ ] T065 Validate <3s live update latency (SC-003) with CloudWatch metrics
- [ ] T066 Validate 80% cache hit rate (SC-008) with cache stats logging
- [ ] T067 Validate $60/month budget (SC-010) with `make cost` analysis

### Documentation & Cleanup

- [ ] T068 [P] Update `src/dashboard/config.js` with resolution endpoints
- [ ] T069 [P] Add skeleton loading UI components in `src/dashboard/app.js` (FR-011)
- [ ] T070 [P] Run `make validate` and fix any issues
- [ ] T071 Run quickstart.md validation per spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 - MVP core functionality
- **US2 (Phase 4)**: Depends on Phase 2 - can run parallel to US1
- **US3 (Phase 5)**: Depends on US2 (shares cache infrastructure)
- **US4 (Phase 6)**: Depends on US1 (shares SSE infrastructure)
- **US5 (Phase 7)**: Depends on US2 (shares cache infrastructure)
- **Integration (Phase 8)**: Depends on all user stories

### Within Each Phase

1. Tests FIRST - write, verify they FAIL
2. Implementation - make tests PASS
3. Checkpoint - validate before proceeding

### Parallel Opportunities

**Phase 2 (Foundation)**:
```
T006, T007, T008, T009 can run in parallel (different test files)
```

**Phase 3 (US1)**:
```
T017, T018 can run in parallel (fanout vs SSE tests)
```

**Phase 4 (US2)**:
```
T029, T030 can run in parallel (cache vs query tests)
```

**Across Phases**:
```
After Phase 2 complete:
- US1 and US2 can run in parallel (different Lambda components)
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup (Terraform)
2. Complete Phase 2: Foundation (models, bucket, aggregation)
3. Complete Phase 3: US1 (live updates via SSE)
4. Complete Phase 4: US2 (instant resolution switching)
5. **STOP and VALIDATE**: Dashboard shows live updates + fast switching
6. Deploy/demo MVP

### Incremental Delivery

1. Foundation → Test core time-series logic
2. +US1 → Live streaming works → Demo!
3. +US2 → Instant switching → Demo!
4. +US3 → Historical scroll → Demo!
5. +US4 → Multi-ticker → Demo!
6. +US5 → Offline resilience → Demo!

### Test Failure Protocol

Per spec.md, when tests fail:

1. **DO NOT assume tests are wrong**
2. Review canonical sources `[CS-XXX]`
3. Research Prometheus/InfluxDB/Grafana patterns
4. Formulate 3+ approaches before changing code
5. Ask clarifying questions if in doubt
6. Document decision in `docs/architecture-decisions.md`

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 71 |
| Phase 1 (Setup) | 5 |
| Phase 2 (Foundation) | 11 |
| Phase 3 (US1) | 12 |
| Phase 4 (US2) | 11 |
| Phase 5 (US3) | 8 |
| Phase 6 (US4) | 7 |
| Phase 7 (US5) | 7 |
| Phase 8 (Integration) | 10 |
| Parallel Opportunities | 21 tasks marked [P] |

**MVP Scope**: Phases 1-4 (39 tasks) delivers live updates + instant resolution switching.

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story
- All design decisions cite canonical sources [CS-XXX]
- TDD is MANDATORY - tests first, then implementation
- Verify tests FAIL before implementing, PASS after
- Commit after each logical group of tasks
- Stop at any checkpoint to validate independently
