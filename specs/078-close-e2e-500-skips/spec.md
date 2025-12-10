# Feature Specification: Close Config Creation 500 E2E Test Skips

**Feature Branch**: `078-close-e2e-500-skips`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "Close Config Creation 500 E2E Test Skips - Remove defensive skips now that Feature 077 fixed the underlying issue"

## User Scenarios & Testing

### User Story 1 - Remove 500 Error Test Skips (Priority: P1)

As a QA engineer, I want the E2E test suite to exercise config creation functionality without skipping tests, so that we have full regression coverage for the config creation flow.

**Why this priority**: Config creation is a core user flow. The 500 error was fixed in Feature 077 (PR #332), but ~18 tests still skip defensively. Without removing these skips, we have a blind spot in E2E coverage that could allow regressions to go undetected.

**Independent Test**: Can be validated by running `pytest tests/e2e/ -k "config" -v` and confirming zero tests skip with "Config creation endpoint returning 500" message.

**Acceptance Scenarios**:

1. **Given** the E2E test suite with config-related tests, **When** tests execute against preprod, **Then** no test skips due to "Config creation endpoint returning 500 - API issue"
2. **Given** a test that previously skipped for 500 errors, **When** it now runs, **Then** it either passes (valid config) or fails with appropriate validation error (422 for invalid input)
3. **Given** the test file `test_config_crud.py`, **When** running all tests, **Then** all 8 config CRUD tests execute without 500-related skips

---

### User Story 2 - Verify Test Pass Rate (Priority: P2)

As a release manager, I want all unskipped tests to pass against preprod, so that we can confidently merge this change without introducing test failures.

**Why this priority**: Removing skips without verifying the tests pass would break CI. We need to confirm the Feature 077 fix actually works in preprod before declaring victory.

**Independent Test**: Run full E2E suite against preprod and verify all previously-skipped tests now pass.

**Acceptance Scenarios**:

1. **Given** tests in `test_config_crud.py` that were skipped, **When** run against preprod with Feature 077 deployed, **Then** all tests pass
2. **Given** tests in `test_alerts.py` with config dependencies, **When** run after skip removal, **Then** tests pass or skip only for unrelated reasons (e.g., "Alerts endpoint not implemented")
3. **Given** tests in `test_anonymous_restrictions.py`, **When** config creation is attempted, **Then** system returns 422 for invalid input (not 500)

---

### User Story 3 - Update Tech Debt Documentation (Priority: P3)

As a project maintainer, I want RESULT2-tech-debt.md updated to reflect the closure of this tech debt category, so that our tracking documents remain accurate.

**Why this priority**: Documentation hygiene. The tech debt inventory should reflect what's actually outstanding, not stale information.

**Independent Test**: Verify RESULT2-tech-debt.md shows the "E2E Test Skips (Config 500)" category as closed with date and PR reference.

**Acceptance Scenarios**:

1. **Given** the current RESULT2-tech-debt.md, **When** this feature is complete, **Then** the "~18 NOW CLOSEABLE" category shows as "CLOSED"
2. **Given** the closed category, **When** viewing the document, **Then** it includes the closure date and PR number

---

### Edge Cases

- What happens if a test was skipping for BOTH "500 error" and "endpoint not implemented"?
  - Remove only the 500-related skip condition; preserve other skip conditions
- How does the system handle tests that depend on config creation but test other functionality (alerts, failure injection)?
  - These tests should now be able to create configs and proceed to test their actual functionality
- What if preprod doesn't have Feature 077 deployed yet?
  - Tests will fail; this feature is blocked until Feature 077 reaches preprod

## Requirements

### Functional Requirements

- **FR-001**: E2E tests MUST NOT skip with message "Config creation endpoint returning 500 - API issue"
- **FR-002**: Tests MUST preserve skip conditions unrelated to the 500 error (e.g., "Config creation not available", "Endpoint not implemented")
- **FR-003**: The skip pattern `pytest.skip("Config creation endpoint returning 500")` MUST be removed from all test files
- **FR-004**: All modified tests MUST pass against preprod after skip removal
- **FR-005**: RESULT2-tech-debt.md MUST be updated with closure summary
- **FR-006**: No test coverage regression - tests that were executing before MUST continue to execute

### Test Files to Modify

- **test_config_crud.py**: ~8 tests with 500 skip patterns
- **test_alerts.py**: ~2 tests with 500 skip patterns
- **test_anonymous_restrictions.py**: ~5 tests with 500 skip patterns
- **test_auth_anonymous.py**: ~2 tests with 500 skip patterns
- **test_failure_injection.py**: ~1 test with 500 skip pattern
- **test_sentiment.py**: ~1 test with 500 skip pattern (if applicable)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Zero E2E tests contain the skip message "Config creation endpoint returning 500"
- **SC-002**: 100% of unskipped tests pass against preprod with Feature 077 deployed
- **SC-003**: RESULT2-tech-debt.md updated with closure date and PR reference
- **SC-004**: No increase in total test skip count (excluding the intentional removals)

## Assumptions

- Feature 077 has been deployed to preprod before this feature is tested
- The 422 response from the fixed endpoint provides sufficient error information for tests expecting validation failures
- Tests with multiple skip conditions will retain their non-500-related skip conditions

## Dependencies

- **Requires**: Feature 077 (Config Creation 500 Fix) deployed to preprod
- **Blocked by**: None (code is merged to main)

## Out of Scope

- E2E tests skipped for "Endpoint not implemented" (~60 tests) - requires separate feature work
- E2E tests skipped for auth/environment constraints (~20 tests) - intentional architectural decisions
- Unit test validator TODOs (6 skips) - separate audit needed
- Flaky test `test_cache_expiry` fix - separate backlog item
