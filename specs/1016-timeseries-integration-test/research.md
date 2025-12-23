# Research: Timeseries Integration Test Suite

**Feature**: 1016-timeseries-integration-test
**Date**: 2025-12-22

## Research Questions Resolved

### RQ-001: LocalStack DynamoDB Table Creation Pattern

**Question**: How should we manage DynamoDB table lifecycle in integration tests?

**Decision**: Use class-scoped fixtures for table lifecycle

**Rationale**:
- Table creation is slow (~2s per table in LocalStack)
- Tests within same class share table for performance
- Teardown ensures test isolation between classes
- Pattern already used in `tests/integration/ohlc/test_happy_path.py`

**Alternative Considered**: Session-scoped table shared by all tests
- Rejected: Risk of test pollution, harder to isolate failures

**Source**: Codebase analysis - `tests/integration/conftest.py`, existing integration test patterns

---

### RQ-002: Time Mocking Strategy for Partial Buckets

**Question**: How should we handle time-dependent tests for partial bucket detection?

**Decision**: Use freezegun with fixed timestamps per constitution Amendment 1.5

**Rationale**:
- `@freeze_time("2024-01-02T10:37:30Z")` provides deterministic time
- Allows testing partial bucket at 50% progress exactly
- Compatible with datetime.now(timezone.utc) pattern
- Already a project dependency

**Alternative Considered**: Manual time injection via parameters
- Rejected: More boilerplate, less realistic testing

**Source**: Constitution Amendment 1.5, existing unit tests using freezegun

---

### RQ-003: Test Data Generation Approach

**Question**: How should we generate test data for integration tests?

**Decision**: Use deterministic fixtures with known values

**Rationale**:
- Constitution requires synthetic test data (Section 7)
- Fixed ticker symbols (AAPL, TSLA) for reproducibility
- Fixed sentiment values ([0.6, 0.9, 0.3, 0.7]) for OHLC verification
- ISO8601 timestamps for CodeQL compatibility

**Alternative Considered**: Hypothesis property-based testing
- Deferred: Good for edge cases but adds complexity; can add later

**Source**: Constitution Section 7 - Synthetic Test Data requirement

---

### RQ-004: Query Interface for Testing

**Question**: Should we test via direct function calls or Lambda invocation?

**Decision**: Call `write_fanout` and `query_timeseries` directly

**Rationale**:
- Integration tests target the library code, not Lambda handlers
- Direct function calls are faster than HTTP invocation
- Matches existing integration test patterns in codebase
- Lambda handler integration is covered in E2E tests

**Alternative Considered**: Invoke Lambda functions via LocalStack
- Rejected: Slower, more complex setup, overkill for library testing

**Source**: Existing patterns in `tests/integration/ingestion/`, `tests/integration/ohlc/`

---

### RQ-005: Assertion Strategy for OHLC Values

**Question**: How should we compare floating-point sentiment scores in assertions?

**Decision**: Use pytest.approx for float comparisons

**Rationale**:
- Sentiment scores are floats (0.0-1.0)
- Floating point comparison needs tolerance
- `pytest.approx(0.7, rel=0.001)` prevents false failures
- Standard pytest pattern

**Alternative Considered**: Exact equality with Decimal
- Rejected: Overkill for sentiment scores which are derived from ML models

**Source**: pytest documentation, existing unit tests in codebase

---

## Key Findings

1. **LocalStack fixtures are mature** - The existing `tests/integration/conftest.py` provides all needed DynamoDB client fixtures
2. **Timeseries library is complete** - `src/lib/timeseries/` has all functions needed: `generate_fanout_items`, `write_fanout`, `floor_to_bucket`
3. **Query function may need implementation** - Need to verify `query_timeseries` exists or implement it
4. **Test isolation pattern established** - Use `test_run_id` fixture for unique table names

## Dependencies Identified

| Dependency | Status | Notes |
|------------|--------|-------|
| LocalStack | Available | Configured in conftest.py |
| freezegun | Available | In requirements-dev.txt |
| boto3 | Available | Core dependency |
| src/lib/timeseries | Implemented | Fanout, bucket, aggregation modules exist |
