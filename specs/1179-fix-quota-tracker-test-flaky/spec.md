# Feature Specification: Fix QuotaTracker Thread Safety Bug

**Feature Branch**: `1179-fix-quota-tracker-test-flaky`
**Created**: 2026-01-09
**Status**: Draft
**Input**: User description: "Fix flaky thread safety test test_different_services_can_be_updated_concurrently in tests/unit/shared/test_quota_tracker_threadsafe.py. Test expects 100 calls but got 52 due to race condition. This blocks Deploy Pipeline."

## Problem Statement

The `QuotaTracker` component has a thread safety bug that causes lost updates when multiple threads concurrently record API calls for different services. This manifests as a flaky test in CI that blocks the Deploy Pipeline on main branch.

### Root Cause Analysis

The `record_call()` method performs an unprotected read-modify-write cycle:
1. Thread A reads cached tracker (tiingo=0, finnhub=0)
2. Thread B reads cached tracker (tiingo=0, finnhub=0)
3. Thread A modifies tiingo to 1, writes back
4. Thread B modifies finnhub to 1, writes back (overwrites Thread A's tiingo=1)
5. Result: tiingo=0, finnhub=1 (Thread A's update lost)

This is a classic read-modify-write race condition with stale cached objects.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accurate API Usage Tracking Under Concurrent Load (Priority: P1)

The system tracks API quota usage for multiple external services (Tiingo, Finnhub, SendGrid). When multiple ingestion workers run concurrently and call different APIs, each call must be accurately counted to prevent quota overruns and unexpected API costs.

**Why this priority**: Accurate quota tracking prevents production incidents where API rate limits are exceeded, causing service degradation and potential data loss.

**Independent Test**: Can be fully tested by spawning multiple threads that call `record_call()` for different services concurrently, then verifying all calls are accurately counted.

**Acceptance Scenarios**:

1. **Given** an empty quota tracker, **When** 100 threads each record 1 call to service A and 100 threads each record 1 call to service B concurrently, **Then** the tracker shows exactly 100 calls for service A and 100 calls for service B.

2. **Given** an existing quota tracker with 50 calls recorded for service A, **When** 50 additional calls are recorded concurrently across 50 threads, **Then** the tracker shows exactly 100 calls for service A with zero lost updates.

3. **Given** concurrent operations on multiple different services, **When** calls are recorded simultaneously, **Then** updates to one service never overwrite or lose updates to another service.

---

### User Story 2 - Thread-Safe Quota State Reads (Priority: P2)

When checking quota availability while other threads are recording calls, the system must return consistent state without data corruption or stale reads that could lead to incorrect quota decisions.

**Why this priority**: Inconsistent reads could cause the system to exceed quotas (if reads show too few calls) or unnecessarily throttle (if reads show too many calls).

**Independent Test**: Can be tested by having reader threads continuously check quota state while writer threads record calls, verifying read results are always consistent (no partial updates visible).

**Acceptance Scenarios**:

1. **Given** writers recording calls and readers checking quota simultaneously, **When** a reader checks quota state, **Then** the returned count is always a valid snapshot (either before or after any given write, never partial).

2. **Given** high contention with many concurrent readers and writers, **When** the system operates under load, **Then** no exceptions, deadlocks, or data corruption occur.

---

### User Story 3 - Reliable CI Pipeline (Priority: P1)

The Deploy Pipeline must pass consistently without flaky test failures. The thread safety tests must deterministically pass when the underlying implementation is correct.

**Why this priority**: Flaky tests block deployments, waste developer time investigating false failures, and erode confidence in the test suite.

**Independent Test**: Run the thread safety test suite 100 times consecutively; all runs must pass.

**Acceptance Scenarios**:

1. **Given** the fixed QuotaTracker implementation, **When** `test_different_services_can_be_updated_concurrently` runs, **Then** it passes 100% of the time (100 consecutive runs).

2. **Given** the fixed implementation, **When** the full thread safety test suite runs in CI, **Then** all tests pass without any flakiness.

---

### Edge Cases

- What happens when the cache is cleared while a thread is in the middle of record_call()?
- How does the system handle contention when the critical threshold is reached mid-operation?
- What happens if sync_to_dynamodb() is called while record_call() is in progress?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accurately count all API calls recorded via `record_call()` regardless of concurrent access patterns
- **FR-002**: System MUST NOT lose updates when multiple threads call `record_call()` for different services simultaneously
- **FR-003**: System MUST provide atomic read-modify-write semantics for quota updates
- **FR-004**: System MUST maintain thread safety across all public methods of QuotaTrackerManager
- **FR-005**: System MUST NOT introduce deadlocks under any concurrent access pattern
- **FR-006**: System MUST preserve backward compatibility - existing callers require no changes

### Non-Functional Requirements

- **NFR-001**: Lock contention overhead MUST NOT degrade single-threaded performance by more than 5%
- **NFR-002**: Solution MUST NOT require callers to change their usage patterns

### Key Entities

- **QuotaTracker**: Immutable data model holding usage counts for each service (tiingo, finnhub, sendgrid)
- **QuotaTrackerManager**: Manager class providing thread-safe access to cached QuotaTracker state
- **_quota_cache_lock**: Module-level lock protecting cache access (needs expanded scope)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Test `test_different_services_can_be_updated_concurrently` passes 100 consecutive times without failure
- **SC-002**: All existing thread safety tests continue to pass without modification
- **SC-003**: No new test flakiness introduced in the quota_tracker test suite
- **SC-004**: Deploy Pipeline on main branch succeeds after the fix is merged
- **SC-005**: Single-threaded quota tracking operations complete within 5% of current performance

## Assumptions

- The existing `_quota_cache_lock` can be extended to protect the full read-modify-write cycle
- Callers do not depend on specific timing or ordering of cache updates
- The fix will be applied to `QuotaTrackerManager.record_call()` method
- Python's threading.Lock is sufficient (no need for RLock based on current code analysis)

## Out of Scope

- Refactoring QuotaTracker to use immutable updates (copy-on-write pattern)
- Adding distributed locking for multi-process scenarios
- Performance optimization of the locking strategy
- Changes to the DynamoDB sync behavior
