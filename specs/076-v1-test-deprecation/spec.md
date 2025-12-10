# Feature Specification: Deprecate v1 API Integration Tests

**Feature Branch**: `076-v1-test-deprecation`
**Created**: 2025-12-10
**Status**: Draft
**Input**: User description: "Deprecate v1 API Integration Tests - Audit and Removal"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Audit v1 Tests for v2 Equivalence (Priority: P1)

As a developer maintaining the test suite, I need to verify that each skipped v1 API test has equivalent coverage in the v2 test suite, so that I can safely remove deprecated tests without losing coverage.

**Why this priority**: Before any test removal, we must confirm no valuable test coverage is lost. This audit is the foundation for all subsequent work.

**Independent Test**: Can be validated by creating an audit document mapping each v1 test to its v2 equivalent (or documenting why no equivalent is needed).

**Acceptance Scenarios**:

1. **Given** 21 skipped v1 API tests in `tests/integration/test_dashboard_preprod.py`, **When** an audit is performed, **Then** each test is mapped to a v2 equivalent or explicitly marked as "no equivalent needed" with justification
2. **Given** a v1 test that validates a specific behavior, **When** searching for v2 coverage, **Then** the equivalent v2 test is identified in `tests/e2e/` or the behavior is confirmed as deprecated
3. **Given** a v1 test with no obvious v2 equivalent, **When** analyzed, **Then** the audit documents whether the behavior should exist in v2 (gap) or is intentionally not covered (deprecated feature)

---

### User Story 2 - Remove Confirmed Deprecated Tests (Priority: P2)

As a developer, I want to remove v1 API tests that have been confirmed as having equivalent v2 coverage, so that the test suite has fewer skipped tests and reduced maintenance burden.

**Why this priority**: Once the audit confirms equivalence, removal is straightforward. This depends on US1 completion.

**Independent Test**: Run test suite before and after removal - skip count should decrease by the number of removed tests, and no actual coverage is lost.

**Acceptance Scenarios**:

1. **Given** an audit document confirming v1 test X has v2 equivalent Y, **When** test X is removed, **Then** the test suite still passes and coverage is maintained
2. **Given** all 21 v1 tests have been audited, **When** tests with confirmed equivalents are removed, **Then** `pytest --collect-only` shows 21 fewer skipped tests
3. **Given** a removed test, **When** its justification is reviewed, **Then** there exists a documented link to the v2 equivalent or deprecation rationale

---

### User Story 3 - Update Validation Gap Documentation (Priority: P3)

As a project maintainer, I want the RESULT1-validation-gaps.md document updated to reflect the closed gap, so that project status accurately reflects current state.

**Why this priority**: Documentation update is important but non-blocking. It depends on US2 completion.

**Independent Test**: Read RESULT1-validation-gaps.md and verify the "21 v1 API integration tests" entry is updated to reflect closure.

**Acceptance Scenarios**:

1. **Given** 21 v1 tests have been removed, **When** RESULT1-validation-gaps.md is reviewed, **Then** the document shows these tests as "closed" rather than "intentional skip"
2. **Given** the audit document exists, **When** referenced in RESULT1, **Then** stakeholders can trace the decision rationale

---

### Edge Cases

- What happens if a v1 test validates behavior not covered by any v2 test?
  - Document as a coverage gap; may require new v2 test creation (out of scope for this feature)
- What happens if v2 test exists but with different acceptance criteria?
  - Analyze whether v2 criteria are sufficient; document discrepancies
- What happens if v1 test file has non-deprecated tests mixed in?
  - Remove only the specific tests marked with "v1 API deprecated" skip reason

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST produce an audit document mapping all 21 v1 tests to v2 equivalents or deprecation justifications
- **FR-002**: System MUST NOT remove any test without documented justification
- **FR-003**: Audit document MUST reference specific v2 test file and function name for each mapping
- **FR-004**: Removal process MUST preserve any non-deprecated tests in the same file
- **FR-005**: Audit document MUST categorize each v1 test as one of:
  - "v2 equivalent exists" (with reference)
  - "behavior deprecated" (with rationale)
  - "coverage gap identified" (requires follow-up)
- **FR-006**: RESULT1-validation-gaps.md MUST be updated to reflect final state

### Key Entities

- **v1 Test**: A skipped integration test with reason "v1 API deprecated" in `tests/integration/test_dashboard_preprod.py`
- **v2 Test**: An active test in `tests/e2e/` directory that validates equivalent behavior
- **Audit Document**: A traceability matrix mapping v1 tests to v2 equivalents with justification

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Audit document exists at `specs/076-v1-test-deprecation/audit.md` with all 21 v1 tests mapped
- **SC-002**: Zero tests removed without documented justification in audit document
- **SC-003**: Test suite skip count reduced by exactly the number of removed deprecated tests
- **SC-004**: No reduction in actual test behavior coverage (as verified by audit mapping)
- **SC-005**: RESULT1-validation-gaps.md updated to show 21 fewer skipped tests in "v1 API" category

## Assumptions

- The skip reason "v1 API deprecated - use /api/v2/* endpoints" indicates intentional deprecation, not temporary skip
- Tests in `tests/e2e/` represent the v2 API test suite
- If a v1 behavior has no v2 equivalent and the behavior is still needed, that represents a gap to be addressed in a separate feature
- The 21 skipped tests all reside in a single file: `tests/integration/test_dashboard_preprod.py`

## Scope Boundaries

### In Scope

- All 21 skipped tests with "v1 API deprecated" skip reason
- Audit document creation
- Test removal after audit confirms equivalence
- RESULT1 documentation update

### Out of Scope

- Creating new v2 tests to fill gaps (separate feature)
- Modifying any v2 tests
- Changes to production code
- Other integration test files
