# Tasks: SSE In-Memory State Validation

**Input**: Design documents from `/specs/1231-sse-state-validation/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Included per constitution requirement.

**Organization**: Bottom-up — models and introspection methods first, then validator, then handler wiring, then tests.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Foundational — Models and Introspection Methods

**Purpose**: Add the data models and per-component introspection methods that the StateValidator will call.

- [ ] T001 Add `IntegrityCheck` and `IntegrityReport` pydantic models to `src/lambdas/sse_streaming/models.py` — `IntegrityCheck` has fields: `connection_pool: str` (ok | phantom_connections_detected | pool_reset), `event_buffer: str` (ok | corrupted_entries_detected | buffer_cleared), `debouncer: str` (ok | stale_keys_detected | future_timestamps_reset); `IntegrityReport` has fields: `status: str` (healthy | degraded | reset), `checks: IntegrityCheck`, `last_validated: datetime | None`, `resets_since_start: int`; extend `StreamStatus` with `integrity: IntegrityReport | None = None`
- [ ] T002 Add `purge_phantom_connections(threshold_seconds: float = 900)` method to `ConnectionManager` in `src/lambdas/sse_streaming/connection.py` — iterate `_connections`, find entries where `(now - connected_at).total_seconds() > threshold_seconds`, remove them, return count of purged connections; use existing `_lock` for thread safety
- [ ] T003 Add `get_connection_ages()` method to `ConnectionManager` in `src/lambdas/sse_streaming/connection.py` — return `dict[str, float]` mapping connection_id to age in seconds; used by validator for reporting
- [ ] T004 Add `check_integrity(start_time: float)` method to `EventBuffer` in `src/lambdas/sse_streaming/stream.py` — iterate `_buffer`, remove entries where: (a) `event.id` doesn't match `evt_` prefix pattern, or (b) entry was added before `start_time` (use a `_added_at` timestamp dict alongside `_buffer`); return count of purged entries
- [ ] T005 Add `_added_at: dict[str, float]` tracking dict to `EventBuffer.__init__()` in `src/lambdas/sse_streaming/stream.py`; update `add()` to record `time.time()` keyed by `event.id`; update `clear()` to also clear `_added_at`; trim `_added_at` in tandem with `_buffer` when max_size exceeded
- [ ] T006 Add future-timestamp guard to `Debouncer.should_emit()` in `src/lambdas/sse_streaming/stream.py` — before the existing comparison, check `if last_emit > current_time: self._last_emit.pop(key, None)` and return `True` (allow emission); this self-heals corrupted timestamps
- [ ] T007 Add `check_integrity(max_age_seconds: float)` method to `Debouncer` in `src/lambdas/sse_streaming/stream.py` — iterate `_last_emit`, remove entries older than `max_age_seconds` or with future timestamps; return count of entries removed

**Checkpoint**: All introspection/purge methods exist on their respective classes. No handler changes yet.

---

## Phase 2: StateValidator Module (User Story 1) — Core Validation

**Goal**: Central validator that orchestrates per-component checks.

- [ ] T008 [US1] Create `src/lambdas/sse_streaming/state_validator.py` with `StateValidator` class — constructor takes `conn_manager: ConnectionManager`, `stream_gen_fn: Callable` (the `get_stream_generator` function), `metrics: MetricsEmitter`; instance vars: `_resets_since_start: int = 0`, `_last_validated: datetime | None = None`, `_phantom_threshold: float = 900.0` (15 min), `_debounce_max_age: float` (2x heartbeat interval, read from `SSE_HEARTBEAT_INTERVAL` env or default 60s)
- [ ] T009 [US1] Implement `validate_state()` method in `StateValidator` — calls `_check_connection_pool()`, `_check_event_buffer()`, `_check_debouncer()` in sequence; measures total elapsed time via `time.perf_counter()`; if elapsed > 5ms, logs warning with elapsed_ms; updates `_last_validated` and `_resets_since_start`; emits `StateValidation/DurationMs` metric; returns `bool` (True if any resets occurred)
- [ ] T010 [US1] Implement `_check_connection_pool()` in `StateValidator` — calls `conn_manager.purge_phantom_connections(self._phantom_threshold)`; if purge_count > 0, logs warning with count and emits `StateValidation/PhantomConnectionsPurged` metric; returns `bool`
- [ ] T011 [US1] Implement `_check_event_buffer()` in `StateValidator` — calls `get_stream_generator()._event_buffer.check_integrity(get_stream_generator()._start_time)`; if purge_count > 0, logs warning and emits `StateValidation/BufferEntriesPurged` metric; returns `bool`
- [ ] T012 [US1] Implement `_check_debouncer()` in `StateValidator` — calls `get_stream_generator()._debouncer.check_integrity(self._debounce_max_age)`; if reset_count > 0, logs warning and emits `StateValidation/DebouncerKeysReset` metric; returns `bool`

**Checkpoint**: `StateValidator` can validate all singletons and emit metrics. Not yet wired into handler.

---

## Phase 3: Health Endpoint Extension (User Story 2) — Integrity Reporting

**Goal**: `/api/v2/stream/status` reports state integrity.

- [ ] T013 [US2] Implement `get_integrity()` method in `StateValidator` — builds `IntegrityReport` from current state: runs lightweight read-only checks (counts, not purges) on each component; sets `status` to "healthy" if all checks pass, "degraded" if any anomalies detected, "reset" if resets occurred since last check; populates `checks` with per-component status strings; includes `last_validated` timestamp and `resets_since_start` counter
- [ ] T014 [US2] Add module-level `get_state_validator()` lazy initializer in `state_validator.py` — follows same pattern as `get_stream_generator()` in `stream.py`; returns singleton `StateValidator` instance
- [ ] T015 [US2] Modify `_handle_stream_status()` in `handler.py` — import `get_state_validator`; call `get_state_validator().get_integrity()`; pass result to `StreamStatus(..., integrity=integrity_report)`

**Checkpoint**: `/api/v2/stream/status` includes `integrity` section.

---

## Phase 4: Handler Wiring — Per-Connection Validation

**Goal**: Every new connection triggers state validation before acquiring a slot.

- [ ] T016 [US1] Add `validate_state()` call in `_handle_global_stream()` in `handler.py` — before `connection_manager.acquire()`, call `get_state_validator().validate_state()`; log result if resets occurred
- [ ] T017 [US1] Add `validate_state()` call in `_handle_config_stream()` in `handler.py` — same pattern as T016, before `connection_manager.acquire()`
- [ ] T018 [US1] Add lightweight heartbeat-cycle check in `SSEStreamGenerator.generate_global_stream()` in `stream.py` — inside the heartbeat emission block (when `current_time - last_heartbeat >= self._heartbeat_interval`), call `get_state_validator().validate_state()` wrapped in try/except (validation failure must not kill the stream)
- [ ] T019 [US1] Add lightweight heartbeat-cycle check in `SSEStreamGenerator.generate_config_stream()` in `stream.py` — same pattern as T018

**Checkpoint**: All connection paths and heartbeat cycles trigger validation.

---

## Phase 5: Tests

**Goal**: Full test coverage for validation logic.

- [ ] T020 Write `tests/unit/test_state_validator.py` — test `StateValidator._check_connection_pool()`: create `ConnectionManager`, acquire a connection, manually set `connected_at` to 20 minutes ago, call `validate_state()`, assert connection was purged and metric was emitted
- [ ] T021 Write test for event buffer integrity — create `EventBuffer`, add events, manually insert an entry with `_added_at` timestamp before `_start_time`, call `check_integrity()`, assert corrupted entry was removed and valid entries remain
- [ ] T022 Write test for debouncer future timestamp — create `Debouncer`, manually set `_last_emit["AAPL#5m"]` to `time.time() + 3600` (1 hour in the future), call `should_emit("AAPL#5m")`, assert it returns `True` (future timestamp was reset and emission allowed)
- [ ] T023 Write test for debouncer stale key trimming — create `Debouncer`, set `_last_emit` with 100 keys all older than max_age, call `check_integrity()`, assert all stale keys were removed
- [ ] T024 Write test for health endpoint integrity reporting — mock `ConnectionManager` with phantom connections, call `get_integrity()`, assert response has `status: "degraded"` and `checks.connection_pool: "phantom_connections_detected"`
- [ ] T025 Write test for healthy state (no false positives) — create fresh `ConnectionManager`, `EventBuffer`, `Debouncer` with normal state, call `validate_state()`, assert returns `False` (no resets); call `get_integrity()`, assert `status: "healthy"`
- [ ] T026 Write test for validation timeout warning — mock `time.perf_counter()` to simulate 10ms elapsed, call `validate_state()`, assert warning was logged

**Checkpoint**: All validation paths tested. `make test-local` passes.

---

## Phase 6: Polish

- [ ] T027 Run `make validate` — verify linting, formatting pass for all modified and new files
- [ ] T028 Run `make test-local` — verify all tests pass including new state validation tests
- [ ] T029 Manual verification: inject phantom connections via test harness, hit `/api/v2/stream/status`, confirm `integrity.status` reports `degraded`, then establish new SSE connection and confirm phantoms are purged

---

## Dependencies & Execution Order

```
Phase 1: Models + Introspection (T001-T007)
    ↓ (BLOCKS Phase 2 + 3)
Phase 2: StateValidator (T008-T012)
    ↓
Phase 3: Health Endpoint (T013-T015) ← can start after T001
    ↓
Phase 4: Handler Wiring (T016-T019) ← needs Phase 2 + 3
    ↓
Phase 5: Tests (T020-T026) ← needs Phase 1-4
    ↓
Phase 6: Polish (T027-T029)
```

Phase 1 blocks everything. Phases 2 and 3 can partially overlap (T013 needs T008).

---

## Implementation Strategy

### MVP (User Story 1 Only)

1. Phase 1: Models + introspection methods (T001-T007)
2. Phase 2: StateValidator core (T008-T012)
3. Phase 4: Handler wiring (T016-T017, skip T018-T019 heartbeat checks)
4. Phase 5: Core tests (T020-T023, T025)
5. **STOP**: Per-connection validation works, phantoms are purged, corrupted state is reset

### Full Delivery

- 29 tasks total
- 1 new file: `src/lambdas/sse_streaming/state_validator.py` (~150 lines)
- 4 modified files: `connection.py`, `stream.py`, `models.py`, `handler.py`
- 1 new test file: `tests/unit/test_state_validator.py` (~200 lines)
