# Feature Specification: Validation Baseline Establishment

**Feature Branch**: `059-validation-baseline`
**Created**: 2025-12-07
**Status**: Draft
**Input**: User description: "Approach 1: Merge and Iterate on Validation Findings - Establish a clean validation baseline for the target repo by merging pending PRs, running fresh /validate, and addressing any remaining gaps systematically."

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Merge Pending Template Changes (Priority: P1)

As a developer maintaining the template methodology, I want to merge PR #42 (058-target-spec-cleanup) containing the bidirectional allowlist support so that target repos can use allowlist-based suppression for validation findings.

**Why this priority**: P1 because the template changes (FIX-004) must be merged before target repo validation can benefit from the allowlist feature. This is a prerequisite for all subsequent validation work.

**Independent Test**: Merge PR #42 and verify the bidirectional allowlist functions are available in the codebase by importing the verification module.

**Acceptance Scenarios**:

1. **Given** PR #42 is open on template repo, **When** CI checks pass and PR is approved, **Then** the PR can be merged to main
2. **Given** PR #42 is merged, **When** main branch is pulled, **Then** `load_bidirectional_allowlist()` function is available in verification.py
3. **Given** the template is updated, **When** validators run against a target repo with an allowlist file, **Then** suppressed findings are filtered from results

---

### User Story 2 - Fix Target Repo Branch Sync (Priority: P1)

As a developer working on the target repo, I want to resolve the branch synchronization issue preventing PR creation so that the bidirectional allowlist can be merged to main.

**Why this priority**: P1 because the target repo's `051-validation-bypass-audit` branch failed PR creation due to "No commits between main and branch" error. The allowlist file must reach main for validation to pass.

**Independent Test**: Create a valid PR from the target repo branch and verify the allowlist file appears in the PR diff.

**Acceptance Scenarios**:

1. **Given** branch 051-validation-bypass-audit has commits not on main, **When** PR is created, **Then** the PR shows bidirectional-allowlist.yaml in the diff
2. **Given** the target repo PR is created, **When** CI checks pass, **Then** the PR can be merged to main
3. **Given** both repos have their PRs merged, **When** main branches are pulled, **Then** validation infrastructure is complete

---

### User Story 3 - Run Baseline Validation (Priority: P2)

As a developer, I want to run a fresh /validate on the target repo after merging all changes so that I have a documented clean baseline of validation status.

**Why this priority**: P2 because this validation run establishes the baseline after prerequisite merges. It confirms whether the success criteria are met and identifies any remaining gaps.

**Independent Test**: Run `/validate` command on target repo and capture output showing validator status breakdown.

**Acceptance Scenarios**:

1. **Given** both PRs are merged to main, **When** /validate runs on target repo, **Then** output shows validator counts (PASS/FAIL/SKIP)
2. **Given** validation completes, **When** results are reviewed, **Then** zero FAIL status validators are reported
3. **Given** zero FAIL status, **When** WARN findings are reviewed, **Then** all warnings have documented exemptions or are addressed

---

### User Story 4 - Document Validation State (Priority: P3)

As a developer, I want the validation baseline documented so that future validation runs can be compared against a known-good state.

**Why this priority**: P3 because documentation follows successful validation. This creates a reference point for regression detection.

**Independent Test**: Create a validation baseline document showing all validator statuses and any exempted findings.

**Acceptance Scenarios**:

1. **Given** validation passes, **When** results are documented, **Then** document includes date, validator counts, and exemption rationale
2. **Given** baseline is documented, **When** future validation runs, **Then** differences from baseline can be identified

---

### Edge Cases

- What happens if template PR #42 has merge conflicts with main?
  - Answer: Rebase the branch on main and force-push, then re-run CI
- What happens if target repo branch is already merged or closed?
  - Answer: Check PR status first; if already merged, skip to validation step
- What happens if validation reveals new findings after merge?
  - Answer: Address findings systematically - add to allowlist with justification or fix root cause

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Template repo PR #42 MUST pass all CI checks before merge
- **FR-002**: Target repo branch MUST be synchronized with remote to enable PR creation
- **FR-003**: Target repo PR MUST include bidirectional-allowlist.yaml in the changeset
- **FR-004**: Validation run MUST execute all 13 methodology validators
- **FR-005**: Validation output MUST show status breakdown (PASS/FAIL/SKIP/SUPPRESSED counts)
- **FR-006**: Any FAIL findings MUST be either fixed or documented with exemption rationale
- **FR-007**: Baseline documentation MUST be created after successful validation

### Key Entities

- **Pull Request**: A proposed change to a repository's main branch, subject to CI checks and approval
- **Validation Run**: Execution of all methodology validators against a target repository
- **Allowlist Entry**: A documented suppression of a validation finding with classification and justification
- **Baseline Document**: A point-in-time record of validation state for regression comparison

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Zero FAIL status validators on target repo validation output
- **SC-002**: Zero WARN status validators (excluding documented exemptions per Amendment 1.7)
- **SC-003**: All pending PRs merged to main in both template and target repos
- **SC-004**: Validation output documented with date, validator counts, and exemption details
- **SC-005**: Template repo unit tests pass (579+ tests)
- **SC-006**: Target repo unit tests pass (1613+ tests)

## Assumptions

- PR #42 exists and is ready for merge (CI passing, no conflicts)
- Target repo branch 051-validation-bypass-audit contains the bidirectional-allowlist.yaml commit
- The /validate command is available and configured for target repo execution
- Amendment 1.7 (Target Repo Independence) allows validators to SKIP when target repos lack template infrastructure
