# Research: Quota Tracker Reduced-Rate Mode Hysteresis

**Created**: 2026-03-21
**Feature**: 1231-quota-rate-hysteresis

## Codebase Analysis

### Current Reduced-Rate Mode Implementation

**File**: `src/lambdas/shared/quota_tracker.py`

The reduced-rate mode was introduced in Feature 1224 (Cache Architecture Audit). It uses module-level globals:

- `_reduced_rate_mode: bool` -- whether reduced-rate is active
- `_reduced_rate_since: float | None` -- timestamp of entry
- `_last_disconnected_alert: float` -- spam protection for alert metrics
- `REDUCED_RATE_FRACTION = 0.25` -- 25% of normal rate

### Oscillation Root Cause

Two code paths trigger immediate mode transitions with no dampening:

1. **`record_call()` lines 603-611**: Every call to `_atomic_increment_usage()` either succeeds (calls `_exit_reduced_rate_mode()`) or fails (calls `_enter_reduced_rate_mode()`). During flapping, this toggles mode on every invocation.

2. **`get_tracker()` line 471**: Every cache miss that successfully reads DynamoDB calls `_exit_reduced_rate_mode()`. Combined with the 10s cache TTL, this adds another exit trigger.

### Thread Safety Considerations

The existing `_quota_cache_lock` (RLock) protects `_enter_reduced_rate_mode()` and `_exit_reduced_rate_mode()`. Any new hysteresis counters must also be protected by this lock. The RLock is reentrant, so nested acquisition (e.g., `_record_dynamo_success()` acquiring lock, then calling `_exit_reduced_rate_mode()` which also acquires) is safe.

### Test Infrastructure

Three existing test files exercise quota tracker:

- `tests/unit/shared/test_quota_tracker.py` -- Model tests (APIQuotaUsage, QuotaTracker)
- `tests/unit/shared/test_quota_tracker_threadsafe.py` -- Thread-safety tests
- `tests/unit/test_quota_tracker_atomic.py` -- Atomic increment, reduced-rate mode, alerts

All use `clear_quota_cache()` as an autouse fixture for isolation. The new hysteresis counters must be reset in `clear_quota_cache()` to maintain this contract.

### Existing Test for Reduced-Rate Mode (in test_quota_tracker_atomic.py)

The atomic test file already tests:
- Entering reduced-rate mode on DynamoDB failure
- Exiting reduced-rate mode on DynamoDB success
- Alert metric emission with spam protection

These tests will need the stability threshold set to 1 (via env var or by calling the failure/success recording function N times) OR the tests will naturally pass because they already trigger multiple consecutive events of the same type.

## Hysteresis Pattern Research

### Standard Hysteresis Approach

The classic hysteresis pattern uses two thresholds or a stability window:

1. **Counter-based**: Require N consecutive events in the same direction before transitioning. A single contrary event resets the counter. Simple, deterministic, testable.

2. **Time-window based**: Require sustained failure/success for T seconds. More complex, harder to test, time-dependent.

3. **Exponential backoff**: Increase the threshold after each oscillation. Complex, state-heavy.

**Chosen approach**: Counter-based (option 1). It is the simplest, most testable, and directly addresses the problem. A threshold of 3 means the system tolerates up to 2 transient failures before entering reduced mode, and requires 3 consecutive successes to exit.

### Threshold Selection

- **N=1**: Current behavior (no hysteresis). Oscillates during flapping.
- **N=3** (chosen default): Tolerates 2 transient blips. At typical call rates (~1 call/second for busiest service), this means ~3 seconds of sustained failure before mode change. Fast enough for genuine outages, slow enough to filter transients.
- **N=5**: More conservative. 5 seconds to react. May be too slow for genuine outages.
- **N=10**: Too conservative for a system that needs to protect quota within seconds.
