# Implementation Plan: SSE Connection Leak Cleanup

**Branch**: `1231-sse-connection-cleanup` | **Date**: 2026-03-21 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/1231-sse-connection-cleanup/spec.md`

## Summary

Fix SSE connection pool leak under chaos (force-kill) by adding connection TTL and stale connection sweep. Connections track `last_activity` timestamps, `acquire()` sweeps stale entries before capacity check, and the status endpoint reports stale connection counts for observability.

## Technical Context

**Language/Version**: Python 3.13 (existing project standard)
**Primary Dependencies**: No new packages. Uses `datetime`, `time`, `threading` (all existing stdlib imports in `connection.py`).
**Storage**: In-memory only (existing pattern -- ConnectionManager is per-Lambda-instance)
**Testing**: pytest with time mocking (`freezegun` or manual `datetime` patching)
**Target Platform**: AWS Lambda (custom runtime, `provided.al2023`)
**Project Type**: Bug fix / reliability improvement
**Performance Goals**: `sweep_stale()` runs in O(n) where n <= 100 -- negligible overhead on `acquire()`
**Constraints**: Must be backward-compatible with existing `ConnectionManager` API; no breaking changes to handler.py or stream.py
**Scale/Scope**: 2 source files modified, 1 model file modified, 1 new test file, 1 existing test file extended

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Implementation accompaniment (unit tests) | PASS | Tests for TTL, sweep, status endpoint, thread-safety |
| Deterministic time handling in tests | PASS | Mock `datetime.now(UTC)` and `time.time()` for deterministic TTL checks |
| External dependency mocking | PASS | No external dependencies added |
| GPG-signed commits | PASS | Standard workflow |
| Feature branch workflow | PASS | Branch `1231-sse-connection-cleanup` |
| SAST/lint pre-push | PASS | `make validate` |

No violations.

## Project Structure

### Documentation (this feature)

```text
specs/1231-sse-connection-cleanup/
├── spec.md
├── plan.md
├── research.md
├── quickstart.md
├── tasks.md
└── checklists/
    └── requirements.md
```

### Source Code (modified files)

```text
src/lambdas/sse_streaming/
├── connection.py          # MODIFIED: Add last_activity, sweep_stale(), TTL config
└── models.py              # MODIFIED: Add stale_connections, connection_ttl_seconds to StreamStatus

tests/unit/sse_streaming/
├── test_connection.py           # MODIFIED: Add TTL and sweep tests
└── test_connection_cleanup.py   # NEW: Dedicated cleanup/stale connection tests
```

**Structure Decision**: Modify existing source files in-place (connection.py, models.py). New test file for cleanup-specific tests to avoid bloating the existing test_connection.py. The handler.py and stream.py require NO changes -- the fix is entirely within ConnectionManager internals.

## Impact Analysis

### Files Changed

| File | Change | Risk |
|------|--------|------|
| `connection.py` | Add `last_activity` to SSEConnection, add `sweep_stale()`, modify `acquire()` and `update_last_event_id()`, modify `get_status()` | **Medium** -- core connection tracking. Mitigated by: existing thread-safety tests, new TTL tests, backward-compatible API |
| `models.py` | Add 2 fields to `StreamStatus` model | **Low** -- additive change, new fields have defaults |
| `test_connection.py` | Extend existing tests for `last_activity` and `get_status()` changes | **Low** -- test-only |
| `test_connection_cleanup.py` | New file with stale sweep, TTL, and edge case tests | **None** -- new test file |

### Files NOT Changed (and why)

| File | Reason |
|------|--------|
| `handler.py` | No changes needed. `connection_manager.release()` calls remain as-is. The `acquire()` change is internal to ConnectionManager. |
| `stream.py` | No changes needed. `update_last_event_id()` already called on every event dispatch. The internal change to also update `last_activity` is transparent. |
| `config.py` | No changes needed. Config lookup is unrelated. |
| `test_connection_limit.py` | Existing tests still pass -- `acquire()` behavior is additive (sweep before check). |
