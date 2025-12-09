# Tasks: Fix Latency Timing in Traffic Generator

**Input**: Design documents from `/specs/066-fix-latency-timing/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, quickstart.md

**Tests**: No new tests required - existing test `test_very_long_latency` validates the fix.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Target file: `interview/traffic_generator.py`
- Test file: `tests/unit/interview/test_traffic_generator.py`

---

## Phase 1: Setup (No Infrastructure Changes Needed)

**Purpose**: Feature 066 is a bug fix in existing code - no new infrastructure needed

- [x] T001 Create feature branch `066-fix-latency-timing` from main

**Checkpoint**: Branch ready for implementation

---

## Phase 2: User Story 1 - Reliable Latency Tracking (Priority: P1) 🎯 MVP

**Goal**: Fix `time.time()` usage to use `time.monotonic()` for reliable latency measurement

**Independent Test**: Run `test_very_long_latency` 10 times consecutively and verify all pass with positive latency values

### Implementation for User Story 1

- [x] T002 [US1] Change `start = time.time()` to `start = time.monotonic()` at line 124 in interview/traffic_generator.py
- [x] T003 [US1] Change `latency = (time.time() - start) * 1000` to `latency = (time.monotonic() - start) * 1000` at line 135 in interview/traffic_generator.py
- [x] T002b [US1] Also changed lines 499, 506, 513, 520 (additional time.time() usages found)

### Validation for User Story 1

- [x] T004 [US1] Run `pytest tests/unit/interview/test_traffic_generator.py -k test_very_long_latency -v` - PASSED
- [x] T005 [US1] Run test 5 times consecutively - 5/5 PASSED
- [x] T006 [US1] Run `grep -n "time.time()" interview/traffic_generator.py` - No matches found

**Checkpoint**: User Story 1 complete - `test_very_long_latency` passes consistently with positive latency values

---

## Phase 3: User Story 2 - Constitution Compliance (Priority: P2)

**Goal**: Verify codebase complies with constitution Amendment 1.5 (Deterministic Time Handling)

**Independent Test**: Search for `time.time()` usage in timing-critical code and confirm none exist

### Validation for User Story 2

- [x] T007 [US2] Run full test suite `make test-unit` - 1607 passed, 6 skipped, 80.13% coverage
- [x] T008 [US2] Verify no `time.time()` in `traffic_generator.py` - Confirmed, 0 matches

**Checkpoint**: User Story 2 complete - codebase complies with constitution timing guidelines

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and commit

- [ ] T009 Run quickstart.md validation steps (all success criteria)
- [ ] T010 Commit changes with GPG signature per constitution section 8
- [ ] T011 Push to feature branch and create PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **User Story 1 (Phase 2)**: Depends on Setup completion
- **User Story 2 (Phase 3)**: Depends on User Story 1 completion (needs fix applied first)
- **Polish (Phase 4)**: Depends on both User Stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Setup - Core bug fix
- **User Story 2 (P2)**: Depends on User Story 1 - Validates fix meets constitution

### Within Each User Story

- Implementation tasks before validation
- Validation confirms story is complete
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 2 (US1)**: T002 and T003 can run in parallel (different lines in same file, but no conflicts)

```bash
# Launch both line changes together:
Task: T002 "Change time.time() to time.monotonic() at line 124"
Task: T003 "Change time.time() to time.monotonic() at line 135"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (create branch)
2. Complete Phase 2: User Story 1 (apply 2-line fix)
3. **STOP and VALIDATE**: Run test 10 times, verify all pass
4. Deploy/merge if ready

### Incremental Delivery

1. US1 complete → Latency measurement is reliable
2. US2 complete → Constitution compliance verified
3. Polish complete → Code committed, PR created

### Single Developer Strategy

1. Complete US1 (P1) first - this is the critical bug fix
2. Complete US2 (P2) after - validates fix meets constitution
3. Polish phase - commit and push

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- This is a minimal 2-line fix - complexity is intentionally low
- Existing test validates the fix - no new tests needed
- Commit after validation passes
- Stop at any checkpoint to validate story independently
