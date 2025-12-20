# Tasks: Self-Healing Ingestion

**Input**: Design documents from `/specs/1003-self-healing-ingestion/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, quickstart.md ✓

**Tests**: Unit tests are INCLUDED per constitution requirement (Implementation Accompaniment Rule).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Project type**: Serverless Lambda (existing project)
- **Source**: `src/lambdas/ingestion/` (modify existing Lambda)
- **Tests**: `tests/unit/lambdas/ingestion/` (existing test location)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: No new infrastructure needed - extending existing ingestion Lambda

- [x] T001 Create feature branch if not already on `1003-self-healing-ingestion`
- [x] T002 [P] Verify existing handler.py structure and identify insertion point for self-healing call

**Checkpoint**: Ready to begin foundational work

---

## Phase 2: Foundational (Core Self-Healing Module)

**Purpose**: Create the self-healing module that will be called from the handler

**⚠️ CRITICAL**: This module must be complete before user story implementation

- [x] T003 Create src/lambdas/ingestion/self_healing.py with module docstring and imports
- [x] T004 [P] Create tests/unit/lambdas/ingestion/test_self_healing.py with pytest fixtures (DynamoDB table mock, SNS mock)
- [x] T005 Add SelfHealingResult dataclass in src/lambdas/ingestion/self_healing.py (items_found, items_republished, errors)
- [x] T006 Add SELF_HEALING_THRESHOLD_HOURS constant (default: 1) in src/lambdas/ingestion/self_healing.py
- [x] T007 Add SELF_HEALING_BATCH_SIZE constant (default: 100) in src/lambdas/ingestion/self_healing.py

**Checkpoint**: Foundation ready - self-healing module skeleton exists ✅

---

## Phase 3: User Story 1 - Automatic Reprocessing of Stale Items (Priority: P1) 🎯 MVP

**Goal**: Detect items with status="pending" older than 1 hour without sentiment and republish to SNS

**Independent Test**: Create a stale item in DynamoDB, call self-healing, verify SNS message published

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T008 [P] [US1] Unit test: query_stale_pending_items returns empty list when no stale items in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T009 [P] [US1] Unit test: query_stale_pending_items returns items older than threshold in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T010 [P] [US1] Unit test: query_stale_pending_items excludes items with sentiment attribute in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T011 [P] [US1] Unit test: query_stale_pending_items excludes items newer than threshold in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T012 [P] [US1] Unit test: republish_items_to_sns publishes batch messages correctly in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T013 [P] [US1] Unit test: republish_items_to_sns handles SNS failures gracefully in tests/unit/lambdas/ingestion/test_self_healing.py

### Implementation for User Story 1

- [x] T014 [US1] Implement query_stale_pending_items() in src/lambdas/ingestion/self_healing.py - query by_status GSI for pending items
- [x] T015 [US1] Implement filter logic in query_stale_pending_items() - exclude items with sentiment attribute in src/lambdas/ingestion/self_healing.py
- [x] T016 [US1] Implement get_full_items() in src/lambdas/ingestion/self_healing.py - batch GetItem for KEYS_ONLY GSI results
- [x] T017 [US1] Implement republish_items_to_sns() in src/lambdas/ingestion/self_healing.py - reuse existing _publish_sns_batch pattern
- [x] T018 [US1] Add X-Ray tracing decorator to self-healing functions in src/lambdas/ingestion/self_healing.py

**Checkpoint**: User Story 1 complete - stale items can be detected and republished ✅

---

## Phase 4: User Story 2 - Self-Healing Without Manual Intervention (Priority: P1)

**Goal**: Integrate self-healing into scheduled ingestion Lambda so it runs automatically

**Independent Test**: Trigger Lambda via EventBridge, verify self-healing runs without manual action

### Tests for User Story 2

- [x] T019 [P] [US2] Unit test: run_self_healing_check() returns result even when no stale items in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T020 [P] [US2] Unit test: handler calls self-healing after normal ingestion in tests/unit/lambdas/ingestion/test_handler.py
- [x] T021 [P] [US2] Unit test: self-healing does not block handler return on error in tests/unit/lambdas/ingestion/test_handler.py

### Implementation for User Story 2

- [x] T022 [US2] Implement run_self_healing_check() wrapper function in src/lambdas/ingestion/self_healing.py
- [x] T023 [US2] Add try/except wrapper in run_self_healing_check() to prevent failures from affecting main ingestion in src/lambdas/ingestion/self_healing.py
- [x] T024 [US2] Import self_healing module in src/lambdas/ingestion/handler.py
- [x] T025 [US2] Call run_self_healing_check() after normal ingestion completes (before return) in src/lambdas/ingestion/handler.py (after line 403)
- [x] T026 [US2] Add self_healing summary to handler response body in src/lambdas/ingestion/handler.py

**Checkpoint**: User Story 2 complete - self-healing runs automatically with every ingestion ✅

---

## Phase 5: User Story 3 - Observability of Self-Healing Actions (Priority: P2)

**Goal**: Log republish counts and emit CloudWatch metrics for monitoring

**Independent Test**: Run self-healing, check CloudWatch logs and metrics for expected entries

### Tests for User Story 3

- [x] T027 [P] [US3] Unit test: self-healing logs summary with item counts in tests/unit/lambdas/ingestion/test_self_healing.py
- [x] T028 [P] [US3] Unit test: self-healing emits SelfHealingItemsRepublished metric in tests/unit/lambdas/ingestion/test_self_healing.py

### Implementation for User Story 3

- [x] T029 [US3] Add structured logging in run_self_healing_check() with extra dict (items_found, items_republished, threshold_hours) in src/lambdas/ingestion/self_healing.py
- [x] T030 [US3] Import emit_metric from src.lib.metrics in src/lambdas/ingestion/self_healing.py
- [x] T031 [US3] Add SelfHealingItemsFound metric emit in run_self_healing_check() in src/lambdas/ingestion/self_healing.py
- [x] T032 [US3] Add SelfHealingItemsRepublished metric emit in run_self_healing_check() in src/lambdas/ingestion/self_healing.py
- [x] T033 [US3] Add SelfHealingExecutionTime metric emit in run_self_healing_check() in src/lambdas/ingestion/self_healing.py

**Checkpoint**: User Story 3 complete - observability fully implemented ✅

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T034 Run all unit tests: python -m pytest tests/unit/lambdas/ingestion/test_self_healing.py -v
- [ ] T035 Run handler tests: python -m pytest tests/unit/lambdas/ingestion/test_handler.py -v
- [x] T036 [P] Run ruff check on new/modified files
- [ ] T037 [P] Run ruff format on new/modified files
- [ ] T038 Validate quickstart.md commands work against local moto environment
- [ ] T039 [P] Update handler.py module docstring to document self-healing behavior
- [ ] T040 Commit all changes with GPG signature: git commit -S -m "feat(ingestion): Add self-healing for stale pending items"
- [ ] T041 Push to feature branch and create PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational - core stale item detection
- **User Story 2 (Phase 4)**: Depends on Foundational - can run in parallel with US1 if desired
- **User Story 3 (Phase 5)**: Depends on Foundational - can run in parallel with US1/US2
- **Polish (Phase 6)**: Depends on all user stories complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - provides republishing capability
- **User Story 2 (P1)**: Can start after Foundational - integrates US1 into handler (ideally after US1)
- **User Story 3 (P2)**: Can start after Foundational - adds observability (can be parallel with US1/US2)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Foundational module before integrating into handler
- Core implementation before observability
- Story complete before moving to next priority

### Parallel Opportunities

- T002, T004 can run in parallel (different files)
- T008-T013 (all US1 tests) can run in parallel
- T019-T021 (all US2 tests) can run in parallel
- T027-T028 (all US3 tests) can run in parallel
- T036, T037, T039 can run in parallel

---

## Parallel Example: User Story 1 Tests

```bash
# Launch all User Story 1 tests together:
Task: "Unit test: query_stale_pending_items returns empty list when no stale items"
Task: "Unit test: query_stale_pending_items returns items older than threshold"
Task: "Unit test: query_stale_pending_items excludes items with sentiment attribute"
Task: "Unit test: query_stale_pending_items excludes items newer than threshold"
Task: "Unit test: republish_items_to_sns publishes batch messages correctly"
Task: "Unit test: republish_items_to_sns handles SNS failures gracefully"
```

---

## Implementation Strategy

### MVP First (User Story 1 + User Story 2)

1. Complete Phase 1: Setup ✓
2. Complete Phase 2: Foundational module
3. Complete Phase 3: User Story 1 (stale item detection + republishing)
4. Complete Phase 4: User Story 2 (handler integration)
5. **STOP and VALIDATE**: Test self-healing works end-to-end
6. Deploy to preprod and verify dashboard shows data

### Incremental Delivery

1. Setup + Foundational → Module skeleton ready
2. Add User Story 1 → Stale items can be republished (core capability)
3. Add User Story 2 → Self-healing runs automatically (integration)
4. Add User Story 3 → Full observability (monitoring)
5. Each story adds value without breaking previous stories

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 41 |
| Setup Phase | 2 |
| Foundational Phase | 5 |
| User Story 1 (P1) | 11 (6 tests + 5 implementation) |
| User Story 2 (P1) | 8 (3 tests + 5 implementation) |
| User Story 3 (P2) | 7 (2 tests + 5 implementation) |
| Polish Phase | 8 |
| Parallel Opportunities | 18 tasks marked [P] |

**MVP Scope**: User Story 1 + User Story 2 (Tasks T001-T026) - provides core self-healing capability

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- by_status GSI has KEYS_ONLY projection - need GetItem for full data
