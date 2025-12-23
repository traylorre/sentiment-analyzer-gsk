# Feature Specification: Re-trigger PR Checks After Branch Auto-Update

**Branch**: `1028-retrigger-pr-checks`
**Created**: 2025-12-22
**Status**: Implementation
**Priority**: P1 - CI Blocking

## Purpose

Ensure PR checks run after `update-pr-branches.yml` merges main into PR branches. Currently, auto-updated PRs get stuck in "Waiting for status to be reported" state.

## Problem Statement

- `update-pr-branches.yml` runs on `push: branches: [main]` with `paths: ['.github/workflows/**']`
- When workflow files change in main, it calls `gh api repos/.../pulls/$pr/update-branch` for each open PR
- This creates a merge commit on the PR branch (push to feature branch)
- `pr-checks.yml` triggers on:
  - `push: branches: [main, 'dependabot/**']` - NOT feature branches
  - `pull_request: branches: [main]` - NOT direct pushes
- Result: PR branch updated but no checks run, PR stuck waiting

## Root Cause Analysis

The GitHub update-branch API creates a merge commit that:
1. Is pushed to the feature branch (not main)
2. Is NOT a pull_request event (it's a push from the GitHub Actions bot)
3. Doesn't match any trigger in pr-checks.yml

## Solution

After each successful branch update in `update-pr-branches.yml`, trigger `pr-checks.yml` via `workflow_dispatch`:

```bash
gh workflow run pr-checks.yml --ref <branch-name>
```

This leverages the existing `workflow_dispatch:` trigger at line 19 of pr-checks.yml.

## User Story 1 - Auto-triggered Checks (Priority: P1)

As a developer, I want PR checks to automatically run after my branch is auto-updated so that I don't have to manually re-trigger them.

**Acceptance Scenarios**:

1. **Given** an open PR with outdated workflow files, **When** update-pr-branches.yml updates the branch, **Then** pr-checks.yml runs on that branch within 60 seconds
2. **Given** an open PR that fails to update (conflicts), **When** update-pr-branches.yml skips it, **Then** no workflow is triggered for that PR

## User Story 2 - Visibility (Priority: P2)

As an on-call engineer, I want to see which PRs had checks re-triggered so that I can monitor the automation.

**Acceptance Scenarios**:

1. **Given** a successful branch update, **When** workflow_dispatch is triggered, **Then** the job log shows "Triggered pr-checks.yml on branch <name>"
2. **Given** a failed workflow trigger, **When** gh workflow run fails, **Then** the job log shows warning (non-blocking)

## Files to Modify

1. `.github/workflows/update-pr-branches.yml` (lines 59-68): Add `gh workflow run` after successful update

## Implementation Details

Current loop (lines 59-68):
```yaml
for pr in $prs; do
  echo "Updating PR #$pr..."
  if gh api repos/${{ github.repository }}/pulls/$pr/update-branch -X PUT 2>/dev/null; then
    echo "  ✓ PR #$pr updated successfully"
    updated=$((updated + 1))
  else
    echo "  ⚠ PR #$pr skipped (likely has conflicts or is up to date)"
    skipped=$((skipped + 1))
  fi
done
```

Modified loop:
```yaml
for pr in $prs; do
  echo "Updating PR #$pr..."
  # Get branch name for this PR
  branch=$(gh pr view $pr --repo ${{ github.repository }} --json headRefName -q '.headRefName')

  if gh api repos/${{ github.repository }}/pulls/$pr/update-branch -X PUT 2>/dev/null; then
    echo "  ✓ PR #$pr updated successfully"
    updated=$((updated + 1))

    # Trigger pr-checks.yml on the updated branch
    echo "  → Triggering pr-checks.yml on branch '$branch'..."
    if gh workflow run pr-checks.yml --repo ${{ github.repository }} --ref "$branch"; then
      echo "  ✓ pr-checks.yml triggered"
    else
      echo "  ⚠ Failed to trigger pr-checks.yml (non-blocking)"
    fi
  else
    echo "  ⚠ PR #$pr skipped (likely has conflicts or is up to date)"
    skipped=$((skipped + 1))
  fi
done
```

## Permissions

The job already has `contents: write` and `pull-requests: write`. Need to verify if `actions: write` is needed for `gh workflow run`.

According to GitHub docs, triggering workflow_dispatch requires:
- `actions: write` permission on the repository

Add to permissions block:
```yaml
permissions:
  contents: write
  pull-requests: write
  actions: write  # Required for gh workflow run
```

## Validation

1. Local: Review workflow syntax with `actionlint` if available
2. CI: Create test PR, merge workflow change to main, verify checks run on test PR
3. Manual: `gh workflow run pr-checks.yml --ref <test-branch>` works

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Workflow trigger fails | Non-blocking (continue-on-error pattern with warning log) |
| Rate limiting on many PRs | Serial execution already in place |
| Duplicate workflow runs | workflow_dispatch creates distinct run, acceptable |

## Rollback Plan

Remove the `gh workflow run` block and `actions: write` permission. PRs would return to manual check triggering.
