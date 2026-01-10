# Implementation Plan: Fix QuotaTracker Thread Safety Bug

**Branch**: `1179-fix-quota-tracker-test-flaky` | **Date**: 2026-01-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/1179-fix-quota-tracker-test-flaky/spec.md`

## Summary

Fix a thread safety bug in `QuotaTrackerManager.record_call()` that causes lost updates when multiple threads concurrently record API calls for different services. The fix involves extending the existing `_quota_cache_lock` to protect the entire read-modify-write cycle, ensuring atomic updates.

## Technical Context

**Language/Version**: Python 3.13
**Primary Dependencies**: pydantic (BaseModel), threading (Lock), boto3 (DynamoDB sync)
**Storage**: DynamoDB (for persistence), in-memory cache (for fast access)
**Testing**: pytest with concurrent.futures.ThreadPoolExecutor
**Target Platform**: AWS Lambda (Linux)
**Project Type**: Backend service (Lambda functions)
**Performance Goals**: Single-threaded performance within 5% of current
**Constraints**: No deadlocks, backward compatible API
**Scale/Scope**: High-concurrency ingestion workers (~100 concurrent threads in tests)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Thread safety (concurrency) | FIX REQUIRED | Current implementation has race condition |
| Idempotency | PASS | Not affected by this change |
| IAM least-privilege | N/A | No IAM changes |
| No raw SQL/injection | N/A | No database query changes |
| Secrets management | N/A | No secrets involved |

**Gate Status**: PASS (this feature is specifically fixing a thread safety violation)

## Project Structure

### Documentation (this feature)

```text
specs/1179-fix-quota-tracker-test-flaky/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Thread safety research
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
src/lambdas/shared/
└── quota_tracker.py     # Target file for fix

tests/unit/shared/
└── test_quota_tracker_threadsafe.py  # Existing tests (should pass after fix)
```

**Structure Decision**: Single file change in existing shared module. No new files needed.

## Design

### Current Code Analysis

The bug is in `QuotaTrackerManager.record_call()`:

```python
def record_call(self, service, count: int = 1) -> QuotaTracker:
    tracker = self.get_tracker()                    # Step 1: Read (unprotected)
    old_is_critical = getattr(tracker, service).is_critical
    tracker.record_call(service, count)             # Step 2: Modify (unprotected)
    _set_cached_tracker(tracker, synced=False)      # Step 3: Write (protected internally)
    # ... sync logic ...
```

**Problem**: Between Step 1 and Step 3, another thread can complete its own read-modify-write, and when Step 3 executes, it overwrites the other thread's changes.

### Solution

Wrap the entire read-modify-write cycle in `_quota_cache_lock`:

```python
def record_call(self, service, count: int = 1) -> QuotaTracker:
    with _quota_cache_lock:                         # Acquire lock
        tracker = self.get_tracker()                # Step 1: Read (protected)
        old_is_critical = getattr(tracker, service).is_critical
        tracker.record_call(service, count)         # Step 2: Modify (protected)
        _set_cached_tracker(tracker, synced=False)  # Step 3: Write (protected)
        new_is_critical = getattr(tracker, service).is_critical
    # Release lock before sync (sync has its own locking)

    # Critical threshold logging (outside lock)
    if new_is_critical and not old_is_critical:
        logger.warning(...)

    # Sync to DynamoDB (outside lock - has its own thread safety)
    self._maybe_sync()

    return tracker
```

### Key Design Decisions

1. **Single lock scope**: Use existing `_quota_cache_lock` rather than introducing new locks (avoids deadlock risk)

2. **Lock scope boundary**: Hold lock only during read-modify-write, release before DynamoDB sync
   - Sync is I/O-bound and has its own thread safety
   - Holding lock during sync would create unnecessary contention

3. **Return value**: Return the tracker after releasing lock (callers may hold stale reference, but this is existing behavior)

4. **No RLock needed**: Analysis shows no recursive locking patterns - standard Lock is sufficient

### Thread Safety Verification

After fix, the following guarantees hold:

1. **Atomicity**: Read-modify-write is atomic (protected by single lock)
2. **Visibility**: All threads see consistent state (lock provides memory barrier)
3. **No deadlocks**: Single lock with no nested acquisition
4. **Progress**: Lock is held for minimal time (microseconds)

## Complexity Tracking

No constitution violations to justify - this fix removes complexity (race condition) rather than adding it.

## Testing Strategy

### Existing Tests (must pass)

- `test_concurrent_record_calls_are_thread_safe` - 10 threads, same service
- `test_mixed_record_and_check_operations` - readers and writers
- `test_different_services_can_be_updated_concurrently` - **THE FAILING TEST**
- `test_get_all_states_under_contention` - read contention
- `test_cache_stats_are_thread_safe` - cache statistics
- `test_record_call_with_high_contention` - 50 threads stress test
- `test_critical_threshold_sync_under_contention` - sync with contention

### Verification Plan

1. Run `test_different_services_can_be_updated_concurrently` 100 times
2. Run full thread safety test suite
3. Run all quota_tracker unit tests
4. Verify Deploy Pipeline passes in CI

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased lock contention | Low | Low | Lock held for microseconds only |
| Deadlock introduced | Very Low | High | No nested locking, single lock |
| Performance regression | Low | Medium | Benchmark before/after |
| Breaking existing behavior | Very Low | High | All existing tests must pass |

## Out of Scope

- Refactoring to copy-on-write pattern
- Distributed locking for multi-process
- Performance optimization of locking
- Changes to DynamoDB sync behavior
