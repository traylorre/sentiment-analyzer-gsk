# Feature Specification: Fix Latency Timing in Traffic Generator

**Feature Branch**: `066-fix-latency-timing`
**Created**: 2025-12-08
**Status**: Draft
**Input**: User description: "Resolve test_very_long_latency Timing Failure - Fix time.time() usage in traffic_generator.py"

## Problem Statement

The test `test_very_long_latency` in `tests/unit/interview/test_traffic_generator.py` fails intermittently with negative latency values (-1362ms) instead of the expected positive values (>=100ms). Investigation revealed this is not a flaky test but a constitution violation in the source code.

### Root Cause

The source file `interview/traffic_generator.py` uses `time.time()` for latency calculations (lines 124, 135). This violates the project constitution (lines 328, 365) which explicitly prohibits `time.time()` for timing assertions due to:

- `time.time()` returns wall clock time that can jump backward during NTP sync or system clock adjustments
- `time.monotonic()` is immune to system clock adjustments and provides reliable elapsed time measurements

### Evidence

- Test expects `generator.stats.total_latency_ms >= 100` after 100ms sleep
- Actual result: -1362ms (negative latency impossible in real monotonic time)
- Constitution explicitly prohibits `time.time()` in tests: "No tests use `date.today()`, `datetime.now()`, `time.time()`, or `datetime.utcnow()` for assertions"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reliable Latency Tracking (Priority: P1)

As a developer running the test suite, I want latency measurements to be consistent and reliable so that tests pass deterministically regardless of system clock behavior.

**Why this priority**: This is the core fix - without reliable timing, the test suite is unreliable and blocks CI/CD pipelines.

**Independent Test**: Can be fully tested by running `test_very_long_latency` multiple times and verifying consistent positive latency values.

**Acceptance Scenarios**:

1. **Given** a request that takes 100ms to complete, **When** the latency is measured, **Then** the recorded latency is approximately 100ms (positive value within tolerance)
2. **Given** a system clock change during a request, **When** the latency is measured, **Then** the recorded latency is still accurate (monotonic time is unaffected)
3. **Given** multiple concurrent requests, **When** latencies are measured, **Then** all latencies are positive and consistent

---

### User Story 2 - Constitution Compliance (Priority: P2)

As a maintainer, I want the codebase to comply with the project constitution so that timing-related tests are reliable across all environments.

**Why this priority**: Ensures long-term codebase health and prevents similar issues in the future.

**Independent Test**: Can be verified by searching for `time.time()` usage in timing-critical code and confirming none exist.

**Acceptance Scenarios**:

1. **Given** the codebase, **When** I search for `time.time()` in latency/timing code, **Then** no instances are found
2. **Given** the constitution's timing guidelines, **When** I review `traffic_generator.py`, **Then** it uses `time.monotonic()` for elapsed time measurements

---

### Edge Cases

- What happens when a request completes instantly (0ms)? Latency should be 0 or very small positive value.
- What happens when a request takes very long (>10 seconds)? Latency should accurately reflect the duration.
- What happens when `time.monotonic()` overflows? Not a concern for practical durations (monotonic clock is reliable for process lifetime).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST use `time.monotonic()` instead of `time.time()` for all elapsed time measurements in `traffic_generator.py`
- **FR-002**: System MUST record positive latency values for all completed requests
- **FR-003**: System MUST measure latency accurately within reasonable tolerance (e.g., +/- 10ms for 100ms operations)
- **FR-004**: System MUST NOT be affected by system clock changes during latency measurement

### Key Entities

- **TrafficGeneratorStats**: Contains `total_latency_ms` field that accumulates measured latencies
- **Request timing**: Start time captured before request, end time captured after response

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `test_very_long_latency` passes consistently (100% pass rate over 10 consecutive runs)
- **SC-002**: No `time.time()` usage exists in `traffic_generator.py` for timing calculations
- **SC-003**: All unit tests pass with no regression (existing test count maintained)
- **SC-004**: Latency values are always positive when measured

## Assumptions

- The fix requires changing only `traffic_generator.py` source code, not the test itself
- `time.monotonic()` is available in Python 3.3+ (codebase uses Python 3.13)
- The change is purely internal and does not affect the public API of `TrafficGenerator`

## Methodology Consideration

This failure class (time.time() in production code affecting test reliability) may warrant a new methodology via `/add-methodology` to detect `time.time()` usage in timing-critical code paths. This could prevent similar issues in the future by adding automated detection during validation.
