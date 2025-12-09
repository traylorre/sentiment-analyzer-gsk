# Feature Specification: Fix Infracost Cost Check Workflow Failure

**Feature Branch**: `068-fix-infracost-action`
**Created**: 2025-12-08
**Status**: Draft
**Input**: User description: "Fix Infracost Cost Check Workflow Failure - All PRs blocked by failing Cost check due to deprecated infracost/actions/comment action"

## Problem Statement

All PRs in sentiment-analyzer-gsk are blocked by a failing "Cost" check in CI. The failure prevents:
- PR #312 (pytest major) from being reviewable
- PR #313 (pre-commit major) from being reviewable
- PR #316 (Feature 067 spec docs) from merging
- All future PRs from passing CI

**Root Cause**: The workflow at `.github/workflows/pr-checks.yml:271` uses `infracost/actions/comment@v1`, which has been removed from the infracost/actions repository. The action no longer exists - only the `setup/` subfolder action remains.

**Error from CI logs**:
```
##[error]Can't find 'action.yml', 'action.yaml' or 'Dockerfile' for action 'infracost/actions/comment@v3'.
```

## User Scenarios & Testing *(mandatory)*

### User Story 1 - PR Cost Check Passes (Priority: P1)

As a developer submitting a PR, I want the Cost check to pass so that my PR can proceed through the CI pipeline without being blocked by a non-functional action.

**Why this priority**: This is the critical path - without fixing this, no PRs can merge. The Cost check is a required status check for branch protection.

**Independent Test**: Submit any PR and verify the "Cost" job in `pr-checks.yml` completes successfully (green check).

**Acceptance Scenarios**:

1. **Given** a PR is submitted, **When** the pr-checks workflow runs, **Then** the Cost job completes without error
2. **Given** the Cost job runs, **When** infracost CLI is invoked, **Then** no "action not found" errors occur
3. **Given** the workflow completes, **When** viewing PR checks, **Then** all required checks pass (including Cost)

---

### User Story 2 - Cost Comments Appear on PRs (Priority: P2)

As a developer reviewing a PR, I want to see infrastructure cost estimates in PR comments so that I can assess the financial impact of changes.

**Why this priority**: While passing CI is critical (P1), cost visibility is the actual purpose of the Cost job. However, the job can pass without posting comments if infracost has no cost diff to report.

**Independent Test**: Submit a PR that modifies `infrastructure/terraform/` and verify a cost comment appears on the PR.

**Acceptance Scenarios**:

1. **Given** a PR modifies Terraform infrastructure, **When** the Cost job completes, **Then** an Infracost comment is posted to the PR
2. **Given** a PR has no infrastructure changes, **When** the Cost job completes, **Then** the job passes gracefully (no comment required)
3. **Given** the Infracost API is unavailable, **When** the Cost job runs, **Then** the job fails gracefully with `continue-on-error: true`

---

### User Story 3 - Process Improvement Evaluation (Priority: P3)

As a repository maintainer, I want documentation on whether a new methodology should be created to detect deprecated GitHub Actions proactively.

**Why this priority**: Prevention is valuable but not urgent - the immediate fix takes precedence.

**Independent Test**: Review research.md for methodology recommendation with rationale.

**Acceptance Scenarios**:

1. **Given** this failure occurred, **When** the fix is complete, **Then** research.md documents whether `/add-methodology` for action validation is warranted
2. **Given** a methodology recommendation, **When** documented, **Then** it includes rationale based on frequency, impact, and detection feasibility

---

### Edge Cases

- What happens when Infracost API key is missing or invalid? (Job should fail gracefully with `continue-on-error`)
- What happens when no Terraform files exist in the repository? (Job should skip or pass with no output)
- What happens when the PR diff JSON is empty or malformed? (Job should handle gracefully)
- What happens when GitHub token lacks required permissions? (Job should fail with clear error message)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Workflow MUST replace `infracost/actions/comment@v1` action with equivalent CLI command
- **FR-002**: Workflow MUST use `infracost comment github` CLI command with required flags
- **FR-003**: Workflow MUST pass `--path`, `--repo`, `--github-token`, `--pull-request`, and `--behavior` flags
- **FR-004**: Workflow MUST set `--behavior=update` to create/update a single comment per PR
- **FR-005**: Workflow MUST preserve `continue-on-error: true` to prevent cost failures from blocking PRs
- **FR-006**: Workflow MUST use existing `GITHUB_TOKEN` for authentication
- **FR-007**: Workflow MUST reference the correct diff JSON path from previous step

### Key Entities

- **pr-checks.yml**: The workflow file containing the Cost job (lines 232-275)
- **infracost/actions/setup@v3**: The setup action that remains valid and installs Infracost CLI
- **Infracost CLI**: The command-line tool that replaces the deprecated action functionality

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cost check passes on all currently blocked PRs (#312, #313, #316) within one workflow re-run
- **SC-002**: All future PRs have passing Cost checks (verified by the fix PR itself passing)
- **SC-003**: Cost comments appear on PRs with infrastructure changes (functional parity with previous behavior)
- **SC-004**: No regression in existing CI functionality (all other checks continue to pass)
- **SC-005**: Process improvement recommendation documented with clear rationale

## Assumptions

- The Infracost API key (`INFRACOST_API_KEY`) secret is already configured and valid
- The `infracost/actions/setup@v3` action correctly installs the Infracost CLI with `comment` subcommand
- The CLI command `infracost comment github` provides equivalent functionality to the deprecated action
- Branch protection requires the Cost check to pass (hence blocking all PRs)

## Canonical Sources

- [infracost/actions Repository](https://github.com/infracost/actions) - Confirms only `setup/` subfolder exists
- [Infracost CLI comment command](https://www.infracost.io/docs/features/cli_commands/#comment) - Current recommended approach
- [Infracost GitHub Integration Docs](https://www.infracost.io/docs/integrations/github_actions/) - Official GitHub Actions setup guide
