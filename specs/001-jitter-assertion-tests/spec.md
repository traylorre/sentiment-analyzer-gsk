# Feature Specification: Per-Cache Jitter Assertion Tests

**Feature Branch**: `001-jitter-assertion-tests`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Feature 1224.1 — Per-Cache Jitter Assertion Tests

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Jitter Regression Detection (Priority: P1)

A developer modifies a cache module and accidentally removes the jitter call. The test suite catches the regression immediately — a dedicated test for that cache asserts that stored TTL values fall within the expected jitter range rather than equaling the exact base TTL. The developer sees a clear failure message identifying which cache lost its jitter.

**Why this priority**: Without these tests, jitter removal is silent. The thundering herd protection from Feature 1224 can be unknowingly undone by any future edit to any of the 10 cache files.

**Independent Test**: Run the jitter integration test file and verify all 10 caches produce TTL values within the expected range (base TTL ± 10%).

**Acceptance Scenarios**:

1. **Given** a cache stores an entry with jittered TTL, **When** the test inspects the stored TTL, **Then** the TTL is within ±10% of the base TTL but not exactly equal to it (over multiple samples).
2. **Given** a developer removes the jitter call from a cache, **When** the test suite runs, **Then** the test for that cache fails with a clear message identifying the cache and expected range.
3. **Given** all 10 caches have jitter applied, **When** the full test suite runs, **Then** all jitter assertion tests pass.

---

### Edge Cases

- What if the jitter percentage is set to 0 via environment variable? Tests should still pass since 0% jitter produces exact TTL values (tests assert range, not inequality).
- What if random.seed produces a value exactly at the boundary? Tests use range assertions (>=, <=) so boundary values pass.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST include one jitter assertion per cache (10 caches total) verifying stored TTL is within ±10% of the base TTL.
- **FR-002**: Each test MUST be independent — failure in one cache's jitter test does not affect other cache tests.
- **FR-003**: Test failure messages MUST identify the specific cache and the expected TTL range to aid debugging.
- **FR-004**: Tests MUST NOT modify production code — test-only change.
- **FR-005**: Tests MUST NOT break existing test suite (3484 tests baseline).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 10 caches have a dedicated jitter assertion test that passes when jitter is applied and fails when jitter is removed.
- **SC-002**: Removing a single `jittered_ttl()` call from any cache file causes exactly one test failure.
- **SC-003**: All existing tests continue to pass (3484+ baseline).

## Assumptions

- The jitter percentage remains at 10% (configurable via CACHE_JITTER_PCT env var, default 0.1).
- Tests access internal cache state (module-level dicts/tuples) to inspect stored TTL values. This is acceptable for integration-style unit tests.
- Each cache stores the effective TTL as the third element of its cache entry tuple, or in a field accessible from the cache entry structure.
