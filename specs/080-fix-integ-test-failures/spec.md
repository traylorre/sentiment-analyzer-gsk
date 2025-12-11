# Feature Specification: Integration Test Failures Resolution

**Feature Branch**: `080-fix-integ-test-failures`
**Created**: 2025-12-10
**Status**: Planned
**Input**: Fix integration test failures from CI pipeline run 20097301157

## Overview

Integration tests are failing in the CI pipeline with 7 failures out of 152 tests. The primary failure is an API response format mismatch where tests expect a bare `list` but the API now returns `{'configurations': [], 'max_allowed': 2}`. This feature aligns tests with the current API contract.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fix Configuration List Response Expectation (Priority: P1)

Developers need integration tests to pass so the CI/CD pipeline can complete successfully. The `test_configs_list_returns_json` test fails because it expects `GET /api/v2/configurations` to return a bare JSON array, but the API now returns a wrapper object with `configurations` and `max_allowed` fields.

**Why this priority**: This is a critical pipeline blocker. Without this fix, no deployments can proceed. The test expectation is stale and must be updated to match the actual API contract.

**Independent Test**: Can be fully tested by running `pytest tests/e2e/test_dashboard_buffered.py::test_configs_list_returns_json -v` and verifying it passes.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** `GET /api/v2/configurations` is called, **Then** test expects response format `{'configurations': [...], 'max_allowed': N}`
2. **Given** the updated test, **When** CI pipeline runs integration tests, **Then** `test_configs_list_returns_json` passes

---

### User Story 2 - Investigate and Fix Observability Test Timeouts (Priority: P2)

Several tests are failing with `ReadTimeout(TimeoutError())`. These include observability-related tests that may be hitting AWS CloudWatch or X-Ray APIs which can be slow in certain conditions.

**Why this priority**: Timeout failures may be flaky or indicate genuine infrastructure issues. They should be investigated to determine if they're transient or require test adjustments (increased timeouts, mocking, or skip conditions).

**Independent Test**: Can be verified by running the failing observability tests locally with extended timeouts to isolate whether the issue is timing or infrastructure access.

**Acceptance Scenarios**:

1. **Given** observability tests, **When** tests run against preprod environment, **Then** tests either pass with appropriate timeouts or skip with clear reasoning
2. **Given** AWS access issues (permissions, throttling), **When** tests detect the issue, **Then** tests fail fast with actionable error message

---

### User Story 3 - Reduce Skip Rate Below Threshold (Priority: P3)

The current test run shows 64 skipped tests out of 216 (22.6% skip rate), which exceeds the 15% quality threshold. Many skips may be due to missing endpoints (Feature 079 roadmap), but some may be stale skip conditions that can be removed.

**Why this priority**: While not a blocker, high skip rates mask potential issues and reduce test coverage confidence. This should be addressed as part of overall test health improvement.

**Independent Test**: Can be verified by reviewing skip reasons, removing obsolete `pytest.skip()` calls, and running full test suite to measure new skip rate.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** obsolete skip conditions are identified and removed, **Then** skip rate decreases toward 15% threshold
2. **Given** tests skipped due to missing endpoints, **When** skip reasons are documented, **Then** they can be tracked against Feature 079 roadmap

---

### Edge Cases

- What happens when API response format changes again? → Tests should validate response structure flexibly (check for required fields rather than exact structure)
- How does system handle timeout vs. permission error? → Tests should distinguish between transient timeout and permanent access denied (different failure modes)
- What if observability tests fail due to AWS region configuration? → Tests should validate AWS_REGION environment variable is set correctly

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test `test_configs_list_returns_json` MUST expect response format `{'configurations': list, 'max_allowed': int}` instead of bare list
- **FR-002**: Test assertions MUST access configurations via `data['configurations']` or `data.get('configurations', [])`
- **FR-003**: Observability tests MUST have appropriate timeout values (minimum 30 seconds for AWS API calls)
- **FR-004**: Tests MUST distinguish between timeout errors and permission/access errors in failure messages
- **FR-005**: Skip conditions MUST have documented reasons linking to tracked issues or feature roadmap items

### Key Entities

- **Configuration Response**: API response containing `configurations` (list of user configurations) and `max_allowed` (integer quota)
- **Test Skip Condition**: Reason for skipping a test, including reference to blocking issue or feature number

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Integration tests pass with 0 failures (currently 7 failures)
- **SC-002**: Skip rate is documented and tracked (target: below 15%, current: 22.6%)
- **SC-003**: CI pipeline completes successfully end-to-end
- **SC-004**: All 7 failing tests are either fixed or skipped with documented justification
- **SC-005**: No new test failures introduced by these changes

## Out of Scope

- Implementing missing API endpoints (covered by Feature 079)
- Reducing skip rate below 15% immediately (requires Feature 079 endpoint implementations)
- Performance optimization of AWS API calls
- Adding new test coverage

## Assumptions

- The API response format change (`list` → `{configurations, max_allowed}`) is intentional and correct
- DASHBOARD_API_KEY secret is correctly configured in preprod environment (verified: present since 2025-11-24)
- Timeout failures are related to AWS API latency, not infrastructure misconfiguration
- Some skip conditions are valid and tied to unimplemented endpoints per Feature 079 roadmap

## Clarifications

*Session 2025-12-10*:
- Q: Is DASHBOARD_API_KEY configured correctly? → A: Yes, verified in preprod environment secrets
- Q: What is the root cause of the config list test failure? → A: API response format changed from `list` to `{configurations: [], max_allowed: N}`, test expectation not updated
