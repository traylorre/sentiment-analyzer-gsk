# Tasks: GSI Query Optimization

**Input**: Design documents from `/specs/502-gsi-query-optimization/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test updates ARE required (FR-007, FR-008, FR-009 in spec.md mandate test modifications)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No setup required - this is a refactoring feature on existing codebase

All infrastructure already exists. GSIs are deployed in Terraform.

**Checkpoint**: Ready to proceed to Foundational phase

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test fixtures that all user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 Add GSI-aware table creation fixtures with by_entity_status, by_sentiment, by_email GSIs in tests/conftest.py
- [x] T002 [P] Create query mock helper function with side_effect support in tests/conftest.py
- [x] T003 [P] Create paginated query mock helper in tests/conftest.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Efficient Ticker Lookup (Priority: P1) 🎯 MVP

**Goal**: Replace table.scan() with by_entity_status GSI query in ingestion handler

**Independent Test**: Verify `_get_active_tickers()` uses GSI query with IndexName="by_entity_status"

### Implementation for User Story 1

- [x] T004 [US1] Replace table.scan() with table.query(IndexName="by_entity_status") in src/lambdas/ingestion/handler.py:_get_active_tickers()
- [x] T005 [US1] Add pagination handling with LastEvaluatedKey loop in src/lambdas/ingestion/handler.py:_get_active_tickers()
- [ ] T006 [US1] Update unit tests to mock table.query() instead of table.scan() in tests/unit/lambdas/ingestion/
- [ ] T007 [US1] Add test case for empty results from GSI query in tests/unit/lambdas/ingestion/
- [ ] T008 [US1] Add test case for pagination scenario in tests/unit/lambdas/ingestion/

**Checkpoint**: User Story 1 complete - ingestion handler uses GSI query

---

## Phase 4: User Story 2 - Efficient Sentiment Item Retrieval (Priority: P1)

**Goal**: Replace _scan_table() with _query_by_sentiment() using by_sentiment GSI in SSE streaming

**Independent Test**: Verify polling service queries by_sentiment GSI instead of scanning

### Implementation for User Story 2

- [x] T009 [US2] Create new _query_by_sentiment() function using table.query(IndexName="by_sentiment") in src/lambdas/sse_streaming/polling.py
- [x] T010 [US2] Replace all _scan_table() calls with _query_by_sentiment() in src/lambdas/sse_streaming/polling.py
- [x] T011 [US2] Remove deprecated _scan_table() function from src/lambdas/sse_streaming/polling.py
- [ ] T012 [US2] Update unit tests to mock table.query() in tests/unit/lambdas/sse_streaming/
- [ ] T013 [US2] Add test case for different sentiment types (positive/neutral/negative) in tests/unit/lambdas/sse_streaming/

**Checkpoint**: User Story 2 complete - SSE polling uses GSI query

---

## Phase 5: User Story 3 - Efficient Alert Lookup by Ticker (Priority: P2)

**Goal**: Replace table.scan() with by_entity_status GSI query with FilterExpression for ticker

**Independent Test**: Verify `_find_alerts_by_ticker()` uses GSI query with FilterExpression

### Implementation for User Story 3

- [x] T014 [US3] Replace table.scan() with table.query(IndexName="by_entity_status", FilterExpression="ticker = :ticker") in src/lambdas/notification/alert_evaluator.py:_find_alerts_by_ticker()
- [x] T015 [US3] Ensure pagination is handled with LastEvaluatedKey in src/lambdas/notification/alert_evaluator.py
- [ ] T016 [US3] Update unit tests to mock table.query() in tests/unit/lambdas/notification/test_alert_evaluator.py
- [ ] T017 [US3] Add test case for ticker with no matching alerts in tests/unit/lambdas/notification/test_alert_evaluator.py

**Checkpoint**: User Story 3 complete - alert evaluator uses GSI query

---

## Phase 6: User Story 4 - Efficient Digest User Lookup (Priority: P2)

**Goal**: Replace table.scan() with by_entity_status GSI query in digest service

**Independent Test**: Verify `get_users_due_for_digest()` uses GSI query

### Implementation for User Story 4

- [x] T018 [US4] Replace table.scan() with table.query(IndexName="by_entity_status") in src/lambdas/notification/digest_service.py:get_users_due_for_digest()
- [x] T019 [US4] Maintain existing ProjectionExpression and ExpressionAttributeNames in src/lambdas/notification/digest_service.py
- [ ] T020 [US4] Update unit tests to mock table.query() in tests/unit/test_digest_service.py
- [ ] T021 [US4] Add test case for no users due for digest in tests/unit/test_digest_service.py

**Checkpoint**: User Story 4 complete - digest service uses GSI query

---

## Phase 7: User Story 5 - Email Lookup Deprecation (Priority: P3)

**Goal**: Deprecate get_user_by_email() to prevent accidental scan usage

**Independent Test**: Verify `get_user_by_email()` raises NotImplementedError with guidance message

### Implementation for User Story 5

- [x] T022 [US5] Replace get_user_by_email() implementation with NotImplementedError in src/lambdas/dashboard/auth.py
- [x] T023 [US5] Add docstring deprecation notice directing to get_user_by_email_gsi() in src/lambdas/dashboard/auth.py
- [ ] T024 [US5] Update any tests that call get_user_by_email() to expect NotImplementedError in tests/unit/lambdas/dashboard/
- [ ] T025 [US5] Add explicit test for NotImplementedError with correct message in tests/unit/lambdas/dashboard/test_auth.py

**Checkpoint**: User Story 5 complete - deprecated function properly guards against misuse

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Validation and cleanup across all stories

- [x] T026 [P] Verify no table.scan() calls remain in production code (except chaos.py) using grep
- [ ] T027 [P] Run full unit test suite to confirm all tests pass: pytest tests/unit/ -v
- [x] T028 [P] Run linting and formatting: ruff check src/ tests/ && ruff format src/ tests/
- [x] T029 Validate quickstart.md verification steps in specs/502-gsi-query-optimization/quickstart.md
- [x] T030 Update any affected docstrings with GSI usage notes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No setup needed - skip
- **Foundational (Phase 2)**: Creates shared test fixtures - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - US1 and US2 are both P1 and can proceed in parallel
  - US3 and US4 are both P2 and can proceed in parallel after P1
  - US5 is P3 and can proceed after P2
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 3 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 4 (P2)**: Can start after Foundational - No dependencies on other stories
- **User Story 5 (P3)**: Can start after Foundational - No dependencies on other stories

### Within Each User Story

- Implementation before test updates (modify code, then fix tests)
- Pagination handling after basic query conversion
- Test validation at end of each story

### Parallel Opportunities

- T002 and T003 can run in parallel (different helper functions)
- US1 (T004-T008) and US2 (T009-T013) can run in parallel (different Lambda modules)
- US3 (T014-T017) and US4 (T018-T021) can run in parallel (different service files)
- T026, T027, T028 can all run in parallel (different validation types)

---

## Parallel Example: Foundational Phase

```bash
# Launch foundation tasks in parallel:
Task: "Add GSI-aware table creation fixtures in tests/conftest.py"
Task: "Create query mock helper function in tests/conftest.py"
Task: "Create paginated query mock helper in tests/conftest.py"
```

## Parallel Example: P1 Stories

```bash
# After foundation, launch both P1 stories in parallel:
# Story 1: Ingestion Handler
Task: "Replace table.scan() with GSI query in src/lambdas/ingestion/handler.py"

# Story 2: SSE Streaming
Task: "Create _query_by_sentiment() in src/lambdas/sse_streaming/polling.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T003)
2. Complete Phase 3: User Story 1 (T004-T008)
3. **STOP and VALIDATE**: Run `pytest tests/unit/lambdas/ingestion/ -v`
4. Verify no scan() calls: `grep -r "\.scan(" src/lambdas/ingestion/`

### Incremental Delivery

1. Complete Foundational → Test fixtures ready
2. Add User Story 1 (ingestion) → Validate → Most critical path optimized
3. Add User Story 2 (SSE streaming) → Validate → User-facing performance improved
4. Add User Story 3+4 (notifications) → Validate → Cost optimization complete
5. Add User Story 5 (deprecation) → Validate → Future misuse prevented

### Parallel Team Strategy

With multiple developers:

1. Team completes Foundational together (T001-T003)
2. Once Foundational is done:
   - Developer A: User Story 1 (ingestion)
   - Developer B: User Story 2 (SSE streaming)
3. After P1 stories:
   - Developer A: User Story 3 (alerts)
   - Developer B: User Story 4 (digest)
4. Either developer: User Story 5 (deprecation)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently testable after completion
- chaos.py exception: Retains table.scan(Limit=100) for admin debugging
- Reference: Branch `2-remove-scan-fallbacks` has prior implementation (behind main)
