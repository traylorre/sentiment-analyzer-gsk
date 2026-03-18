# Feature Specification: Metrics Cache Max Entries Eviction Test

**Feature Branch**: `001-metrics-cache-bounds-test`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Feature 1224.2 — Metrics Cache Max Entries Eviction Test

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bounded Cache Regression Detection (Priority: P1)

A developer modifies the metrics cache and accidentally removes the max_entries bound or LRU eviction logic. The test suite catches the regression — a dedicated test fills the cache beyond the limit and asserts that the oldest entry was evicted and the cache size never exceeds the configured maximum.

**Why this priority**: The metrics cache was previously unbounded (FR-008 from Feature 1224). Without this test, the bound can be silently removed, re-introducing the unbounded growth bug.

**Independent Test**: Fill the metrics cache with entries exceeding max_entries and verify eviction occurs.

**Acceptance Scenarios**:

1. **Given** the metrics cache is filled to its maximum capacity, **When** a new entry is added, **Then** the oldest entry is evicted and the cache size equals max_entries.
2. **Given** the eviction counter exists, **When** eviction occurs, **Then** the eviction counter increments.

### Edge Cases

- What if max_entries is set to 1? The cache should still function (store 1, evict on 2nd).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test MUST verify that adding entries beyond max_entries triggers LRU eviction.
- **FR-002**: Test MUST verify cache size never exceeds max_entries after insertion.
- **FR-003**: Test MUST verify eviction counter increments on eviction.
- **FR-004**: Test MUST NOT modify production code — test-only change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Test passes when LRU eviction is present and fails when eviction logic is removed.
- **SC-002**: All existing tests continue to pass.
