# Tasks: SSE Endpoint Implementation

**Input**: Design documents from `/specs/015-sse-endpoint-fix/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included per FR-012, FR-013, FR-014 requirements (comprehensive testing requested)

**Organization**: Tasks grouped by user story for independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1, US2, US3, US4)
- Exact file paths included

---

## Phase 1: Setup

**Purpose**: Create SSE module structure

- [x] T001 Create SSE module file at src/lambdas/dashboard/sse.py with module docstring and imports (sse_starlette, asyncio, logging, threading)
- [x] T002 [P] Create unit test file at tests/unit/dashboard/test_sse.py with pytest imports and markers

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core SSE infrastructure that ALL user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Implement ConnectionManager class in src/lambdas/dashboard/sse.py with acquire(), release(), count property, and max_connections=100 (FR-015)
- [x] T004 Implement Pydantic models (MetricsEventData, NewItemEventData, HeartbeatEventData) in src/lambdas/dashboard/sse.py per data-model.md
- [x] T005 [P] Add unit tests for ConnectionManager (acquire/release, limit enforcement) in tests/unit/dashboard/test_sse.py
- [x] T006 Implement create_event_generator() async generator in src/lambdas/dashboard/sse.py that yields heartbeat events every 30 seconds (FR-004)
- [x] T007 Add logging for connection open/close events in src/lambdas/dashboard/sse.py (FR-016)
- [x] T008 [P] Add unit tests for create_event_generator() (heartbeat timing, event format) in tests/unit/dashboard/test_sse.py

**Checkpoint**: Foundation ready - SSE infrastructure complete

---

## Phase 3: User Story 1 - Dashboard Real-Time Connection (Priority: P1) 🎯 MVP

**Goal**: Global SSE endpoint at /api/v2/stream returns 200 with text/event-stream, dashboard shows "Connected"

**Independent Test**: `curl -N http://localhost:8000/api/v2/stream` returns streaming events with heartbeats

### Tests for User Story 1

- [x] T009 [P] [US1] Add unit test for global stream endpoint handler in tests/unit/dashboard/test_sse.py
- [x] T010 [P] [US1] Add E2E test for /api/v2/stream availability (T095) - update tests/e2e/test_sse.py to add global stream test

### Implementation for User Story 1

- [x] T011 [US1] Implement GET /api/v2/stream endpoint in src/lambdas/dashboard/sse.py using EventSourceResponse (FR-001, FR-003)
- [x] T012 [US1] Add metrics event generation to create_event_generator() in src/lambdas/dashboard/sse.py - call aggregate_dashboard_metrics() from metrics.py (FR-009)
- [x] T013 [US1] Wire SSE router to handler.py - add include_router() call for sse.router in src/lambdas/dashboard/router_v2.py
- [x] T014 [US1] Add connection count metric emission in src/lambdas/dashboard/sse.py (FR-017)
- [x] T015 [US1] Handle 503 response when connection limit reached in src/lambdas/dashboard/sse.py (FR-015)

**Checkpoint**: Dashboard shows "Connected", receives heartbeats and metrics events

---

## Phase 4: User Story 2 - Graceful Connection Recovery (Priority: P2)

**Goal**: SSE supports Last-Event-ID header for reconnection resilience

**Independent Test**: Connect with `Last-Event-ID: evt_001` header, verify server accepts and resumes

### Tests for User Story 2

- [x] T016 [P] [US2] Add unit test for Last-Event-ID header handling in tests/unit/dashboard/test_sse.py

### Implementation for User Story 2

- [x] T017 [US2] Extract Last-Event-ID from request headers in GET /api/v2/stream in src/lambdas/dashboard/sse.py (FR-005)
- [x] T018 [US2] Add event ID to all emitted events in create_event_generator() in src/lambdas/dashboard/sse.py (FR-011)
- [ ] T019 [US2] Update existing E2E test_sse_reconnection_with_last_event_id in tests/e2e/test_sse.py to verify 200 status (not skip on 404)

**Checkpoint**: Reconnection with Last-Event-ID works, E2E test T098 passes

---

## Phase 5: User Story 3 - Configuration-Specific Streaming (Priority: P3)

**Goal**: Authenticated users can stream events for specific configurations

**Independent Test**: Create config, connect to /api/v2/configurations/{id}/stream, receive filtered events

### Tests for User Story 3

- [x] T020 [P] [US3] Add unit test for config stream auth validation in tests/unit/dashboard/test_sse.py
- [x] T021 [P] [US3] Add unit test for config stream 404 on invalid config in tests/unit/dashboard/test_sse.py

### Implementation for User Story 3

- [x] T022 [US3] Implement GET /api/v2/configurations/{config_id}/stream endpoint in src/lambdas/dashboard/sse.py (FR-002)
- [x] T023 [US3] Add authentication check using get_user_id_from_request() from router_v2.py in config stream (FR-006, FR-007)
- [x] T024 [US3] Add configuration validation - return 404 if config not found (FR-008)
- [x] T025 [US3] Create config-specific event generator that filters events by config's tickers in src/lambdas/dashboard/sse.py
- [x] T026 [US3] Update E2E tests (T095-T099) in tests/e2e/test_sse.py to remove pytest.skip on 404 - endpoints now exist (FR-014)

**Checkpoint**: All E2E SSE tests pass without skipping

---

## Phase 6: User Story 4 - Local Development Testing (Priority: P4)

**Goal**: Developers can test SSE locally without deploying to preprod

**Independent Test**: Run uvicorn locally, curl SSE endpoint, see events

### Implementation for User Story 4

- [ ] T027 [US4] Create local SSE test script at scripts/test_sse_local.py with example curl commands
- [ ] T028 [US4] Update quickstart.md with local testing instructions (already exists, verify completeness)
- [ ] T029 [US4] Add SSE fixtures to tests/conftest.py for mocking EventSourceResponse in unit tests (FR-012)
- [ ] T030 [US4] Verify unit tests run without network dependencies - add mock for DynamoDB calls in tests/unit/dashboard/test_sse.py

**Checkpoint**: Developers can fully test SSE locally

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T031 Run full test suite: `PYTHONPATH=. pytest tests/unit/dashboard/test_sse.py tests/e2e/test_sse.py -v`
- [x] T032 [P] Format code: `black src/lambdas/dashboard/sse.py tests/unit/dashboard/test_sse.py`
- [x] T033 [P] Lint code: `ruff check src/lambdas/dashboard/sse.py tests/unit/dashboard/test_sse.py`
- [ ] T034 Run E2E tests against preprod to verify SC-002 (all SSE tests pass)
- [ ] T035 Verify dashboard shows "Connected" in preprod (SC-001)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - MVP delivery
- **User Story 2 (Phase 4)**: Depends on Foundational - can parallel with US1
- **User Story 3 (Phase 5)**: Depends on Foundational - can parallel with US1/US2
- **User Story 4 (Phase 6)**: Depends on Foundational - can parallel with others
- **Polish (Phase 7)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Independent - core SSE functionality
- **US2 (P2)**: Independent - reconnection support (can parallel with US1)
- **US3 (P3)**: Independent - config-specific streaming (can parallel)
- **US4 (P4)**: Independent - local testing (can parallel)

### Parallel Opportunities

```bash
# After Foundational phase, can run in parallel:
# - All user stories (US1, US2, US3, US4) can be worked on simultaneously
# - Within each story, tests marked [P] can run in parallel
```

---

## Parallel Example: User Story 1

```bash
# Launch tests for US1 together:
Task: "T009 - Add unit test for global stream endpoint handler"
Task: "T010 - Add E2E test for /api/v2/stream availability"

# Then implementation sequentially (T011 → T012 → T013 → T014 → T015)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T002)
2. Complete Phase 2: Foundational (T003-T008)
3. Complete Phase 3: User Story 1 (T009-T015)
4. **STOP and VALIDATE**: Dashboard shows "Connected", /api/v2/stream returns 200
5. Deploy to preprod and verify

### Incremental Delivery

1. Setup + Foundational → SSE infrastructure ready
2. Add US1 → Dashboard connects → Deploy (MVP!)
3. Add US2 → Reconnection works → Deploy
4. Add US3 → Config streams work → Deploy
5. Add US4 → Local testing ready → Complete

---

## Success Criteria Mapping

| Success Criteria | Tasks |
|-----------------|-------|
| SC-001: Dashboard "Connected" in 5s | T011, T013, T015, T035 |
| SC-002: All E2E tests pass | T026, T034 |
| SC-003: Pipeline succeeds | T031, T034 |
| SC-004: Metrics event in 60s | T012 |
| SC-005: Reconnect in 30s | T017, T018, T019 |
| SC-006: 80% unit test coverage | T005, T008, T009, T016, T020, T021 |
| SC-007: Local testing works | T027, T028, T029, T030 |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story
