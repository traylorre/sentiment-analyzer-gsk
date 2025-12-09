# Feature Specification: Stale PR Auto-Update

**Feature Branch**: `069-stale-pr-autoupdate`
**Created**: 2025-12-08
**Status**: Draft
**Input**: User description: "Add slash command /poke-stale-prs or a scheduled workflow that auto-updates PR branches when main changes"

## Problem Statement

When workflow files in `.github/workflows/` are fixed in main, existing open PRs continue to fail because they run the outdated workflow from their own branch. This requires manual intervention to update each PR branch with the latest main, causing:

1. Developer friction (manual `gh api` calls for each PR)
2. Delayed PR merges while waiting for manual updates
3. Confusion about why PRs fail after a workflow fix is merged

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic PR Updates on Workflow Changes (Priority: P1)

When a workflow file is updated in main, all open PR branches are automatically updated to include the fix, ensuring they run the corrected CI pipeline without manual intervention.

**Why this priority**: This is the core value proposition - eliminating manual PR updates when workflow files change. This addresses the root cause of the recurring CI failures observed with PRs 312-316 after the infracost fix.

**Independent Test**: Create a PR, merge a workflow fix to main, verify the PR branch is automatically updated and re-runs CI with the new workflow.

**Acceptance Scenarios**:

1. **Given** an open PR with a stale branch, **When** a workflow file is pushed to main, **Then** the PR branch is updated with the latest main within 5 minutes
2. **Given** multiple open PRs, **When** a workflow fix is merged to main, **Then** all open PR branches are updated in parallel
3. **Given** a PR with merge conflicts, **When** auto-update is triggered, **Then** the update is skipped and no error disrupts other PR updates

---

### User Story 2 - Manual PR Refresh Command (Priority: P2)

Developers can manually trigger a refresh of all stale PRs using the `/poke-stale-prs` slash command, providing on-demand control when immediate updates are needed.

**Why this priority**: Provides manual override capability for situations where automatic updates haven't run yet or for debugging purposes.

**Independent Test**: Run `/poke-stale-prs` command and verify all open PRs are updated with latest main.

**Acceptance Scenarios**:

1. **Given** multiple open PRs behind main, **When** developer runs `/poke-stale-prs`, **Then** all PR branches are updated with latest main
2. **Given** a PR that cannot be auto-merged due to conflicts, **When** `/poke-stale-prs` runs, **Then** that PR is skipped with a warning message and other PRs proceed
3. **Given** no open PRs exist, **When** `/poke-stale-prs` runs, **Then** command completes with "No open PRs to update" message

---

### User Story 3 - Visibility into Auto-Update Activity (Priority: P3)

Repository maintainers can see when and which PRs were auto-updated, providing transparency into the automated process.

**Why this priority**: Useful for debugging and audit trails, but not essential for core functionality.

**Independent Test**: Check GitHub Actions workflow run history to see auto-update executions and which PRs were processed.

**Acceptance Scenarios**:

1. **Given** auto-update workflow runs, **When** maintainer views Actions tab, **Then** they see which PRs were updated and any that were skipped
2. **Given** a PR was skipped due to conflicts, **When** viewing workflow logs, **Then** the reason for skipping is clearly logged

---

### Edge Cases

- What happens when a PR has merge conflicts with main? → Skip that PR, continue with others, log warning
- What happens when GitHub API rate limits are hit? → Workflow fails gracefully with clear error message
- What happens when no open PRs exist? → Workflow completes successfully with informational message
- What happens when auto-update is triggered during an ongoing CI run? → GitHub handles this naturally (new push cancels in-progress runs for that branch)
- What happens when GITHUB_TOKEN lacks permissions? → Clear error message identifying missing permission

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically update all open PR branches when any file in `.github/workflows/` is modified in main
- **FR-002**: System MUST provide a `/poke-stale-prs` slash command for manual triggering of PR branch updates
- **FR-003**: System MUST skip PRs that have merge conflicts and continue processing remaining PRs
- **FR-004**: System MUST log which PRs were updated and which were skipped (with reasons)
- **FR-005**: System MUST complete PR updates within 5 minutes of workflow file changes to main
- **FR-006**: System MUST use existing `GITHUB_TOKEN` permissions (no additional secrets required)
- **FR-007**: System MUST NOT fail the entire workflow if individual PR updates fail

### Non-Functional Requirements

- **NFR-001**: Auto-update workflow must not consume excessive GitHub Actions minutes (target: < 1 minute per execution)
- **NFR-002**: Solution must work with standard GitHub repository permissions (no admin access required)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero manual `gh api update-branch` commands needed after workflow fixes are merged to main
- **SC-002**: All open PRs are updated within 5 minutes of workflow file changes to main
- **SC-003**: PRs with merge conflicts do not block updates to other PRs
- **SC-004**: Workflow execution completes in under 60 seconds for repositories with up to 20 open PRs
- **SC-005**: `/poke-stale-prs` command successfully updates all eligible PRs in a single invocation

## Assumptions

- Repository uses GitHub Actions for CI/CD
- `GITHUB_TOKEN` has sufficient permissions to update PR branches (standard for PR-triggered workflows)
- PR branches are configured to allow updates from base branch (GitHub default)
- Open PRs target the `main` branch (or configurable base branch)
