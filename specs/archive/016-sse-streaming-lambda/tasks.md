# Tasks: SSE Streaming Lambda

**Input**: Design documents from `/specs/016-sse-streaming-lambda/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/sse-events.md, quickstart.md

**Tests**: Unit and E2E tests are required per constitution (Testing requirement).

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and SSE Lambda directory structure

- [x] T001 Create SSE Lambda directory structure: src/lambdas/sse_streaming/
- [x] T002 [P] Create Dockerfile for SSE Lambda with Lambda Web Adapter in src/lambdas/sse_streaming/Dockerfile
- [x] T003 [P] Create requirements.txt for SSE Lambda dependencies in src/lambdas/sse_streaming/requirements.txt
- [x] T004 [P] Create __init__.py for SSE streaming module in src/lambdas/sse_streaming/__init__.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement ConnectionManager class with thread-safe connection tracking in src/lambdas/sse_streaming/connection.py
- [x] T006 [P] Implement SSE event models (HeartbeatData, MetricsEventData, SentimentUpdateData) in src/lambdas/sse_streaming/models.py
- [x] T007 [P] Implement CloudWatch custom metrics helper in src/lambdas/sse_streaming/metrics.py
- [x] T008 Create FastAPI app with X-Ray tracing in src/lambdas/sse_streaming/handler.py
- [x] T009 [P] Unit tests for ConnectionManager in tests/unit/sse_streaming/test_connection.py
- [x] T010 [P] Unit tests for SSE event models in tests/unit/sse_streaming/test_models.py

**Checkpoint**: Foundation ready - SSE Lambda core infrastructure complete ✅

---

## Phase 3: User Story 1 - Real-Time Dashboard Updates (Priority: P1) 🎯 MVP

**Goal**: Dashboard users receive real-time sentiment updates via SSE without page refresh

**Independent Test**: Connect to /api/v2/stream and verify heartbeat + metrics events stream in real-time

### Tests for User Story 1

- [x] T011 [P] [US1] Unit test for global stream endpoint in tests/unit/sse_streaming/test_global_stream.py
- [x] T012 [P] [US1] Unit test for DynamoDB polling and metrics aggregation in tests/unit/sse_streaming/test_polling.py

### Implementation for User Story 1

- [x] T013 [US1] Implement DynamoDB polling service with configurable interval in src/lambdas/sse_streaming/polling.py
- [x] T014 [US1] Implement SSE event generator (heartbeat every 30s, metrics on change) in src/lambdas/sse_streaming/stream.py
- [x] T015 [US1] Implement GET /api/v2/stream endpoint (global, no auth) in src/lambdas/sse_streaming/handler.py
- [x] T016 [US1] Implement GET /api/v2/stream/status endpoint (connection info) in src/lambdas/sse_streaming/handler.py
- [x] T017 [US1] Add connection lifecycle logging (connect, disconnect, errors) at INFO level in src/lambdas/sse_streaming/handler.py

**Checkpoint**: Global SSE stream functional - users can receive real-time metrics updates ✅

---

## Phase 4: User Story 2 - REST API Reliability (Priority: P1)

**Goal**: Existing REST APIs continue working unchanged after two-Lambda deployment

**Independent Test**: Run full E2E test suite against REST endpoints; 100% tests pass without modification

### Tests for User Story 2

- [x] T018 [P] [US2] E2E test verifying dashboard Lambda returns unwrapped responses in tests/e2e/test_dashboard_buffered.py

### Implementation for User Story 2

- [x] T019 [US2] Update dashboard Lambda Terraform to use BUFFERED invoke mode in infrastructure/terraform/main.tf
- [x] T020 [US2] Add SSE Lambda module instance with RESPONSE_STREAM in infrastructure/terraform/main.tf
- [x] T021 [US2] Create ECR repository for SSE Lambda container in infrastructure/terraform/main.tf
- [x] T022 [US2] Add SSE Lambda Function URL output in infrastructure/terraform/main.tf (outputs in main.tf)
- [x] T023 [US2] Update modules/lambda to support image_uri for Docker Lambdas in infrastructure/terraform/modules/lambda/main.tf
- [x] T024 [US2] Add image_uri variable to Lambda module in infrastructure/terraform/modules/lambda/variables.tf

**Checkpoint**: Two-Lambda architecture deployed - REST APIs work, SSE Lambda has Function URL

---

## Phase 5: User Story 3 - Graceful Connection Handling (Priority: P2)

**Goal**: SSE connections handle reconnection gracefully with Last-Event-ID resumption

**Independent Test**: Simulate disconnect, verify client reconnects with Last-Event-ID and resumes from correct event

### Tests for User Story 3

- [x] T025 [P] [US3] Unit test for Last-Event-ID handling in tests/unit/sse_streaming/test_reconnection.py
- [x] T026 [P] [US3] Unit test for connection limit enforcement (503 response) in tests/unit/sse_streaming/test_connection_limit.py

### Implementation for User Story 3

- [x] T027 [US3] Implement event ID tracking and buffer in src/lambdas/sse_streaming/stream.py
- [x] T028 [US3] Implement Last-Event-ID header parsing for reconnection resumption in src/lambdas/sse_streaming/handler.py
- [x] T029 [US3] Implement 503 Service Unavailable response when connection limit (100) reached in src/lambdas/sse_streaming/handler.py
- [x] T030 [US3] Add Retry-After header to 503 responses in src/lambdas/sse_streaming/handler.py

**Checkpoint**: Graceful connection handling complete - reconnection and limits work

---

## Phase 6: User Story 4 - Configuration-Specific Streams (Priority: P3)

**Goal**: Users receive SSE updates filtered to their configured tickers only

**Independent Test**: Connect to /api/v2/configurations/{id}/stream with X-User-ID, verify only configured tickers appear in events

### Tests for User Story 4

- [x] T031 [P] [US4] Unit test for config stream authentication (X-User-ID required) in tests/unit/sse_streaming/test_config_stream.py
- [x] T032 [P] [US4] Unit test for ticker filtering in config streams in tests/unit/sse_streaming/test_ticker_filter.py

### Implementation for User Story 4

- [x] T033 [US4] Implement config lookup from DynamoDB in src/lambdas/sse_streaming/config.py
- [x] T034 [US4] Implement X-User-ID header validation (401 if missing) in src/lambdas/sse_streaming/handler.py
- [x] T035 [US4] Implement GET /api/v2/configurations/{config_id}/stream endpoint in src/lambdas/sse_streaming/handler.py
- [x] T036 [US4] Implement ticker filtering for sentiment_update events in src/lambdas/sse_streaming/stream.py
- [x] T037 [US4] Return 404 if configuration not found in src/lambdas/sse_streaming/handler.py

**Checkpoint**: Config-specific streams complete - users can subscribe to filtered updates

---

## Phase 7: Frontend Integration

**Purpose**: Update frontend to use separate SSE URL

- [x] T038 Add SSE_BASE_URL configuration to src/dashboard/config.js
- [x] T039 Update EventSource initialization to use SSE_BASE_URL in src/dashboard/app.js

---

## Phase 8: E2E Testing & Polish

**Purpose**: End-to-end validation and cross-cutting concerns

- [x] T040 [P] E2E test for SSE global stream endpoint in tests/e2e/test_sse.py
- [x] T041 [P] E2E test for SSE config stream endpoint in tests/e2e/test_sse.py
- [x] T042 E2E test for SSE connection limit (503 response) in tests/e2e/test_sse.py
- [x] T043 Validate quickstart.md local development workflow
- [x] T044 Update CLAUDE.md with SSE Lambda patterns and commands

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 (P2) can start after US1 basics are working
  - US4 (P3) can start after US1 basics are working
- **Frontend (Phase 7)**: Depends on US1 + US2 (needs both Lambdas deployed)
- **E2E/Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundation only - core SSE streaming
- **User Story 2 (P1)**: Foundation only - infrastructure/Terraform changes
- **User Story 3 (P2)**: Depends on US1 stream implementation
- **User Story 4 (P3)**: Depends on US1 stream implementation

### Within Each User Story

- Tests written first (TDD approach per constitution)
- Models/services before endpoints
- Core implementation before error handling
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
```
T002 (Dockerfile) || T003 (requirements.txt) || T004 (__init__.py)
```

**Phase 2 (Foundational)**:
```
T006 (models) || T007 (metrics)
T009 (connection tests) || T010 (model tests)
```

**User Story 1**:
```
T011 (stream tests) || T012 (polling tests)
```

**User Story 2**:
```
All Terraform tasks (T019-T024) are sequential within module but can parallel with US1
```

**User Story 3**:
```
T025 (reconnection tests) || T026 (limit tests)
```

**User Story 4**:
```
T031 (auth tests) || T032 (filter tests)
```

**E2E Phase**:
```
T040 (global stream E2E) || T041 (config stream E2E)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Real-Time Updates)
4. Complete Phase 4: User Story 2 (REST API Reliability)
5. **STOP and VALIDATE**: Both Lambdas deployed and functional
6. Deploy to preprod - SSE works, REST APIs unchanged

### Incremental Delivery

1. Setup + Foundational → SSE Lambda skeleton ready
2. Add US1 → Global stream works → Can demo real-time updates
3. Add US2 → Two-Lambda Terraform → Full deployment working
4. Add US3 → Reconnection handling → Production-ready resilience
5. Add US4 → Config filtering → Full feature complete

---

## Summary

| Phase | Tasks | Parallel Opportunities |
|-------|-------|------------------------|
| Phase 1: Setup | 4 | 3 tasks parallelizable |
| Phase 2: Foundational | 6 | 4 tasks parallelizable |
| Phase 3: US1 Real-Time | 7 | 2 test tasks parallelizable |
| Phase 4: US2 REST API | 7 | 1 test task |
| Phase 5: US3 Reconnection | 6 | 2 test tasks parallelizable |
| Phase 6: US4 Config Streams | 7 | 2 test tasks parallelizable |
| Phase 7: Frontend | 2 | Sequential |
| Phase 8: E2E/Polish | 5 | 2 E2E tests parallelizable |
| **Total** | **44** | Multiple parallel batches |

---

## Notes

- Docker-based Lambda required for AWS Lambda Web Adapter
- SSE Lambda reads from existing DynamoDB tables (no new tables needed)
- Dashboard Lambda stays on Mangum/BUFFERED mode (no code changes)
- 100 connection limit per Lambda instance (in-memory tracking)
- 30-second heartbeat interval, 5-second polling interval
- All commits must be GPG-signed per project constitution
