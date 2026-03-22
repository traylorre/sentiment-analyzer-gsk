# Design Plan: Quota Tracker Reduced-Rate Mode Hysteresis

**Input**: [spec.md](spec.md)
**Created**: 2026-03-21

## Problem Analysis

The quota tracker's reduced-rate mode (25% of normal) enters on any DynamoDB failure and exits on any success. The entry/exit functions (`_enter_reduced_rate_mode()` and `_exit_reduced_rate_mode()`) are called on every `record_call()` and `get_tracker()` invocation. When DynamoDB connectivity flaps (intermittent failures), the system oscillates between 25% and 100% rate on every call.

### Current Call Flow (Oscillation)

```
record_call()
  -> _atomic_increment_usage() SUCCESS -> _exit_reduced_rate_mode()  # exits immediately
  -> _atomic_increment_usage() FAIL    -> _enter_reduced_rate_mode() # enters immediately

get_tracker()
  -> table.get_item() SUCCESS -> _exit_reduced_rate_mode()  # exits immediately
```

Each success/failure immediately toggles the mode with zero dampening.

### Fixed Call Flow (Hysteresis)

```
record_call()
  -> _atomic_increment_usage() SUCCESS -> _record_dynamo_success()
     -> if consecutive_successes >= N and in reduced mode: _exit_reduced_rate_mode()
  -> _atomic_increment_usage() FAIL    -> _record_dynamo_failure()
     -> if consecutive_failures >= N and not in reduced mode: _enter_reduced_rate_mode()
```

## Design

### New Module-Level State

Add three module-level globals (protected by existing `_quota_cache_lock`):

- `_consecutive_successes: int = 0` -- reset on any failure
- `_consecutive_failures: int = 0` -- reset on any success
- `QUOTA_RATE_STABILITY_THRESHOLD: int` -- configurable via env var, default 3

### New Functions

- `_record_dynamo_success()`: Increment `_consecutive_successes`, reset `_consecutive_failures` to 0. If `_consecutive_successes >= N` and currently in reduced mode, call `_exit_reduced_rate_mode()`.
- `_record_dynamo_failure()`: Increment `_consecutive_failures`, reset `_consecutive_successes` to 0. If `_consecutive_failures >= N` and not currently in reduced mode, call `_enter_reduced_rate_mode()`.

### Modified Functions

- `record_call()`: Replace direct calls to `_enter/_exit_reduced_rate_mode()` with `_record_dynamo_success()` / `_record_dynamo_failure()`.
- `get_tracker()`: Replace direct call to `_exit_reduced_rate_mode()` with `_record_dynamo_success()`.
- `clear_quota_cache()`: Reset `_consecutive_successes` and `_consecutive_failures` to 0.
- `_enter_reduced_rate_mode()`: Add consecutive failure count to log message.
- `_exit_reduced_rate_mode()`: Add consecutive success count to log message.

### Thread Safety

All new state is protected by the existing `_quota_cache_lock` RLock. The `_record_dynamo_success/failure` functions acquire the lock, and the `_enter/_exit` functions they call also acquire it (safe because RLock is reentrant).

## Files Changed

| File | Change |
|------|--------|
| `src/lambdas/shared/quota_tracker.py` | Add hysteresis globals, new functions, modify existing functions |
| `tests/unit/test_quota_tracker_hysteresis.py` | New test file for hysteresis behavior |

## Risk Assessment

- **Low risk**: Change is additive -- new globals and functions, minimal modification to existing logic.
- **Backward compatible**: `clear_quota_cache()` resets new state, so all existing tests remain isolated.
- **Default threshold of 3**: Conservative enough to prevent oscillation, aggressive enough to react within seconds.
