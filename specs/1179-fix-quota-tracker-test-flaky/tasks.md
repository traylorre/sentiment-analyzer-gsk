# Tasks: Fix QuotaTracker Thread Safety Bug

**Input**: Design documents from `/specs/1179-fix-quota-tracker-test-flaky/`
**Prerequisites**: plan.md (required), spec.md (required), research.md

**Tests**: Existing tests should pass after fix. No new tests needed.

**Organization**: Tasks are minimal for this bug fix - single file change with verification.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Verification)

**Purpose**: Confirm current state and reproduce the bug

- [ ] T001 Verify on correct branch (1179-fix-quota-tracker-test-flaky)
- [ ] T002 Run `test_different_services_can_be_updated_concurrently` to confirm failure

---

## Phase 2: Implementation

**Purpose**: Fix the thread safety bug in QuotaTrackerManager.record_call()

- [ ] T003 [US1] [US3] Modify `record_call()` in `src/lambdas/shared/quota_tracker.py` to wrap read-modify-write in `_quota_cache_lock`

**Implementation Details**:
```python
def record_call(self, service, count: int = 1) -> QuotaTracker:
    with _quota_cache_lock:                         # Add lock
        tracker = self.get_tracker()
        old_is_critical = getattr(tracker, service).is_critical
        tracker.record_call(service, count)
        _set_cached_tracker(tracker, synced=False)
        new_is_critical = getattr(tracker, service).is_critical
    # Release lock before sync

    # Rest of method remains unchanged (logging, sync)
```

---

## Phase 3: Verification - User Story 1 & 3 (Accurate Tracking + CI Reliability)

**Goal**: Verify fix resolves the race condition and CI passes consistently

**Independent Test**: Run the flaky test 100 times - must pass 100/100

- [ ] T004 [US1] [US3] Run `test_different_services_can_be_updated_concurrently` 10 times to verify fix
- [ ] T005 [US1] [US3] Run full `test_quota_tracker_threadsafe.py` test suite
- [ ] T006 [US1] Run all quota_tracker unit tests (`tests/unit/shared/test_quota_tracker*.py`)

---

## Phase 4: Verification - User Story 2 (Consistent Reads)

**Goal**: Verify no regression in read operations under contention

- [ ] T007 [US2] Run `test_get_all_states_under_contention` to verify read consistency
- [ ] T008 [US2] Run `test_mixed_record_and_check_operations` to verify readers work with writers

---

## Phase 5: Polish & Commit

**Purpose**: Finalize and commit

- [ ] T009 Run ruff check and format
- [ ] T010 Commit changes with descriptive message
- [ ] T011 Push branch and create PR

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies - start immediately
- **Phase 2 (Implementation)**: Depends on Phase 1
- **Phase 3 (Verification US1/US3)**: Depends on Phase 2
- **Phase 4 (Verification US2)**: Can run in parallel with Phase 3
- **Phase 5 (Polish)**: Depends on Phase 3 and Phase 4 passing

### Critical Path

```
T001 → T002 → T003 → T004 → T005 → T006 → T009 → T010 → T011
                         ↘ T007 → T008 ↗
```

---

## Implementation Strategy

### Single Developer Path

1. Complete Phase 1: Verify bug exists
2. Complete Phase 2: Apply fix (single line change + context)
3. Complete Phase 3-4: Run all verification tests
4. Complete Phase 5: Commit and push

### Time Estimate

- Total tasks: 11
- Estimated time: 15-20 minutes (mostly test execution time)

---

## Notes

- This is a minimal fix - single lock addition
- No new tests needed - existing tests verify the fix
- The key verification is T004 (running flaky test multiple times)
- CI will run full test suite including the previously flaky test
