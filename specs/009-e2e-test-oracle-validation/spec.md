# Feature Specification: E2E Test Oracle Validation

**Feature Branch**: `009-e2e-test-oracle-validation`
**Created**: 2025-11-29
**Status**: Draft
**Input**: User description: "Improve E2E test quality by adding oracle validation to eliminate trivial test outcomes. Based on audit findings: fix tests with dual-outcome assertions, add oracle comparison for sentiment tests, extend synthetic data coverage to preprod tests, and ensure all tests exercise specific failure modes in the processing layer."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix Sentiment Oracle Validation (Priority: P1)

As a QA engineer, I want sentiment tests to compare actual API responses against computed oracle values so that passing tests confirm correct data transformation rather than just response structure.

**Why this priority**: The audit found that `test_sentiment_with_synthetic_oracle` generates synthetic data but only validates structure, not actual oracle values. This undermines the purpose of having an oracle-based test and allows incorrect sentiment calculations to pass undetected.

**Independent Test**: Can be fully tested by running the sentiment test suite and verifying each test compares numeric sentiment values within tolerance (e.g., ±0.01) against oracle-computed expected values.

**Acceptance Scenarios**:

1. **Given** a configuration with known tickers and synthetic news data, **When** sentiment is retrieved from the API, **Then** the sentiment score differs from oracle-computed value by no more than 0.01
2. **Given** synthetic news with embedded expected sentiment (-0.5), **When** the processing pipeline computes sentiment, **Then** the result matches the embedded oracle value within tolerance
3. **Given** an oracle computation failure, **When** the test runs, **Then** the test fails explicitly rather than passing with structure-only validation

---

### User Story 2 - Eliminate Dual-Outcome Assertions (Priority: P1)

As a QA engineer, I want tests to assert specific expected outcomes rather than accepting multiple outcomes (e.g., `assert A or B`), so that test failures provide clear diagnostic information.

**Why this priority**: The audit found 8+ tests with dual-outcome assertions like `assert rate_limited > 0 or successes == len(status_codes)` which pass regardless of rate limiting behavior, making them ineffective at detecting regressions.

**Independent Test**: Can be verified by reviewing test assertions and confirming each test targets a single specific outcome with appropriate test variants for different scenarios.

**Acceptance Scenarios**:

1. **Given** a rate limiting test, **When** the test runs, **Then** it either confirms rate limiting occurred within N requests OR skips explicitly with a documented reason
2. **Given** a test that currently uses `assert A or B`, **When** refactored, **Then** it becomes two separate test functions: one for scenario A and one for scenario B
3. **Given** a test that cannot deterministically trigger its target condition in preprod, **When** the condition is not met, **Then** the test skips with a clear message rather than passing falsely

---

### User Story 3 - Extend Synthetic Data to Preprod Tests (Priority: P2)

As a QA engineer, I want preprod API contract tests to use seeded synthetic data fixtures instead of hardcoded values, so that tests exercise varied data patterns between runs while remaining deterministic within a run.

**Why this priority**: Currently only 2 of 20 test files use synthetic data generators. Other tests use hardcoded tickers (AAPL, MSFT) which means the same API paths are exercised every run, potentially missing edge cases.

**Independent Test**: Can be tested by running the E2E suite twice with different seeds and confirming different ticker symbols/config names are used while test outcomes remain consistent.

**Acceptance Scenarios**:

1. **Given** a configuration CRUD test, **When** it runs with seed 42, **Then** it creates configs with deterministic but seed-derived names and ticker combinations
2. **Given** two test runs with different seeds, **When** comparing test data created, **Then** different ticker symbols are used (not always AAPL/MSFT)
3. **Given** a test run with `E2E_TEST_SEED=42`, **When** the run is repeated with the same seed, **Then** identical synthetic data is generated

---

### User Story 4 - Add Processing Layer Failure Mode Tests (Priority: P2)

As a QA engineer, I want tests that inject specific failure conditions into the processing layer so that error handling paths are verified rather than only happy paths.

**Why this priority**: The audit identified gaps where sentiment computation errors, DynamoDB throttling, and SNS delivery failures are not tested, meaning error handling code is unverified.

**Independent Test**: Can be tested by running failure injection tests and confirming appropriate error responses or fallback behaviors.

**Acceptance Scenarios**:

1. **Given** a mock adapter configured to return malformed news data, **When** the sentiment pipeline processes it, **Then** the system returns a graceful error rather than crashing
2. **Given** a circuit breaker test with injectable failure mode, **When** failures are injected, **Then** the circuit breaker transitions to open state
3. **Given** an external API timeout, **When** the processing pipeline handles it, **Then** appropriate retry or fallback behavior is observed

---

### User Story 5 - Reduce Test Skip Rate (Priority: P3)

As a QA engineer, I want tests that frequently skip in preprod to either be fixed to work reliably or converted to appropriate test types, so that the E2E suite provides consistent coverage.

**Why this priority**: Many observability and notification tests skip when resources aren't available, providing false confidence in test coverage metrics.

**Independent Test**: Can be measured by tracking skip rate across test runs and ensuring skipped tests have documented justification.

**Acceptance Scenarios**:

1. **Given** a test that skips due to missing CloudWatch access, **When** reviewed, **Then** it is either converted to a unit test with mocks OR moved to a separate "integration-optional" marker
2. **Given** the E2E test suite, **When** run in preprod, **Then** the skip rate is below 15% of total tests
3. **Given** a skipped test, **When** examining the skip message, **Then** it includes actionable information about why it skipped and under what conditions it would run

---

### Edge Cases

- What happens when the oracle computation differs from production due to version mismatch?
- How does the system handle tests that legitimately cannot run in preprod (e.g., require production-only resources)?
- What happens when synthetic data generation produces edge case values (negative scores, empty arrays)?
- How are tests handled when preprod environment is partially available (some services up, others down)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test oracle MUST compute expected values using the same algorithms as production code
- **FR-002**: Sentiment comparison assertions MUST use numeric tolerance (±0.01) rather than exact equality
- **FR-003**: Tests MUST NOT use `assert A or B` patterns for validating distinct behaviors
- **FR-004**: Dual-outcome tests MUST be split into separate test functions with explicit names
- **FR-005**: Tests that cannot trigger their target condition MUST skip with descriptive messages
- **FR-006**: Synthetic data generators MUST be seeded from `test_run_id` for determinism
- **FR-007**: All preprod tests MUST use `synthetic_seed` fixture for random value generation
- **FR-008**: Failure injection tests MUST use mock adapter `fail_mode` flags
- **FR-009**: Circuit breaker tests MUST be able to inject failures to test state transitions
- **FR-010**: Test skip messages MUST include the condition that caused the skip and remediation steps
- **FR-011**: E2E test suite MUST track and report skip rate as a quality metric

### Key Entities

- **Test Oracle**: Component that computes expected values using production algorithms, seeded for determinism
- **Synthetic Data Generator**: Seeded random generators for tickers, news, sentiment, and configurations
- **Mock Adapter**: Test doubles for external APIs (Tiingo, Finnhub, SendGrid) with injectable failure modes
- **Test Fixture**: Session-scoped pytest fixtures providing synthetic data and oracle instances

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero tests with dual-outcome assertions (`assert A or B`) in the E2E suite
- **SC-002**: All sentiment tests compare actual values against oracle-computed expected values
- **SC-003**: Test suite skip rate is below 15% when run in preprod
- **SC-004**: 100% of synthetic data usage is deterministically reproducible with `E2E_TEST_SEED`
- **SC-005**: At least 5 new failure injection tests covering error handling paths
- **SC-006**: All skipped tests include actionable skip messages explaining conditions and remediation
- **SC-007**: Test suite detects at least 2 sentinel bugs (intentionally introduced defects) that current tests miss

## Assumptions

- The existing `SyntheticTestOracle` class in `test_financial_pipeline.py` provides a working pattern that can be extended
- Production sentiment calculation algorithms are accessible for oracle implementation
- Preprod environment has sufficient stability for E2E tests to run reliably
- Mock adapter patterns already exist and can be reused across test files
- The test suite's randomization architecture (UUID-based `test_run_id`) is correct and should be preserved
