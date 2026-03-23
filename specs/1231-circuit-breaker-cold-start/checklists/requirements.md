# Requirements Checklist: 1231-circuit-breaker-cold-start

## Functional Requirements

- [ ] **FR-001**: `get_state()` returns `state="closed"` when DynamoDB unreachable
  - File: `src/lambdas/shared/circuit_breaker.py` (already implemented, needs test coverage)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestColdStartFailOpen`
  - Verification: Mock DynamoDB to raise `ClientError`, assert `state.state == "closed"` and `state.can_execute() == True`

- [ ] **FR-002**: `get_state()` logs `state_source` structured field
  - File: `src/lambdas/shared/circuit_breaker.py` (modify logging in `get_state()`)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestColdStartLogging`
  - Verification: Capture log output, assert `state_source` in extra fields

- [ ] **FR-003**: `get_state()` logs `cold_start` boolean field
  - File: `src/lambdas/shared/circuit_breaker.py` (modify logging in `get_state()`)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestColdStartLogging`
  - Verification: Capture log output, assert `cold_start` in extra fields with correct boolean value

- [ ] **FR-004**: `save_state()` never raises exceptions
  - File: `src/lambdas/shared/circuit_breaker.py` (already implemented, needs test coverage)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestSaveStateResilience`
  - Verification: Mock DynamoDB to raise various exceptions, assert no propagation

- [ ] **FR-005**: `ColdStartEvent` log emitted on first `get_state()` per service
  - File: `src/lambdas/shared/circuit_breaker.py` (add cold start detection logic)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestColdStartLogging`
  - Verification: Clear cache, call `get_state()`, assert log with cold_start=true; call again, assert cold_start=false

- [ ] **FR-006**: `SilentFailure/Count` metric includes `ColdStart` dimension
  - File: `src/lambdas/shared/circuit_breaker.py` (add dimension to `emit_metric()` call)
  - Test: `tests/unit/shared/test_circuit_breaker_cold_start.py::TestColdStartMetrics`
  - Verification: Mock `emit_metric`, assert `ColdStart` dimension present

## Implementation Tasks

- [ ] Add `state_source` and `cold_start` fields to all log entries in `get_state()`
- [ ] Add `ColdStart` dimension to `SilentFailure/Count` metric emission
- [ ] Write `test_circuit_breaker_cold_start.py` with all test classes
- [ ] Run existing tests to verify zero regressions
- [ ] Update `docs/cache-failure-policies.md` if it exists (or note in spec)

## Test Matrix

| Scenario | Cache State | DynamoDB | Expected State | state_source | cold_start |
|----------|-------------|----------|----------------|--------------|------------|
| Cold start, DB healthy | empty | returns item | from DB | dynamodb | true |
| Cold start, DB empty | empty | no item | default closed | dynamodb | true |
| Cold start, DB unreachable | empty | raises error | default closed | default_fail_open | true |
| Warm, cache hit | populated | N/A | from cache | cache | false |
| Warm, cache expired, DB healthy | expired | returns item | from DB | dynamodb | false |
| Warm, cache expired, DB unreachable | expired | raises error | default closed | default_fail_open | false |

## Acceptance Criteria Trace

| SC | Verified By | Status |
|----|------------|--------|
| SC-001 | `TestColdStartFailOpen::test_all_services_default_closed_on_dynamo_failure` | Pending |
| SC-002 | `TestColdStartLogging::test_state_source_field_present_*` | Pending |
| SC-003 | `TestColdStartMetrics::test_silent_failure_metric_includes_cold_start_dimension` | Pending |
| SC-004 | `make test-local` (existing test suite) | Pending |
| SC-005 | `TestColdStartFailOpen::test_concurrent_cold_start_all_default_closed` | Pending |
