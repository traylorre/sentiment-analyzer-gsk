# Tasks: Quota Tracker Reduced-Rate Mode Hysteresis

**Input**: Design documents from `/specs/1231-quota-rate-hysteresis/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included per constitution requirement.

**Organization**: Single source file change with dedicated test file.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Hysteresis State and Core Functions

**Purpose**: Add the counters, threshold configuration, and core recording functions. Everything else builds on this.

- [ ] T001 Add hysteresis module-level globals to `src/lambdas/shared/quota_tracker.py` — add `_consecutive_successes: int = 0`, `_consecutive_failures: int = 0`, and `QUOTA_RATE_STABILITY_THRESHOLD = int(os.environ.get("QUOTA_RATE_STABILITY_THRESHOLD", "3"))` alongside existing reduced-rate globals (after line 63)
- [ ] T002 Implement `_record_dynamo_success()` in `src/lambdas/shared/quota_tracker.py` — acquire `_quota_cache_lock`, increment `_consecutive_successes`, reset `_consecutive_failures` to 0; if `_consecutive_successes >= QUOTA_RATE_STABILITY_THRESHOLD` and `_reduced_rate_mode` is True, call `_exit_reduced_rate_mode()`
- [ ] T003 Implement `_record_dynamo_failure()` in `src/lambdas/shared/quota_tracker.py` — acquire `_quota_cache_lock`, increment `_consecutive_failures`, reset `_consecutive_successes` to 0; if `_consecutive_failures >= QUOTA_RATE_STABILITY_THRESHOLD` and `_reduced_rate_mode` is False, call `_enter_reduced_rate_mode()`
- [ ] T004 Update `clear_quota_cache()` in `src/lambdas/shared/quota_tracker.py` — add `_consecutive_successes = 0` and `_consecutive_failures = 0` to the global resets to maintain test isolation

**Checkpoint**: Core hysteresis functions exist. No callers changed yet.

---

## Phase 2: Wire Hysteresis into Callers

**Purpose**: Replace direct `_enter/_exit_reduced_rate_mode()` calls with hysteresis-aware `_record_dynamo_success/failure()`.

- [ ] T005 [US1] Update `record_call()` in `src/lambdas/shared/quota_tracker.py` — replace `_exit_reduced_rate_mode()` (line 605) with `_record_dynamo_success()`; replace `_enter_reduced_rate_mode()` (line 611) with `_record_dynamo_failure()`
- [ ] T006 [US1] Update `get_tracker()` in `src/lambdas/shared/quota_tracker.py` — replace `_exit_reduced_rate_mode()` (line 471) with `_record_dynamo_success()`

**Checkpoint**: Mode transitions now require N consecutive events. Oscillation eliminated.

---

## Phase 3: Enhanced Logging

**Purpose**: Add counter context to mode transition log messages for operations visibility.

- [ ] T007 [US2] Update `_enter_reduced_rate_mode()` log message to include consecutive failure count — change logger.warning to include `extra={"consecutive_failures": _consecutive_failures}`
- [ ] T008 [US2] Update `_exit_reduced_rate_mode()` log message to include consecutive success count — change logger.info to include `extra={"consecutive_successes": _consecutive_successes}`

**Checkpoint**: Log messages include hysteresis context.

---

## Phase 4: Tests

**Purpose**: Comprehensive tests for hysteresis behavior, edge cases, and backward compatibility.

- [ ] T009 Create `tests/unit/test_quota_tracker_hysteresis.py` with test fixture — import `clear_quota_cache`, `QuotaTrackerManager`, etc.; autouse fixture calls `clear_quota_cache()` before/after each test; helper `_make_mock_table()` creates mock DynamoDB table
- [ ] T010 [US1] Test: flapping DynamoDB does not cause oscillation — alternate success/failure on mock table for 20 calls; assert `_reduced_rate_mode` stays False (never reaches N consecutive failures)
- [ ] T011 [US1] Test: N consecutive failures enters reduced-rate mode — configure mock table to fail N times; call `record_call()` N times; assert `_reduced_rate_mode` is True
- [ ] T012 [US1] Test: N consecutive successes exits reduced-rate mode — enter reduced mode (via N failures), then succeed N times; assert `_reduced_rate_mode` is False
- [ ] T013 [US1] Test: (N-1) successes then 1 failure resets counter — enter reduced mode, succeed (N-1) times, fail once; assert `_reduced_rate_mode` is still True
- [ ] T014 [US1] Test: (N-1) failures then 1 success resets counter — fail (N-1) times from normal mode, succeed once; assert `_reduced_rate_mode` is still False
- [ ] T015 [US1] Test: configurable threshold via env var — set `QUOTA_RATE_STABILITY_THRESHOLD=5` in env; verify 4 failures don't trigger but 5 do
- [ ] T016 [US2] Test: log messages include counter context — use `caplog` fixture; trigger mode entry via N failures; assert log message contains "consecutive_failures"
- [ ] T017 Backward compatibility: run existing tests — verify `tests/unit/test_quota_tracker_atomic.py` tests still pass (especially reduced-rate tests which may need threshold adjustment)

**Checkpoint**: All tests pass. `make test-local` succeeds.

---

## Phase 5: Validation

- [ ] T018 Run `make validate` — verify linting, formatting pass
- [ ] T019 Run `make test-local` — verify all tests pass including existing quota tracker tests

---

## Dependencies & Execution Order

```
Phase 1: Hysteresis State (T001-T004)
    | (BLOCKS ALL)
Phase 2: Wire Callers (T005-T006)
    |
Phase 3: Enhanced Logging (T007-T008)
    |
Phase 4: Tests (T009-T017)
    |
Phase 5: Validation (T018-T019)
```

All phases are sequential (single file, each builds on previous).

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1: Hysteresis state + functions (T001-T004)
2. Phase 2: Wire callers (T005-T006)
3. Phase 4: Core tests (T009-T015)
4. **STOP**: Oscillation eliminated, tests pass

### Full Delivery

- 19 tasks total
- 1 source file modified: `src/lambdas/shared/quota_tracker.py` (~30 lines added)
- 1 new test file: `tests/unit/test_quota_tracker_hysteresis.py` (~200 lines)
