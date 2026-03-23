# Tasks: SSE Connection Leak Cleanup

**Input**: Design documents from `/specs/1231-sse-connection-cleanup/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included per constitution requirement.

**Organization**: Incremental modifications to existing files, one concern per phase.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Connection Liveness Tracking (FR-001, FR-005)

**Purpose**: Add `last_activity` field to `SSEConnection` and update it on every event dispatch. This is the foundation for all TTL/sweep logic.

- [ ] T001 [P1] [US1] Add `last_activity: datetime` field to `SSEConnection` dataclass in `src/lambdas/sse_streaming/connection.py` -- defaults to `datetime.now(UTC)` on creation (same pattern as `connected_at`). This field tracks the last time any event was dispatched for this connection.
- [ ] T002 [P1] [US1] Modify `ConnectionManager.update_last_event_id()` in `connection.py` to also set `self._connections[connection_id].last_activity = datetime.now(UTC)` when updating the event ID. This piggybacks on the existing call path in `stream.py` (called on every heartbeat, metrics, sentiment_update, and partial_bucket dispatch).
- [ ] T003 [P1] [US1] Write unit tests in `tests/unit/sse_streaming/test_connection.py` -- extend `TestSSEConnection`: (1) `test_connection_has_last_activity` verifies `last_activity` is set on creation, (2) extend `test_update_last_event_id` to verify `last_activity` is also updated.

**Checkpoint**: `SSEConnection` tracks activity. `update_last_event_id()` refreshes it. Existing tests still pass.

---

## Phase 2: TTL Configuration and Stale Detection (FR-002, FR-003, FR-008)

**Purpose**: Add TTL configuration and `sweep_stale()` method to `ConnectionManager`.

- [ ] T004 [P1] [US1] Add `connection_ttl_seconds` parameter to `ConnectionManager.__init__()` -- defaults to `int(os.environ.get("SSE_CONNECTION_TTL", str(2 * int(os.environ.get("SSE_HEARTBEAT_INTERVAL", "30")))))`. Store as `self._connection_ttl_seconds`. Add `@property connection_ttl_seconds` accessor.
- [ ] T005 [P1] [US1] Implement `ConnectionManager.sweep_stale()` method -- under `self._lock`, iterate `self._connections`, compute `inactive_seconds = (datetime.now(UTC) - conn.last_activity).total_seconds()`, remove entries where `inactive_seconds > self._connection_ttl_seconds`. Log each removal at WARNING level with `connection_id`, `inactive_seconds`, and sanitized `user_id`. Return the count of swept connections (int).
- [ ] T006 [P1] [US1] Write `tests/unit/sse_streaming/test_connection_cleanup.py` with class `TestSweepStale`: (1) `test_sweep_removes_stale_connections` -- create manager, acquire 3 connections, patch `datetime.now(UTC)` to advance past TTL, call `sweep_stale()`, verify count is 0 and return value is 3. (2) `test_sweep_preserves_active_connections` -- acquire 2 connections, update one's `last_activity` to recent, advance time, sweep, verify 1 remains. (3) `test_sweep_with_no_stale_connections` -- acquire connections, don't advance time, sweep returns 0. (4) `test_sweep_logs_removed_connections` -- verify WARNING log emitted for each swept connection.

**Checkpoint**: `sweep_stale()` correctly identifies and removes stale connections based on TTL.

---

## Phase 3: Sweep on Acquire (FR-004) -- MVP

**Purpose**: Wire `sweep_stale()` into `acquire()` so stale connections are reclaimed before capacity check.

- [ ] T007 [P2] [US2] Modify `ConnectionManager.acquire()` to call `self._sweep_stale_internal()` (lock-free internal version) at the beginning of the `with self._lock:` block, BEFORE the capacity check. Extract the sweep logic into `_sweep_stale_internal()` (no lock, called while lock is held) and have `sweep_stale()` call it under the lock. This avoids double-locking.
- [ ] T008 [P2] [US2] Write tests in `test_connection_cleanup.py` with class `TestSweepOnAcquire`: (1) `test_acquire_sweeps_stale_before_capacity_check` -- fill manager to capacity with stale connections, advance time, call `acquire()`, verify it succeeds (returns SSEConnection, not None) and stale entries are gone. (2) `test_acquire_at_capacity_with_no_stale_returns_none` -- fill manager with active connections, call `acquire()`, verify returns None. (3) `test_acquire_partial_stale_frees_some_slots` -- 50 active + 50 stale at capacity 100, acquire succeeds, count is 51.

**Checkpoint**: `acquire()` self-heals the pool. The primary leak scenario is fixed.

---

## Phase 4: Status Endpoint Extension (FR-006, FR-007)

**Purpose**: Add stale connection visibility to the status endpoint.

- [ ] T009 [P3] [US3] Add `stale_connections` and `connection_ttl_seconds` fields to `StreamStatus` model in `src/lambdas/sse_streaming/models.py`. Both `int`, with `stale_connections` defaulting to 0 and `connection_ttl_seconds` defaulting to 60.
- [ ] T010 [P3] [US3] Add `count_stale()` method to `ConnectionManager` -- under lock, count connections where `(datetime.now(UTC) - conn.last_activity).total_seconds() > self._connection_ttl_seconds`. This is read-only (does not remove).
- [ ] T011 [P3] [US3] Modify `ConnectionManager.get_status()` to include `stale_connections: self.count_stale()` and `connection_ttl_seconds: self._connection_ttl_seconds` in the returned dict.
- [ ] T012 [P3] [US3] Write tests in `test_connection_cleanup.py` with class `TestStatusEndpoint`: (1) `test_status_includes_stale_count` -- mix of active/stale connections, verify `stale_connections` field is accurate. (2) `test_status_includes_ttl` -- verify `connection_ttl_seconds` matches configured value. (3) `test_status_stale_count_is_zero_when_all_active` -- all connections within TTL, stale_connections is 0.

**Checkpoint**: Status endpoint provides full observability into connection pool health.

---

## Phase 5: Thread-Safety and Edge Cases

**Purpose**: Extend thread-safety tests and cover edge cases.

- [ ] T013 Write thread-safety tests in `test_connection_cleanup.py` with class `TestSweepThreadSafety`: (1) `test_concurrent_acquire_with_stale_sweep` -- 50 threads call `acquire()` simultaneously on a pool with 50 stale entries. Verify no exceptions, count is consistent, no duplicates. (2) `test_concurrent_sweep_and_release` -- one thread calls `sweep_stale()` while another calls `release()` on the same connection. Verify no exceptions, count is 0.
- [ ] T014 Write edge case tests in `test_connection_cleanup.py` with class `TestSweepEdgeCases`: (1) `test_sweep_empty_pool` -- sweep on empty manager returns 0. (2) `test_sweep_all_connections_stale` -- all 100 connections stale, sweep removes all, count is 0. (3) `test_ttl_boundary_exact` -- connection at exactly TTL seconds is NOT swept (boundary is strictly greater than). (4) `test_custom_ttl_via_env_var` -- set `SSE_CONNECTION_TTL` env var, verify manager uses it.

**Checkpoint**: Thread-safety preserved under all concurrent scenarios. Edge cases covered.

---

## Phase 6: Validation and Polish

- [ ] T015 Run `make validate` -- verify linting, formatting, security checks pass for modified files
- [ ] T016 Run existing SSE streaming tests `pytest tests/unit/sse_streaming/ -v` -- verify no regressions in existing test_connection.py, test_connection_limit.py, or other SSE tests
- [ ] T017 Run new tests `pytest tests/unit/sse_streaming/test_connection_cleanup.py -v` -- verify all new tests pass

---

## Dependencies & Execution Order

```
Phase 1: Liveness Tracking (T001-T003)
    | (BLOCKS ALL)
Phase 2: TTL + Sweep (T004-T006)
    |
Phase 3: Sweep on Acquire (T007-T008) -- MVP
    |
Phase 4: Status Endpoint (T009-T012) -- can run in parallel with Phase 5
Phase 5: Thread-Safety (T013-T014)    -- can run in parallel with Phase 4
    |
Phase 6: Validation (T015-T017)
```

Phases 4 and 5 are independent and can be developed in parallel.

---

## Implementation Strategy

### MVP (Phases 1-3)

1. Phase 1: `last_activity` tracking (T001-T003)
2. Phase 2: TTL config + `sweep_stale()` (T004-T006)
3. Phase 3: Wire into `acquire()` (T007-T008)
4. **STOP**: Connection leak is fixed. Pool self-heals on next `acquire()`.

### Full Delivery

- 17 tasks total
- 2 source files modified: `connection.py` (~40 lines added), `models.py` (~4 lines added)
- 1 new test file: `test_connection_cleanup.py` (~200 lines)
- 1 existing test file extended: `test_connection.py` (~10 lines added)
- 0 changes to handler.py or stream.py
