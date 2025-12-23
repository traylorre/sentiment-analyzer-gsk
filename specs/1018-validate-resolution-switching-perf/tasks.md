# Tasks: Validate Resolution Switching Performance

**Input**: Design documents from `/specs/1018-validate-resolution-switching-perf/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: This feature involves creating a performance test. Tests are part of the core deliverable.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Ensure prerequisites are in place for instrumentation and testing

- [x] T001 Verify Playwright and pytest-playwright are installed via `pip list | grep playwright`
- [x] T002 Verify preprod dashboard is accessible and returns 200 for resolution endpoints

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before user stories can be implemented

**⚠️ CRITICAL**: User Story 1 (Performance Test) depends on User Story 2 (Instrumentation) completing first. US2 must complete before US1 can run meaningful tests.

- [x] T003 Read existing switchResolution() implementation in src/dashboard/timeseries.js to understand current timing approach
- [x] T004 Identify chart render completion callback pattern in src/dashboard/timeseries.js

**Checkpoint**: Foundation ready - instrumentation work can begin

---

## Phase 3: User Story 2 - Instrument Resolution Switching (Priority: P1)

**Goal**: Add Performance API instrumentation to measure perceived resolution switch latency

**Independent Test**: Trigger a resolution switch in browser and verify `window.lastSwitchMetrics` is populated with timing data

**Note**: US2 comes before US1 because instrumentation must exist before the performance test can measure it

### Implementation for User Story 2

- [x] T005 [US2] Add performance.mark('resolution-switch-start') at start of switchResolution() in src/dashboard/timeseries.js
- [x] T006 [US2] Add performance.mark('resolution-switch-end') after chart.update() completes in src/dashboard/timeseries.js
- [x] T007 [US2] Add performance.measure() to calculate duration between marks in src/dashboard/timeseries.js
- [x] T008 [US2] Store previousResolution before switch to capture from_resolution in src/dashboard/timeseries.js
- [x] T009 [US2] Track cache_hit boolean based on cache.get() result in src/dashboard/timeseries.js
- [x] T010 [US2] Expose window.lastSwitchMetrics object with {duration_ms, from_resolution, to_resolution, cache_hit, timestamp} in src/dashboard/timeseries.js
- [x] T011 [US2] Add same instrumentation to MultiTickerManager.switchResolution() in src/dashboard/timeseries.js

**Checkpoint**: Instrumentation complete - can verify by opening browser console and switching resolution

---

## Phase 4: User Story 1 - Validate Performance Target (Priority: P1) 🎯 MVP

**Goal**: Create automated performance test validating p95 < 100ms for resolution switching

**Independent Test**: Run `pytest tests/e2e/test_resolution_switch_perf.py -v` and verify test passes with p95 < 100ms

### Tests for User Story 1

- [x] T012 [P] [US1] Create test file tests/e2e/test_resolution_switch_perf.py with pytest-playwright imports
- [x] T013 [US1] Implement fixture to navigate to preprod dashboard and warm cache by loading all 8 resolutions in tests/e2e/test_resolution_switch_perf.py
- [x] T014 [US1] Implement helper to click resolution button and capture window.lastSwitchMetrics via page.evaluate() in tests/e2e/test_resolution_switch_perf.py
- [x] T015 [US1] Implement test_resolution_switch_p95_under_100ms that executes 100+ resolution switches in tests/e2e/test_resolution_switch_perf.py
- [x] T016 [US1] Add statistics calculation for min, max, mean, p50, p90, p95, p99 using Python statistics module in tests/e2e/test_resolution_switch_perf.py
- [x] T017 [US1] Add assertion that p95 < 100ms with descriptive failure message in tests/e2e/test_resolution_switch_perf.py
- [x] T018 [US1] Add structured output of PerformanceReport as JSON to test log in tests/e2e/test_resolution_switch_perf.py
- [x] T019 [US1] Add separate p95 assertion for cache-hit only switches in tests/e2e/test_resolution_switch_perf.py

**Checkpoint**: Performance test complete and validating SC-002

---

## Phase 5: User Story 3 - Document Performance Validation (Priority: P2)

**Goal**: Create documentation explaining measurement methodology

**Independent Test**: Follow docs/performance-validation.md instructions and successfully run a performance test

### Implementation for User Story 3

- [x] T020 [P] [US3] Create docs/performance-validation.md with overview of performance validation approach
- [x] T021 [US3] Document how resolution switching latency is measured (Performance API marks/measures) in docs/performance-validation.md
- [x] T022 [US3] Document how to run the performance test locally in docs/performance-validation.md
- [x] T023 [US3] Document how to interpret test results (what p95 < 100ms means) in docs/performance-validation.md
- [x] T024 [US3] Document troubleshooting for common issues (cache misses, slow preprod) in docs/performance-validation.md
- [x] T025 [US3] Document how to add new performance validations following this pattern in docs/performance-validation.md

**Checkpoint**: Documentation complete - team members can run validations independently

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [x] T026 Run ruff check on test file tests/e2e/test_resolution_switch_perf.py
- [x] T027 Run pytest --collect-only to verify test discovery in tests/e2e/test_resolution_switch_perf.py
- [x] T028 Run actual performance test against preprod to validate p95 target (may skip if preprod unavailable)
- [x] T029 Update specs/1018-validate-resolution-switching-perf/quickstart.md with final test command

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - verify prerequisites
- **Foundational (Phase 2)**: Depends on Setup - understand existing code
- **US2 Instrumentation (Phase 3)**: Depends on Foundational - must add instrumentation first
- **US1 Performance Test (Phase 4)**: Depends on US2 - cannot test without instrumentation
- **US3 Documentation (Phase 5)**: Can start after US2, complete after US1
- **Polish (Phase 6)**: Depends on US1 and US2 complete

### User Story Dependencies

- **User Story 2 (P1 - Instrumentation)**: Must complete first - enables measurement
- **User Story 1 (P1 - Performance Test)**: Depends on US2 - measures what instrumentation exposes
- **User Story 3 (P2 - Documentation)**: Can proceed in parallel after US2, references US1 results

### Within Each User Story

- Instrumentation changes in single file (timeseries.js) - sequential within US2
- Test file tasks can be done incrementally - build up test capability
- Documentation can be written as understanding develops

### Parallel Opportunities

- T012 (create test file) [P] can start after US2 foundation
- T020 (create docs) [P] can start after US2 foundation
- Within US1: Tasks are sequential (building test incrementally)
- Within US3: Documentation tasks are sequential (building on each section)

---

## Parallel Example: After Phase 3 (Instrumentation Complete)

```bash
# These can run in parallel once US2 instrumentation is complete:
Task: T012 [P] [US1] Create test file tests/e2e/test_resolution_switch_perf.py
Task: T020 [P] [US3] Create docs/performance-validation.md
```

---

## Implementation Strategy

### MVP First (User Story 2 + 1)

1. Complete Phase 1: Setup (verify prerequisites)
2. Complete Phase 2: Foundational (understand existing code)
3. Complete Phase 3: User Story 2 (add instrumentation)
4. **CHECKPOINT**: Verify instrumentation by manually testing in browser
5. Complete Phase 4: User Story 1 (create performance test)
6. **STOP and VALIDATE**: Run performance test to validate SC-002
7. If test passes: MVP complete, p95 < 100ms validated

### Incremental Delivery

1. Complete US2 → Instrumentation in production, manual testing possible
2. Complete US1 → Automated validation, CI integration possible
3. Complete US3 → Team can run validations independently, documentation complete

---

## Summary

| Metric | Count |
|--------|-------|
| Total Tasks | 29 |
| Phase 1 (Setup) | 2 |
| Phase 2 (Foundational) | 2 |
| Phase 3 (US2 - Instrumentation) | 7 |
| Phase 4 (US1 - Performance Test) | 8 |
| Phase 5 (US3 - Documentation) | 6 |
| Phase 6 (Polish) | 4 |
| Parallel Opportunities | 2 tasks marked [P] |

**MVP Scope**: Phases 1-4 (19 tasks) delivers validated p95 < 100ms resolution switching.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US2 must complete before US1 because performance test needs instrumentation
- Commit after each task or logical group
- Stop at Phase 4 checkpoint to validate MVP
