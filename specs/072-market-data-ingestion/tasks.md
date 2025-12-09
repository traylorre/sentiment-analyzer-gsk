# Tasks: Market Data Ingestion

**Input**: Design documents from `/specs/072-market-data-ingestion/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required per constitution (Implementation Accompaniment Rule). Each new function requires unit tests.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Lambda code**: `src/lambdas/` (existing structure)
- **Shared utilities**: `src/lambdas/shared/` (existing)
- **Tests**: `tests/unit/`, `tests/integration/`
- **Infrastructure**: `infra/` (Terraform)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and core utilities needed by all user stories

- [ ] T001 Create feature branch `072-market-data-ingestion` from main
- [ ] T002 Create ingestion Lambda directory structure at `src/lambdas/ingestion/`
- [ ] T003 [P] Implement deduplication key generator utility in `src/lambdas/shared/utils/dedup.py`
- [ ] T004 [P] Create NewsItem pydantic model in `src/lambdas/shared/models/news_item.py`
- [ ] T005 [P] Create CollectionEvent pydantic model in `src/lambdas/shared/models/collection_event.py`
- [ ] T006 [P] Create DataSourceConfig pydantic model in `src/lambdas/shared/models/data_source.py`
- [ ] T007 [P] Unit test for deduplication key generator in `tests/unit/shared/test_dedup.py`
- [ ] T008 [P] Unit tests for new pydantic models in `tests/unit/shared/models/test_news_item.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T009 Implement FailoverOrchestrator class in `src/lambdas/shared/failover.py` (primary/secondary with timeout)
- [ ] T010 Add `get_news_with_failover()` method to FailoverOrchestrator
- [ ] T011 [P] Unit tests for FailoverOrchestrator in `tests/unit/shared/test_failover.py`
- [ ] T012 Implement ConsecutiveFailureTracker in `src/lambdas/shared/failure_tracker.py` (15-min window, 3-failure threshold)
- [ ] T013 [P] Unit tests for ConsecutiveFailureTracker in `tests/unit/shared/test_failure_tracker.py`
- [ ] T014 Create Terraform module for EventBridge scheduler at `infra/modules/eventbridge_scheduler/`
- [ ] T015 [P] Create Terraform module for SNS notification topic at `infra/modules/sns_notification/`
- [ ] T016 Create ingestion Lambda base handler skeleton in `src/lambdas/ingestion/handler.py`
- [ ] T017 [P] Create ingestion Lambda config in `src/lambdas/ingestion/config.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Fresh Data Availability (Priority: P1) 🎯 MVP

**Goal**: Collect market sentiment data every 5 minutes during market hours, ensuring data freshness <15 minutes

**Independent Test**: Invoke Lambda manually and verify news items appear in DynamoDB with timestamps within 15 minutes of current time

### Tests for User Story 1

- [ ] T018 [P] [US1] Unit test for scheduled collection trigger in `tests/unit/ingestion/test_handler_schedule.py`
- [ ] T019 [P] [US1] Unit test for news item storage with deduplication in `tests/unit/ingestion/test_storage.py`
- [ ] T020 [P] [US1] Integration test for ingestion flow in `tests/integration/ingestion/test_collection_flow.py`

### Implementation for User Story 1

- [ ] T021 [US1] Implement `handle_scheduled_collection()` in `src/lambdas/ingestion/handler.py`
- [ ] T022 [US1] Implement `fetch_news()` using FailoverOrchestrator in `src/lambdas/ingestion/collector.py`
- [ ] T023 [US1] Implement `store_news_items()` with deduplication in `src/lambdas/ingestion/storage.py`
- [ ] T024 [US1] Add market hours check (9:30 AM - 4:00 PM ET) in `src/lambdas/shared/utils/market.py`
- [ ] T025 [P] [US1] Unit test for market hours check in `tests/unit/shared/test_market_hours.py`
- [ ] T026 [US1] Configure EventBridge schedule (5-min cron during market hours) in `infra/environments/dev/ingestion.tf`
- [ ] T027 [US1] Add CloudWatch logging for collection events in handler

**Checkpoint**: US1 complete - data collection runs automatically every 5 minutes during market hours

---

## Phase 4: User Story 2 - Multi-Source Resilience (Priority: P1)

**Goal**: Automatic failover from Tiingo to Finnhub within 10 seconds when primary source fails

**Independent Test**: Simulate Tiingo failure (mock timeout) and verify data comes from Finnhub within 10 seconds

### Tests for User Story 2

- [ ] T028 [P] [US2] Unit test for failover trigger on timeout in `tests/unit/ingestion/test_failover_trigger.py`
- [ ] T029 [P] [US2] Unit test for source attribution tracking in `tests/unit/ingestion/test_source_attribution.py`
- [ ] T030 [P] [US2] Integration test for failover scenario in `tests/integration/ingestion/test_failover_scenario.py`

### Implementation for User Story 2

- [ ] T031 [US2] Add 10-second timeout to FailoverOrchestrator in `src/lambdas/shared/failover.py`
- [ ] T032 [US2] Implement source attribution in NewsItem storage in `src/lambdas/ingestion/storage.py`
- [ ] T033 [US2] Add `is_failover` flag to CollectionEvent in `src/lambdas/ingestion/collector.py`
- [ ] T034 [US2] Implement circuit breaker integration in FailoverOrchestrator (uses existing CircuitBreakerManager)
- [ ] T035 [US2] Add failover metrics to CloudWatch in `src/lambdas/ingestion/metrics.py`

**Checkpoint**: US2 complete - system resilient to single-source failures with automatic failover

---

## Phase 5: User Story 3 - Data Quality Confidence (Priority: P2)

**Goal**: Provide confidence scores (0.0-1.0) with each sentiment value for informed decision-making

**Independent Test**: Fetch news items and verify each has sentiment.score, sentiment.confidence, and sentiment.label

### Tests for User Story 3

- [ ] T036 [P] [US3] Unit test for sentiment score range validation in `tests/unit/shared/models/test_sentiment_score.py`
- [ ] T037 [P] [US3] Unit test for confidence threshold logic in `tests/unit/ingestion/test_confidence_threshold.py`

### Implementation for User Story 3

- [ ] T038 [US3] Implement sentiment score extraction from Finnhub adapter in `src/lambdas/ingestion/sentiment.py`
- [ ] T039 [US3] Add confidence calculation for Tiingo (derived from source reliability) in `src/lambdas/ingestion/sentiment.py`
- [ ] T040 [US3] Implement label derivation (positive/neutral/negative based on score thresholds) in `src/lambdas/shared/models/news_item.py`
- [ ] T041 [US3] Store sentiment embedded in NewsItem in `src/lambdas/ingestion/storage.py`

**Checkpoint**: US3 complete - all sentiment data includes confidence scores and labels

---

## Phase 6: User Story 4 - Operational Visibility (Priority: P2)

**Goal**: Operations team can monitor collection health and receive alerts on failures

**Independent Test**: Trigger 3 consecutive failures and verify SNS alert is published within 5 minutes

### Tests for User Story 4

- [ ] T042 [P] [US4] Unit test for consecutive failure alerting in `tests/unit/ingestion/test_alerting.py`
- [ ] T043 [P] [US4] Unit test for CollectionEvent logging in `tests/unit/ingestion/test_collection_event.py`
- [ ] T044 [P] [US4] Integration test for SNS notification delivery in `tests/integration/ingestion/test_alerting_sns.py`

### Implementation for User Story 4

- [ ] T045 [US4] Implement alert publisher using SNS in `src/lambdas/ingestion/alerting.py`
- [ ] T046 [US4] Integrate ConsecutiveFailureTracker with alert publisher in handler
- [ ] T047 [US4] Implement CollectionEvent persistence to DynamoDB in `src/lambdas/ingestion/audit.py`
- [ ] T048 [US4] Add CloudWatch metrics for collection success rate in `src/lambdas/ingestion/metrics.py`
- [ ] T049 [US4] Create CloudWatch dashboard for ingestion monitoring in `infra/modules/cloudwatch_dashboard/`
- [ ] T050 [US4] Configure SNS topic subscription for operations team in `infra/environments/dev/alerting.tf`

**Checkpoint**: US4 complete - full operational visibility with proactive alerting

---

## Phase 7: Downstream Notification

**Goal**: Notify dependent systems within 30 seconds of new data storage (FR-004, SC-005)

**Independent Test**: Store new news items and verify SNS message published within 30 seconds

### Tests for Downstream Notification

- [ ] T051 [P] Unit test for notification payload generation in `tests/unit/ingestion/test_notification_payload.py`
- [ ] T052 [P] Integration test for SNS publish timing in `tests/integration/ingestion/test_notification_timing.py`

### Implementation for Downstream Notification

- [ ] T053 Implement NewDataNotification publisher in `src/lambdas/ingestion/notification.py`
- [ ] T054 Integrate notification with storage completion in `src/lambdas/ingestion/storage.py`
- [ ] T055 Create SNS topic for downstream notifications in `infra/environments/dev/sns.tf`
- [ ] T056 Add notification latency metric to CloudWatch in `src/lambdas/ingestion/metrics.py`

**Checkpoint**: Downstream systems receive notifications within 30 seconds of new data

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, cleanup, and production readiness

- [ ] T057 [P] Update CLAUDE.md with ingestion patterns and troubleshooting
- [ ] T058 [P] Create ON_CALL_SOP.md section for ingestion failures
- [ ] T059 Run `make validate` and fix any issues
- [ ] T060 Run `make test-local` and verify all tests pass
- [ ] T061 [P] Add type hints to all new modules
- [ ] T062 Security review: verify no secrets in code, proper log sanitization
- [ ] T063 Run quickstart.md validation scenarios
- [ ] T064 Update pyproject.toml if any new dependencies added
- [ ] T065 Final code review and PR creation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **US1-US4 (Phases 3-6)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 and US4 are both P2 and can proceed after P1s or in parallel
- **Downstream (Phase 7)**: Depends on US1 (storage) completion
- **Polish (Phase 8)**: Depends on all feature phases being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Enhances US1 failover but independently testable
- **User Story 3 (P2)**: Can start after Foundational - Independent sentiment enrichment
- **User Story 4 (P2)**: Can start after Foundational - Independent monitoring layer

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/utilities before services
- Services before handlers
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup):**
- T003, T004, T005, T006 can all run in parallel (different files)
- T007, T008 can run in parallel with each other

**Phase 2 (Foundational):**
- T011, T013, T015, T017 can run in parallel
- T014, T015 (Terraform modules) can run in parallel

**Per User Story:**
- All tests marked [P] within a story can run in parallel
- Models within a story marked [P] can run in parallel

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all model creation tasks together:
Task: T004 "Create NewsItem pydantic model in src/lambdas/shared/models/news_item.py"
Task: T005 "Create CollectionEvent pydantic model in src/lambdas/shared/models/collection_event.py"
Task: T006 "Create DataSourceConfig pydantic model in src/lambdas/shared/models/data_source.py"
```

## Parallel Example: User Story 1

```bash
# Launch all US1 tests together:
Task: T018 "Unit test for scheduled collection trigger"
Task: T019 "Unit test for news item storage with deduplication"
Task: T020 "Integration test for ingestion flow"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Fresh Data Availability)
4. **STOP and VALIDATE**: Test data collection every 5 minutes
5. Deploy to dev if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add User Story 1 → Test → Deploy (MVP: scheduled collection works)
3. Add User Story 2 → Test → Deploy (Resilient: failover works)
4. Add User Story 3 → Test → Deploy (Quality: confidence scores)
5. Add User Story 4 → Test → Deploy (Visibility: monitoring)
6. Add Downstream → Test → Deploy (Complete: notifications)
7. Polish → Final PR

### Critical Path

```
Setup → Foundational → US1 (MVP) → US2 (Resilience) → Downstream
                    ↘ US3 (Quality) ↗
                    ↘ US4 (Visibility) ↗
```

---

## Notes

- Existing adapters (TiingoAdapter, FinnhubAdapter) are reused - no modifications needed
- Existing CircuitBreakerManager is reused for failover state
- Existing DynamoDB helpers with `put_item_if_not_exists` provide deduplication
- Constitution v1.7 Core Principles: Search for existing functions before creating new ones
- All tests use fixed dates (per constitution) - no `date.today()` or `datetime.now()`
