# Tasks: Session Eviction Atomic Transaction

**Feature**: 1188-session-eviction-transact
**Created**: 2026-01-10

## Phase 1: Setup

- [x] T001 Create feature branch and spec directory

## Phase 2: Foundation (Error Infrastructure)

- [x] T002 Add `SessionLimitRaceError` class to `src/lambdas/shared/errors/session_errors.py`
- [x] T003 [P] Add unit test for SessionLimitRaceError in `tests/unit/dashboard/test_session_eviction.py`

## Phase 3: User Story 1 - Session Limit Enforcement (P1)

**Goal**: Atomic session eviction when user hits session limit
**Independent Test**: Create user with 5 sessions, login, verify count stays at 5

- [x] T004 [US1] Create `get_user_sessions()` helper to query sessions by user_id in `src/lambdas/dashboard/auth.py`
- [x] T005 [US1] Create `evict_oldest_session_atomic()` function with TransactWriteItems in `src/lambdas/dashboard/auth.py`
- [x] T006 [US1] Add `create_session_with_limit_enforcement()` wrapper that calls eviction when at limit in `src/lambdas/dashboard/auth.py`
- [x] T007 [P] [US1] Add unit tests for evict_oldest_session_atomic in `tests/unit/dashboard/test_session_eviction.py`
- [x] T008 [P] [US1] Add unit tests for create_session_with_limit_enforcement in `tests/unit/dashboard/test_session_eviction.py`

## Phase 4: User Story 2 - Evicted Token Blocklist (P1)

**Goal**: Blocklisted tokens rejected on refresh
**Independent Test**: Evict session, attempt refresh with evicted token, verify 401

- [x] T009 [US2] Create `is_token_blocklisted()` function in `src/lambdas/dashboard/auth.py`
- [x] T010 [US2] Add blocklist check at start of `refresh_access_tokens()` in `src/lambdas/dashboard/auth.py`
- [x] T011 [P] [US2] Add unit tests for blocklist check in `tests/unit/dashboard/test_session_eviction.py`

## Phase 5: User Story 3 - Race Condition Retry (P2)

**Goal**: TransactionCanceledException returns retriable error
**Independent Test**: Force condition check failure, verify SessionLimitRaceError raised

- [x] T012 [US3] Update `evict_oldest_session_atomic()` to raise SessionLimitRaceError on TransactionCanceledException in `src/lambdas/dashboard/auth.py`
- [x] T013 [P] [US3] Add unit test for race condition handling in `tests/unit/dashboard/test_session_eviction.py`

## Phase 6: Integration

- [ ] T014 Update `create_anonymous_session()` to use `create_session_with_limit_enforcement()` in `src/lambdas/dashboard/auth.py`
- [ ] T015 Update `handle_oauth_callback()` to use `create_session_with_limit_enforcement()` in `src/lambdas/dashboard/auth.py`
- [ ] T016 Update `verify_magic_link_token()` to use `create_session_with_limit_enforcement()` in `src/lambdas/dashboard/auth.py`

## Phase 7: Polish

- [x] T017 Run ruff check/format on all modified files
- [ ] T018 Run full unit test suite
- [ ] T019 [P] Add integration test for concurrent session creation in `tests/integration/test_session_race.py`

## Dependencies

```
T001 -> T002 -> T003 (sequential: error class needed first)
T002 -> T004, T009 (error class needed for functions)
T004 -> T005 -> T006 -> T007, T008 (US1 sequential, tests parallel)
T009 -> T010 -> T011 (US2 sequential)
T005, T012 -> T012, T013 (US3 depends on eviction function)
T006, T010 -> T014, T015, T016 (integration needs both US1 and US2)
T014-T016 -> T017 -> T018 -> T019
```

## Parallel Execution Opportunities

**After T002 completes (error class ready)**:
- T003, T004, T009 can run in parallel (independent files)

**After T005 completes (eviction function ready)**:
- T007, T008 can run in parallel (both test the same function)

**After T010 completes (blocklist check ready)**:
- T011, T012 can run in parallel (independent test scenarios)

**After T016 completes (all integration done)**:
- T017, T019 can run in parallel (lint vs integration tests)

## Completion Criteria

- [ ] All unit tests pass
- [ ] No lint errors
- [ ] TransactWriteItems used for session eviction
- [ ] Blocklist check in refresh flow
- [ ] SessionLimitRaceError raised on transaction conflict
- [ ] Session count never exceeds limit under concurrent load

## Implementation Notes

- SESSION_LIMIT constant: 5 (matches spec assumptions)
- Blocklist key pattern: `BLOCK#refresh#{hash}` as PK, `BLOCK` as SK
- TTL on blocklist: 30 days (matches session duration)
- Use low-level boto3 client for TransactWriteItems (not Table resource)
