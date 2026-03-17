# Feature Specification: CacheStats Wiring Integration Tests

**Feature Branch**: `001-cachestats-wiring-tests`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Feature 1224.3 — CacheStats Wiring Integration Tests

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CacheStats Wiring Regression Detection (Priority: P1)

A developer modifies a cache module and accidentally removes the `record_hit()` or `record_miss()` call. The test suite catches the regression — a dedicated test for each cache exercises the hit/miss path and asserts the module-level CacheStats instance incremented.

**Why this priority**: Without these tests, CacheStats wiring removal is silent. CloudWatch metrics would stop flowing for that cache with no test failure.

**Independent Test**: Exercise each cache's hit and miss paths, then inspect the CacheStats counter.

**Acceptance Scenarios**:

1. **Given** a cache hit occurs, **When** the test checks the CacheStats instance, **Then** the hits counter has incremented.
2. **Given** a cache miss occurs, **When** the test checks the CacheStats instance, **Then** the misses counter has incremented.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST verify CacheStats.hits increments on cache hit for each wired cache.
- **FR-002**: Test suite MUST verify CacheStats.misses increments on cache miss for each wired cache.
- **FR-003**: Tests MUST cover all 8 caches with CacheStats wiring: circuit_breaker, tiingo, finnhub, secrets, metrics, sentiment, config, ohlc_response.
- **FR-004**: Tests MUST NOT modify production code — test-only change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 8 caches have CacheStats hit/miss wiring verified by tests.
- **SC-002**: Removing a `record_hit()` or `record_miss()` call from any cache causes a test failure.
- **SC-003**: All existing tests continue to pass.
