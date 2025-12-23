# Tasks: Validate Live Update Latency

**Input**: Design documents from `/specs/1019-validate-live-update-latency/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature includes E2E tests as part of the core deliverable (FR-007).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Verify prerequisites and existing code structure

- [X] T001 Verify SSE streaming Lambda code exists at src/lambdas/sse_streaming/
- [X] T002 Verify dashboard JavaScript exists at src/dashboard/timeseries.js

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user story implementation

**⚠️ CRITICAL**: US2 (Instrumentation) must complete before US1 (Validation) can run meaningful tests.

- [X] T003 Read src/lambdas/sse_streaming/models.py to understand current event structure
- [X] T004 Read src/lambdas/sse_streaming/stream.py to understand event emission flow
- [X] T005 Read src/lambdas/sse_streaming/timeseries_models.py to understand bucket event structure

**Checkpoint**: Foundation ready - instrumentation work can begin

---

## Phase 3: User Story 2 - Instrument SSE Events (Priority: P1)

**Goal**: Add origin_timestamp to SSE events for end-to-end latency measurement

**Independent Test**: Connect to SSE stream, verify events include origin_timestamp field in ISO8601 format

**Note**: US2 comes before US1 because instrumentation must exist before validation tests can measure it

### Implementation for User Story 2

- [X] T006 [US2] Add origin_timestamp field to BucketUpdateEvent in src/lambdas/sse_streaming/timeseries_models.py
- [X] T007 [US2] Add server_timestamp alias to HeartbeatData in src/lambdas/sse_streaming/models.py
- [X] T008 [US2] Update stream.py emit_bucket_update() to include origin_timestamp in src/lambdas/sse_streaming/stream.py
- [X] T009 [US2] Update heartbeat emission to include server_timestamp in src/lambdas/sse_streaming/stream.py

**Checkpoint**: SSE events now include timing fields for latency measurement

---

## Phase 4: User Story 3 - CloudWatch Latency Metrics (Priority: P2)

**Goal**: Log structured latency metrics to CloudWatch Logs for monitoring

**Independent Test**: Trigger SSE events, query CloudWatch Logs Insights, verify latency_ms field present

### Implementation for User Story 3

- [X] T010 [P] [US3] Create latency_logger.py module at src/lambdas/sse_streaming/latency_logger.py
- [X] T011 [US3] Implement log_latency_metric() function with JSON structure per data-model.md
- [X] T012 [US3] Add latency logging call after event serialization in src/lambdas/sse_streaming/stream.py
- [X] T013 [US3] Add is_cold_start detection using Lambda context in src/lambdas/sse_streaming/handler.py

**Checkpoint**: Latency metrics are being logged to CloudWatch

---

## Phase 5: User Story 1 - Validate Performance Target (Priority: P1) 🎯 MVP

**Goal**: Create E2E test validating p95 < 3s for live updates (SC-003)

**Independent Test**: Run `pytest tests/e2e/test_live_update_latency.py -v` and verify p95 < 3000ms

**Depends on**: US2 (instrumentation) and US3 (logging) must be complete

### Tests for User Story 1

- [X] T014 [P] [US1] Create test file tests/e2e/test_live_update_latency.py with pytest-playwright imports
- [X] T015 [US1] Implement fixture to navigate to preprod dashboard and wait for SSE connection
- [X] T016 [US1] Implement helper to extract window.lastLatencyMetrics via page.evaluate()
- [X] T017 [US1] Implement test_live_update_p95_under_3_seconds that collects 50+ latency samples
- [X] T018 [US1] Add statistics calculation for p50, p90, p95, p99 using Python statistics module
- [X] T019 [US1] Add assertion that p95 < 3000ms with descriptive failure message

### Client-Side Implementation for User Story 1

- [X] T020 [P] [US1] Add latency calculation to SSE event handler in src/dashboard/timeseries.js
- [X] T021 [US1] Expose window.lastLatencyMetrics object with latency_ms, event_type, timestamps
- [X] T022 [US1] Add is_clock_skew detection for negative latency values

**Checkpoint**: E2E test validates SC-003 (p95 < 3s latency)

---

## Phase 6: User Story 4 - Document Latency Breakdown (Priority: P3)

**Goal**: Create documentation explaining measurement methodology

**Independent Test**: Follow docs/performance-validation.md to run validation successfully

### Implementation for User Story 4

- [X] T023 [P] [US4] Create docs/performance-validation.md with overview section
- [X] T024 [US4] Document latency breakdown (5 components from research.md)
- [X] T025 [US4] Document how to run E2E latency test locally
- [X] T026 [US4] Document CloudWatch Logs Insights queries from contracts/latency-metrics-api.yaml
- [X] T027 [US4] Document troubleshooting for high latency scenarios
- [X] T028 [US4] Add link to this doc from quickstart.md

**Checkpoint**: Documentation complete - team can run validation independently

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [X] T029 Run ruff check on all modified files
- [X] T030 Run pytest --collect-only to verify E2E test discovery
- [X] T031 Run actual latency test against preprod (may skip if unavailable)
- [X] T032 Update specs/1019-validate-live-update-latency/quickstart.md with final commands

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verify prerequisites
- **Foundational (Phase 2)**: Depends on Setup - understand existing code
- **US2 Instrumentation (Phase 3)**: Depends on Foundational - must instrument first
- **US3 CloudWatch (Phase 4)**: Depends on US2 - logs reference origin_timestamp
- **US1 Validation (Phase 5)**: Depends on US2 and US3 - cannot test without instrumentation
- **US4 Documentation (Phase 6)**: Can proceed after US2, references US1 results
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 2 (P1 - Instrumentation)**: Must complete first - enables measurement
- **User Story 3 (P2 - CloudWatch)**: Can start after US2 - logs use origin_timestamp
- **User Story 1 (P1 - Validation)**: Depends on US2 and US3 - measures instrumented events
- **User Story 4 (P3 - Documentation)**: Can proceed after US2, references US1/US3

### Within Each User Story

- Read existing code before modifying
- Models/fields before logging logic
- Server-side before client-side
- Tests after instrumentation is deployed

### Parallel Opportunities

- T010 (create latency_logger.py) [P] can start after US2 foundation
- T014 (create test file) [P] can start after US2 complete
- T020 (client-side latency) [P] can run with T014
- T023 (create docs) [P] can start after US2 complete

---

## Parallel Example: After Phase 3 (Instrumentation Complete)

```bash
# These can run in parallel once US2 instrumentation is complete:
Task: T010 [P] [US3] Create latency_logger.py module
Task: T014 [P] [US1] Create test file tests/e2e/test_live_update_latency.py
Task: T020 [P] [US1] Add latency calculation to SSE event handler
Task: T023 [P] [US4] Create docs/performance-validation.md
```

---

## Implementation Strategy

### MVP First (User Story 2 + 1)

1. Complete Phase 1: Setup (verify prerequisites)
2. Complete Phase 2: Foundational (understand existing code)
3. Complete Phase 3: User Story 2 (add instrumentation)
4. **CHECKPOINT**: Verify origin_timestamp in SSE events manually
5. Complete Phase 4: User Story 3 (add latency logging)
6. Complete Phase 5: User Story 1 (create E2E validation test)
7. **STOP and VALIDATE**: Run E2E test to validate SC-003
8. If test passes: MVP complete, p95 < 3s validated

### Incremental Delivery

1. Complete US2 → Instrumentation deployed, manual verification possible
2. Complete US3 → CloudWatch metrics available, Logs Insights queries work
3. Complete US1 → Automated E2E validation, CI integration possible
4. Complete US4 → Team can run validations independently, documentation complete

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 32 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 3 |
| Phase 3 (US2 - Instrumentation) | 4 |
| Phase 4 (US3 - CloudWatch) | 4 |
| Phase 5 (US1 - Validation) | 9 |
| Phase 6 (US4 - Documentation) | 6 |
| Phase 7 (Polish) | 4 |
| Parallel Opportunities | 5 tasks marked [P] |

**MVP Scope**: Phases 1-5 (22 tasks) delivers validated p95 < 3s latency target.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US2 must complete before US1 because E2E test needs instrumentation
- Commit after each task or logical group
- Stop at Phase 5 checkpoint to validate MVP
