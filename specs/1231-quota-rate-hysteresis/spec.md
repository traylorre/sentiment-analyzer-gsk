# Feature Specification: Quota Tracker Reduced-Rate Mode Hysteresis

**Feature Branch**: `1231-quota-rate-hysteresis`
**Created**: 2026-03-21
**Status**: Draft
**Input**: User description: "Quota tracker reduced-rate mode oscillation -- the 25% reduced-rate mode enters on DynamoDB failure and exits when DynamoDB becomes reachable. But _exit_reduced_rate_mode() is called inside _sync_to_dynamodb() which is called on every record_call(). If DynamoDB is intermittently failing (flapping), the system oscillates between 25% and 100% on every call. No dampening/hysteresis. Fix: add a stability window."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stable Mode Transitions During DynamoDB Flapping (Priority: P1)

The quota tracker manages API call rates across Tiingo, Finnhub, and SendGrid. When DynamoDB becomes unreachable, the tracker enters a 25% reduced-rate mode to prevent quota overages. Currently, if DynamoDB connectivity is intermittent (flapping), the tracker oscillates between 25% and 100% rate on every single API call -- one call succeeds (exits reduced mode), the next fails (re-enters reduced mode). This means the effective rate limit is unpredictable and the system generates excessive log noise.

With this fix, the tracker requires N consecutive successful DynamoDB syncs before exiting reduced-rate mode, and N consecutive failures before entering it. This prevents mode oscillation during transient connectivity issues and provides predictable rate limiting behavior.

**Why this priority**: Oscillation defeats the purpose of reduced-rate mode. If the system flips between 25% and 100% every call, the effective rate is ~62.5% -- neither the safe 25% nor the full 100%. Operators cannot reason about system behavior during incidents.

**Independent Test**: Can be fully tested with unit tests using a mock DynamoDB table that alternates between success and failure. Verify mode stays stable during flapping.

**Acceptance Scenarios**:

1. **Given** DynamoDB is flapping (alternating success/failure), **When** record_call() is called repeatedly, **Then** the tracker does NOT oscillate between reduced and normal mode on every call.
2. **Given** the tracker is in normal mode, **When** N consecutive DynamoDB failures occur, **Then** the tracker enters reduced-rate mode.
3. **Given** the tracker is in reduced-rate mode, **When** N consecutive DynamoDB successes occur, **Then** the tracker exits reduced-rate mode.
4. **Given** the tracker is in reduced-rate mode and has accumulated (N-1) consecutive successes, **When** a single DynamoDB failure occurs, **Then** the success counter resets and the tracker remains in reduced-rate mode.

---

### User Story 2 - Operations Visibility into Mode Transitions (Priority: P2)

The operations team needs clear, non-noisy logs showing when the tracker enters or exits reduced-rate mode, including the hysteresis counters. During flapping, the current code logs "Entering reduced-rate mode" and "Exiting reduced-rate mode" on every other call, drowning out meaningful signals.

With hysteresis, mode transitions are rare events that indicate genuine state changes, making each log line actionable.

**Why this priority**: Log noise from oscillation masks real problems. When every other line is a mode transition, operators ignore them. Rare, stable transitions are meaningful signals.

**Independent Test**: Can be tested by examining log output during simulated flapping. Verify transition logs only appear when mode actually changes (after N consecutive events).

**Acceptance Scenarios**:

1. **Given** DynamoDB is flapping, **When** record_call() is called 20 times, **Then** the "Entering reduced-rate mode" and "Exiting reduced-rate mode" log messages appear at most once each (not 10 times each).
2. **Given** the tracker transitions from normal to reduced-rate mode, **When** the log is emitted, **Then** it includes the number of consecutive failures that triggered the transition.
3. **Given** the tracker transitions from reduced-rate to normal mode, **When** the log is emitted, **Then** it includes the number of consecutive successes and the total duration in reduced-rate mode.

---

### Edge Cases

- **Rapid flapping (alternating success/failure every call)**: The tracker stays in whichever mode it was in. Neither N consecutive successes nor N consecutive failures accumulate.
- **Long outage (all failures)**: After N consecutive failures, the tracker enters reduced-rate mode and stays there. The failure counter stops being relevant since we are already in reduced mode.
- **Clean recovery (outage then all successes)**: After N consecutive successes, the tracker exits reduced-rate mode. The previous outage duration is logged.
- **Near-threshold recovery with interruption**: If (N-1) consecutive successes are followed by a failure, the success counter resets to zero. The tracker stays in reduced-rate mode.
- **Near-threshold failure with recovery**: If (N-1) consecutive failures are followed by a success, the failure counter resets to zero. The tracker stays in normal mode.
- **Application restart**: Counters reset to zero, mode resets to normal (existing behavior via module globals). This is acceptable because restart implies a fresh connection attempt.
- **Configurable threshold**: The threshold N is configurable via environment variable to allow tuning without code changes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST require N consecutive DynamoDB failures before entering reduced-rate mode, where N defaults to 3 and is configurable via the `QUOTA_RATE_STABILITY_THRESHOLD` environment variable.
- **FR-002**: The system MUST require N consecutive DynamoDB successes before exiting reduced-rate mode, using the same threshold N.
- **FR-003**: A single success during failure accumulation MUST reset the consecutive failure counter to zero.
- **FR-004**: A single failure during success accumulation MUST reset the consecutive success counter to zero.
- **FR-005**: Log messages for mode transitions MUST include the counter value that triggered the transition and (for exit) the duration spent in reduced-rate mode.
- **FR-006**: The `clear_quota_cache()` function MUST reset hysteresis counters alongside existing state, preserving test isolation.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: During simulated DynamoDB flapping (50% failure rate), mode transitions occur zero times if failures and successes alternate, vs. the current behavior of transitioning on every call.
- **SC-002**: After N consecutive failures from normal mode, the tracker enters reduced-rate mode within one call (no delay beyond the threshold).
- **SC-003**: After N consecutive successes from reduced-rate mode, the tracker exits reduced-rate mode within one call.
- **SC-004**: All existing quota tracker tests continue to pass with no modifications (backward compatibility).
- **SC-005**: Log output during a 20-call flapping simulation contains at most 2 mode transition messages (one enter, one exit), vs. the current ~20 messages.

## Assumptions

- The default threshold of 3 consecutive events provides sufficient dampening for typical DynamoDB connectivity patterns.
- The existing `clear_quota_cache()` function is the appropriate place to reset hysteresis state (used by test fixtures).
- Both entry and exit thresholds use the same N value for simplicity; separate thresholds can be added later if needed.
- Thread-safety is maintained through the existing `_quota_cache_lock` (RLock) that already protects mode transition functions.
