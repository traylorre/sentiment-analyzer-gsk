# Tasks: Parallel Ingestion with Cross-Source Deduplication

**Input**: Design documents from `/specs/1010-parallel-ingestion-dedup/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and thread-safety utilities

- [x] T001 Create `src/lib/threading_utils.py` with ThreadSafeQueue and lock helpers
- [x] T002 [P] Create `tests/unit/lib/test_threading_utils.py` with concurrency tests
- [x] T003 [P] Create `src/lambdas/ingestion/dedup.py` module stub with normalize_headline() and generate_dedup_key() signatures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add thread-safety to `src/lambdas/shared/quota_tracker.py` with threading.Lock around record_call() and check_quota()
- [x] T005 [P] Create `tests/unit/shared/test_quota_tracker_threadsafe.py` with concurrent call tests (use threading to simulate race conditions)
- [x] T006 Add thread-safety to `src/lambdas/shared/circuit_breaker.py` with threading.Lock around state transitions
- [x] T007 [P] Create `tests/unit/shared/test_circuit_breaker_threadsafe.py` with concurrent failure recording tests
- [x] T008 Implement `normalize_headline()` in `src/lambdas/ingestion/dedup.py` per research.md (lowercase, strip punctuation, collapse whitespace)
- [x] T009 [P] Create `tests/unit/ingestion/test_headline_normalization.py` with edge cases (punctuation, unicode, trailing source attribution)
- [x] T010 Implement `generate_dedup_key()` in `src/lambdas/ingestion/dedup.py` using SHA256(normalized_headline | publish_date[:10])[:32]
- [x] T011 [P] Create `tests/unit/ingestion/test_dedup_key_generation.py` with cross-source matching tests

**Checkpoint**: Foundation ready - thread-safety and dedup utilities complete. User story implementation can now begin.

---

## Phase 3: User Story 1 - Cross-Source Duplicate Prevention (Priority: P1) MVP

**Goal**: Articles appearing in both Tiingo and Finnhub are stored only once with both sources tracked

**Independent Test**: Ingest a known article from both sources, verify exactly one database record exists with `sources: ["tiingo", "finnhub"]`

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T012 [P] [US1] Create `tests/unit/ingestion/test_cross_source_dedup.py` with test cases:
  - test_same_headline_different_sources_creates_one_record
  - test_tiingo_first_finnhub_updates_sources
  - test_finnhub_first_tiingo_updates_sources
  - test_normalized_headlines_match (with/without punctuation)
- [x] T013 [P] [US1] Create `tests/unit/ingestion/test_upsert_with_source.py` with DynamoDB conditional update tests using moto

### Implementation for User Story 1

- [x] T014 [US1] Implement `upsert_article_with_source()` in `src/lambdas/ingestion/dedup.py` using DynamoDB conditional writes with list_append for sources[]
- [x] T015 [US1] Implement `build_source_attribution()` in `src/lambdas/ingestion/dedup.py` to create per-source metadata dict
- [x] T016 [US1] Modify `_process_article()` in `src/lambdas/ingestion/handler.py` to use dedup_key instead of source_id for PK
- [x] T017 [US1] Update article item schema in handler.py to include: dedup_key, normalized_headline, sources[], source_attribution{}
- [x] T018 [US1] Ensure only one SNS message is published per unique dedup_key (check before publish)

**Checkpoint**: Cross-source deduplication working. Same article from both sources creates one record with multi-source tracking.

---

## Phase 4: User Story 2 - Parallel Source Fetching (Priority: P2)

**Goal**: Fetch from Tiingo and Finnhub simultaneously using ThreadPoolExecutor

**Independent Test**: Time ingestion of 10 tickers, verify parallel execution completes faster than 2x single-source time

### Tests for User Story 2

- [x] T019 [P] [US2] Create `tests/unit/ingestion/test_parallel_fetcher.py` with test cases:
  - test_parallel_fetch_calls_both_sources
  - test_parallel_fetch_handles_one_source_failure
  - test_parallel_fetch_respects_rate_limits
  - test_parallel_fetch_collects_results_thread_safely
- [x] T020 [P] [US2] Create `tests/unit/ingestion/test_parallel_timing.py` to verify parallel execution is faster than sequential

### Implementation for User Story 2

- [x] T021 [US2] Create `src/lambdas/ingestion/parallel_fetcher.py` with ParallelFetcher class using ThreadPoolExecutor(max_workers=4)
- [x] T022 [US2] Implement `fetch_all_sources()` method that submits (ticker, source) pairs as concurrent futures
- [x] T023 [US2] Add thread-safe result collection using queue.Queue from src/lib/threading_utils.py
- [x] T024 [US2] Add thread-safe error collection for per-source failures
- [x] T025 [US2] Integrate ParallelFetcher into `src/lambdas/ingestion/handler.py` lambda_handler(), replacing sequential fetch loop
- [x] T026 [US2] Add pre-fetch quota check using thread-safe quota tracker to prevent exceeding rate limits

**Checkpoint**: Parallel fetching operational. Both sources queried concurrently with thread-safe collection.

---

## Phase 5: User Story 3 - Multi-Source Attribution Tracking (Priority: P3)

**Goal**: Each article tracks which sources provided it with detailed per-source metadata

**Independent Test**: Query an article found in both sources, verify source_attribution contains metadata for both

### Tests for User Story 3

- [ ] T027 [P] [US3] Create `tests/unit/ingestion/test_source_attribution.py` with test cases:
  - test_single_source_article_has_one_attribution
  - test_dual_source_article_has_both_attributions
  - test_attribution_contains_required_fields (article_id, url, crawl_timestamp, original_headline)
- [ ] T028 [P] [US3] Create `tests/integration/ingestion/test_attribution_query.py` to verify querying articles returns full attribution

### Implementation for User Story 3

- [ ] T029 [US3] Enhance `build_source_attribution()` in dedup.py to capture: article_id, url, crawl_timestamp, original_headline, source_name
- [ ] T030 [US3] Modify Tiingo adapter field mapping in `src/lambdas/shared/adapters/tiingo.py` to expose source_name from response
- [ ] T031 [P] [US3] Modify Finnhub adapter field mapping in `src/lambdas/shared/adapters/finnhub.py` to expose source_name from response
- [ ] T032 [US3] Update DynamoDB item schema in data-model.md to document source_attribution map structure
- [ ] T033 [US3] Add attribution aggregation endpoint stub in contracts/metrics-api.yaml (GET /api/v2/metrics/attribution)

**Checkpoint**: Attribution tracking complete. All articles include detailed per-source provenance metadata.

---

## Phase 6: User Story 4 - Collision Metrics & Monitoring (Priority: P4)

**Goal**: Track and expose cross-source collision rate for operational monitoring

**Independent Test**: After ingesting 100 articles (50 each source), verify metrics show correct collision count and rate

### Tests for User Story 4

- [ ] T034 [P] [US4] Create `tests/unit/ingestion/test_collision_metrics.py` with test cases:
  - test_metrics_track_articles_fetched_per_source
  - test_metrics_track_collisions_detected
  - test_collision_rate_calculation
  - test_metrics_published_to_cloudwatch
- [ ] T035 [P] [US4] Create `tests/unit/ingestion/test_collision_alerts.py` for threshold alerting tests

### Implementation for User Story 4

- [ ] T036 [US4] Create `src/lambdas/ingestion/metrics.py` with IngestionMetrics class to track: articles_fetched{source}, articles_stored, collisions_detected
- [ ] T037 [US4] Implement collision_rate property calculation in IngestionMetrics
- [ ] T038 [US4] Add `publish_to_cloudwatch()` method to emit metrics at end of Lambda invocation
- [ ] T039 [US4] Integrate IngestionMetrics into handler.py, incrementing counters during processing
- [ ] T040 [US4] Add CloudWatch alarm threshold at collision_rate > 0.40 or < 0.05 per SC-008

**Checkpoint**: Metrics and monitoring complete. Collision rate visible in CloudWatch with alerting.

---

## Phase 7: Integration & Polish

**Purpose**: End-to-end testing and cross-cutting improvements

- [ ] T041 Create `tests/integration/ingestion/test_parallel_ingestion_flow.py` with LocalStack E2E test:
  - Setup mock Tiingo/Finnhub responses with overlapping articles
  - Run full ingestion flow
  - Verify DynamoDB contains deduplicated articles with multi-source attribution
  - Verify SNS received exactly one message per unique article
- [ ] T042 [P] Add logging throughout parallel_fetcher.py and dedup.py for observability
- [ ] T043 [P] Update `src/lambdas/ingestion/handler.py` docstrings to document new parallel flow
- [ ] T044 Run `make validate` and fix any linting/formatting issues
- [ ] T045 Run `make test-local` and ensure all unit tests pass
- [ ] T046 Validate quickstart.md commands work end-to-end
- [ ] T047 Update CLAUDE.md with new technologies: `concurrent.futures`, `threading.Lock`, `queue.Queue`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on T001 (threading_utils) - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion (T004-T011)
- **User Story 2 (Phase 4)**: Depends on Phase 2 + can use US1 dedup (T014-T018)
- **User Story 3 (Phase 5)**: Depends on US1 attribution schema being defined
- **User Story 4 (Phase 6)**: Depends on US1 (needs dedup to measure collisions)
- **Integration (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - Core dedup logic
- **User Story 2 (P2)**: Can start after US1 upsert logic exists - Parallelizes the flow
- **User Story 3 (P3)**: Can start after US1 - Enhances attribution data
- **User Story 4 (P4)**: Can start after US1 - Measures collision effectiveness

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundation utilities before domain logic
- Core implementation before integrations
- Story complete before moving to next priority

### Parallel Opportunities

Within Phase 2 (Foundational):
- T005 || T007 || T009 || T011 (all test files, different modules)
- T004 || T006 (different shared modules)

Within Phase 3 (US1):
- T012 || T013 (both test files)

Within Phase 4 (US2):
- T019 || T020 (both test files)

Within Phase 5 (US3):
- T027 || T028 (both test files)
- T030 || T031 (different adapter files)

Within Phase 6 (US4):
- T034 || T035 (both test files)

Within Phase 7 (Integration):
- T042 || T043 (different files)

---

## Parallel Example: Phase 2 Foundational

```bash
# Launch all test files together (after implementation stubs exist):
Task: "Create tests/unit/shared/test_quota_tracker_threadsafe.py"
Task: "Create tests/unit/shared/test_circuit_breaker_threadsafe.py"
Task: "Create tests/unit/ingestion/test_headline_normalization.py"
Task: "Create tests/unit/ingestion/test_dedup_key_generation.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T003)
2. Complete Phase 2: Foundational (T004-T011) - **CRITICAL**
3. Complete Phase 3: User Story 1 (T012-T018)
4. **STOP and VALIDATE**: Test cross-source dedup works correctly
5. Deploy to preprod and verify

### Incremental Delivery

1. Setup + Foundational → Thread-safe infrastructure ready
2. Add User Story 1 → Cross-source dedup working → **MVP!**
3. Add User Story 2 → Parallel fetching live → Performance improvement
4. Add User Story 3 → Attribution tracking → Data enrichment
5. Add User Story 4 → Metrics & monitoring → Operational visibility

### Total Task Count: 47

| Phase | Tasks | Parallel Opportunities |
|-------|-------|------------------------|
| Phase 1: Setup | 3 | 2 |
| Phase 2: Foundational | 8 | 4 |
| Phase 3: US1 (P1 MVP) | 7 | 2 |
| Phase 4: US2 (P2) | 8 | 2 |
| Phase 5: US3 (P3) | 7 | 3 |
| Phase 6: US4 (P4) | 7 | 2 |
| Phase 7: Integration | 7 | 2 |
| **Total** | **47** | **17** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Verify tests fail before implementing
- Commit with GPG signature after each task or logical group
- Stop at any checkpoint to validate story independently
- **MVP Scope**: Phases 1-3 (18 tasks) delivers cross-source deduplication
