# Feature Specification: Dependabot Auto-Merge Configuration Audit

**Feature Branch**: `067-dependabot-automerge-audit`
**Created**: 2025-12-08
**Status**: Complete
**Input**: User description: "Audit Dependabot PRs for target repo, research why PR #313 mentions incomplete dependabot.yml, and provide holistic fixes following template repo methodologies"

## Problem Statement

The sentiment-analyzer-gsk repository has 5+ blocked Dependabot PRs that should auto-merge but aren't. Investigation reveals:

1. **PRs show "Dependabot Auto-Merge: SUCCESS" but `autoMergeRequest: null`** - workflow ran but didn't enable auto-merge
2. **No labels applied** - dependabot.yml specifies labels but PRs have none
3. **mergeStateStatus: BEHIND** - PRs fall behind main and don't rebase
4. **Major version bumps in "other-minor-patch" groups** - grouping configuration may be incorrect (pre-commit 3→4, pytest 8→9)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Routine Dependency Updates Auto-Merge (Priority: P1)

As a repository maintainer, I want minor and patch dependency updates to automatically merge after passing CI checks, so that I don't need to manually intervene for routine updates.

**Why this priority**: This is the core functionality that enables "1-year unattended operation" as documented in the dependabot.yml comments. Without working auto-merge, dependency PRs accumulate and require manual intervention.

**Independent Test**: Create a test PR simulating a minor/patch Dependabot update and verify it auto-merges within 24 hours without manual intervention.

**Acceptance Scenarios**:

1. **Given** a Dependabot PR for a minor version update (e.g., 1.0.0→1.1.0), **When** all CI checks pass, **Then** the PR is automatically approved and merged within 24 hours
2. **Given** a Dependabot PR for a patch version update (e.g., 1.0.0→1.0.1), **When** all CI checks pass, **Then** the PR is automatically approved and merged within 24 hours
3. **Given** a Dependabot PR that fails CI checks, **When** the workflow completes, **Then** auto-merge is NOT enabled and the PR remains open for review

---

### User Story 2 - Major Version Updates Require Review (Priority: P2)

As a repository maintainer, I want major version updates to be flagged for manual review with a clear comment explaining why, so that breaking changes don't slip through automatically.

**Why this priority**: Major version updates (e.g., pytest 8→9, pre-commit 3→4) can introduce breaking changes. The current system incorrectly groups some major updates in "other-minor-patch" which defeats the safety mechanism.

**Independent Test**: Create a test PR simulating a major Dependabot update and verify it receives a comment but does NOT auto-merge.

**Acceptance Scenarios**:

1. **Given** a Dependabot PR for a major version update (e.g., 1.0.0→2.0.0), **When** the workflow processes it, **Then** a comment is added explaining manual review is required AND auto-merge is NOT enabled
2. **Given** a Dependabot PR for pytest major update (8.x→9.x), **When** the workflow processes it, **Then** it is NOT grouped with minor/patch updates AND requires manual review
3. **Given** a Dependabot PR for pre-commit major update (3.x→4.x), **When** the workflow processes it, **Then** it is NOT grouped with minor/patch updates AND requires manual review

---

### User Story 3 - Labels Applied Correctly (Priority: P3)

As a repository maintainer, I want Dependabot PRs to have appropriate labels applied (dependencies, python, major/minor/patch), so that I can filter and triage PRs effectively.

**Why this priority**: Labels are important for filtering and reporting but don't block the core auto-merge functionality. This is a nice-to-have that improves maintainability.

**Independent Test**: Verify that a new Dependabot PR receives the labels specified in dependabot.yml configuration.

**Acceptance Scenarios**:

1. **Given** a new Dependabot PR for pip dependencies, **When** it is created, **Then** it has labels "dependencies" and "python" applied
2. **Given** a new Dependabot PR for GitHub Actions, **When** it is created, **Then** it has labels "dependencies" and "github-actions" applied

---

### User Story 4 - Future Major Auto-Merge Capability (Priority: P4)

As a repository maintainer, I want the system architecture to support enabling major version auto-merge in the future with pipeline guardrails, so that the system can be configured for full automation when desired.

**Why this priority**: This is a future enhancement that requires the current system to be properly architected. Not immediately needed but should be considered in the design.

**Independent Test**: Configuration can be modified to enable major auto-merge without code changes.

**Acceptance Scenarios**:

1. **Given** a desire to enable major version auto-merge, **When** the configuration is updated, **Then** major updates auto-merge after passing all CI checks without workflow code changes

---

### Edge Cases

- What happens when Dependabot creates a grouped PR with mixed major/minor updates?
- How does the system handle when a PR falls behind main and needs rebasing?
- What happens when `dependabot/fetch-metadata` fails to detect the update type?
- How are security updates handled differently from regular updates?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST enable auto-merge for Dependabot PRs classified as minor or patch version updates
- **FR-002**: System MUST NOT enable auto-merge for Dependabot PRs classified as major version updates
- **FR-003**: System MUST add explanatory comment to major version update PRs indicating manual review is required
- **FR-004**: System MUST correctly classify version update types using dependabot/fetch-metadata action
- **FR-005**: Dependabot configuration MUST NOT group major version updates with minor/patch updates
- **FR-006**: System MUST apply configured labels to Dependabot PRs as specified in dependabot.yml
- **FR-007**: Workflow MUST have sufficient permissions (contents: write, pull-requests: write) to enable auto-merge
- **FR-008**: System MUST handle GitHub Actions major version updates with auto-merge (these are considered safe per existing config)

### Key Entities

- **Dependabot PR**: A pull request automatically created by GitHub Dependabot for dependency updates
- **Update Type**: Classification of version change (semver-major, semver-minor, semver-patch)
- **Dependency Group**: Logical grouping of dependencies in dependabot.yml that receive updates together
- **Auto-merge Request**: GitHub API state indicating a PR is queued for automatic merge

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Minor/patch Dependabot PRs auto-merge within 24 hours of CI checks passing (0 stuck PRs)
- **SC-002**: Major version PRs receive comment and do NOT have auto-merge enabled (100% compliance)
- **SC-003**: Labels are correctly applied to all new Dependabot PRs (100% of PRs have expected labels)
- **SC-004**: Zero manual intervention required for routine minor/patch updates over a 30-day period
- **SC-005**: Configuration supports future enablement of major auto-merge without code changes

## Scope Boundaries

### In Scope

- Audit and fix dependabot.yml configuration issues
- Audit and fix pr-merge.yml workflow issues
- Research and apply GitHub Dependabot best practices (2024-2025)
- Document findings and configuration patterns
- Evaluate need for new `/dependabot-validate` methodology

### Out of Scope

- Immediately merging the backlogged PRs (address root cause first)
- Changing branch protection rules
- Adding new project dependencies
- Implementing the actual major auto-merge feature (just ensure architecture supports it)

## Assumptions

- GITHUB_TOKEN has sufficient permissions for pr merge operations
- Branch protection rules allow auto-merge when checks pass
- Dependabot service is correctly configured at the GitHub organization level
- Current workflow structure (pr-merge.yml) is the correct location for auto-merge logic

## Dependencies

- GitHub Dependabot service
- dependabot/fetch-metadata action
- GitHub Actions workflow permissions
- Branch protection configuration

## Canonical Sources

- [GitHub Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [dependabot/fetch-metadata Action](https://github.com/dependabot/fetch-metadata)
- [GitHub Auto-merge Documentation](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/automatically-merging-a-pull-request)
