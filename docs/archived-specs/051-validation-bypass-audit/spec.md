# Feature Specification: Validation Bypass Audit

**Feature Branch**: `051-validation-bypass-audit`
**Created**: 2025-12-06
**Status**: Draft
**Input**: User description: "Audit of all false-positives, workarounds, hacks, and anything in the target repo circumventing /validate"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Comprehensive Bypass Inventory (Priority: P1)

As a developer, I need a complete inventory of all validation bypasses in the codebase so that I can understand the scope of technical debt and prioritize remediation.

**Why this priority**: Cannot remediate what isn't measured. This is the foundation for all other work.

**Independent Test**: Run the audit script and verify it produces a structured report listing all bypass patterns with their locations.

**Acceptance Scenarios**:

1. **Given** a codebase with validation bypasses, **When** the audit runs, **Then** it identifies all `SKIP=` patterns in git history
2. **Given** a codebase with pragma comments, **When** the audit runs, **Then** it identifies all `pragma: allowlist` comments
3. **Given** a codebase with lint suppressions, **When** the audit runs, **Then** it identifies all `# noqa` and `# type: ignore` comments
4. **Given** a codebase with deprecation warnings, **When** the audit runs, **Then** it counts `datetime.utcnow()` usages
5. **Given** a codebase with hook issues, **When** the audit runs, **Then** it identifies pre-commit configuration problems

---

### User Story 2 - Classification and Risk Assessment (Priority: P2)

As a tech lead, I need each bypass classified as legitimate (document) vs technical debt (remediate) with risk levels so that I can prioritize remediation work.

**Why this priority**: Not all bypasses are equal - some are legitimate (e.g., moto mock credentials), others are tech debt (e.g., deprecated API usage).

**Independent Test**: Review audit output and verify each bypass has a classification and risk rating.

**Acceptance Scenarios**:

1. **Given** an audit report, **When** reviewing a bypass, **Then** it has a classification (LEGITIMATE or TECH_DEBT)
2. **Given** an audit report, **When** reviewing tech debt, **Then** it has a risk level (HIGH, MEDIUM, LOW)
3. **Given** a legitimate bypass, **When** documented, **Then** it includes justification for why it's acceptable
4. **Given** tech debt, **When** classified, **Then** it includes remediation guidance

---

### User Story 3 - Remediation Execution (Priority: P3)

As a developer, I need to remediate identified tech debt so that the codebase passes validation without bypasses.

**Why this priority**: The goal is a clean repo - this story delivers the actual fixes.

**Independent Test**: After remediation, running `/validate` and `git push` succeeds without any `SKIP=` environment variables.

**Acceptance Scenarios**:

1. **Given** deprecated datetime usage, **When** remediated, **Then** code uses `datetime.now(datetime.UTC)`
2. **Given** a broken pre-commit hook, **When** fixed, **Then** `git push` runs without `SKIP=pytest`
3. **Given** unnecessary lint suppressions, **When** removed, **Then** code passes lint without suppressions
4. **Given** remaining legitimate bypasses, **When** documented, **Then** they have inline justification comments

---

### Edge Cases

- What happens when a bypass is in third-party generated code?
- How does the audit handle bypasses in vendored dependencies?
- What if a bypass was introduced as a temporary fix with an issue reference?

## Requirements *(mandatory)*

### Functional Requirements

**Bypass Detection**:

- **FR-001**: Audit MUST identify all `SKIP=<hook>` patterns used in git commits and documented workflows
- **FR-002**: Audit MUST identify all `pragma: allowlist secret` comments with file locations
- **FR-003**: Audit MUST identify all `# noqa` comments with the suppressed rule codes
- **FR-004**: Audit MUST identify all `# type: ignore` comments with locations
- **FR-005**: Audit MUST count `datetime.utcnow()` usages and group by file

**Classification**:

- **FR-006**: Each bypass MUST be classified as LEGITIMATE or TECH_DEBT
- **FR-007**: Each TECH_DEBT item MUST have a risk level (HIGH, MEDIUM, LOW)
- **FR-008**: Each bypass MUST include the file path and line number
- **FR-009**: LEGITIMATE bypasses MUST include justification documentation

**Remediation**:

- **FR-010**: All `datetime.utcnow()` calls MUST be replaced with timezone-aware alternatives
- **FR-011**: Pre-commit hook configuration MUST work without SKIP= variables
- **FR-012**: Unnecessary lint suppressions MUST be removed
- **FR-013**: Remaining legitimate bypasses MUST have inline documentation

**Reporting**:

- **FR-014**: Audit MUST produce a structured report (markdown or YAML)
- **FR-015**: Report MUST include summary statistics (total bypasses, by category, by risk)
- **FR-016**: Report MUST be reproducible (same input produces same output)

### Key Entities

- **Bypass**: A code pattern that circumvents validation (location, type, classification, risk, justification)
- **AuditReport**: Collection of bypasses with summary statistics and remediation status
- **Classification**: LEGITIMATE (with justification) or TECH_DEBT (with risk level)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Audit identifies 100% of validation bypasses in the codebase (verified by manual sampling)
- **SC-002**: All 365+ datetime.utcnow() deprecation warnings are resolved
- **SC-003**: `git push` succeeds without any `SKIP=` environment variables
- **SC-004**: Pre-commit hooks pass without configuration workarounds
- **SC-005**: Remaining legitimate bypasses are documented with justification comments
- **SC-006**: `/validate` runs cleanly with no new bypass patterns introduced

## Out of Scope

- Bypasses in vendored/third-party code (document but don't remediate)
- Historical git commit analysis beyond current codebase state
- Automated bypass detection in CI (future enhancement)
- Cross-repository bypass patterns (template repo has separate audit)

## Assumptions

- All SKIP= patterns used in current workflows are temporary and should be eliminated
- datetime.utcnow() can be replaced with datetime.now(datetime.UTC) without breaking changes
- Pre-commit hook issues are configuration problems, not fundamental incompatibilities
- Legitimate bypasses are rare and each needs explicit justification
