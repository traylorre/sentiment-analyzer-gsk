# Implementation Plan: Stale PR Auto-Update

**Branch**: `069-stale-pr-autoupdate` | **Date**: 2025-12-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/069-stale-pr-autoupdate/spec.md`

## Summary

Implement automatic PR branch updates when workflow files change in main, plus a manual `/poke-stale-prs` slash command for on-demand updates. This eliminates manual intervention when CI workflow fixes are merged, unblocking stale PRs automatically.

## Technical Context

**Language/Version**: YAML (GitHub Actions workflow syntax), Bash (slash command)
**Primary Dependencies**: GitHub Actions, GitHub CLI (`gh`), GitHub REST API
**Storage**: N/A (workflow configuration only)
**Testing**: Manual verification via PR creation and workflow trigger observation
**Target Platform**: GitHub Actions runner (ubuntu-latest)
**Project Type**: CI/CD automation (workflow + slash command)
**Performance Goals**: < 60 seconds execution for up to 20 open PRs
**Constraints**: Must use existing GITHUB_TOKEN permissions, no additional secrets
**Scale/Scope**: Single workflow file, single slash command file

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | Feature branch workflow, GPG signing, no bypass |
| **Pipeline Check Bypass** | PASS | Enhances pipeline, doesn't bypass any checks |
| **Testing & Validation** | N/A | Workflow config, manual validation via PR checks |
| **Security & Access Control** | PASS | Uses existing GITHUB_TOKEN, no new permissions |
| **Deterministic Time Handling** | N/A | No time-dependent code |
| **Tech Debt Tracking** | PASS | No shortcuts - proper implementation |

**Gate Evaluation**: All applicable gates PASS. This is a CI automation that improves developer workflow.

## Project Structure

### Documentation (this feature)

```text
specs/069-stale-pr-autoupdate/
├── plan.md              # This file
├── research.md          # Phase 0: GitHub API research
├── quickstart.md        # Phase 1: Step-by-step implementation guide
└── tasks.md             # Phase 2: Implementation tasks (created by /speckit.tasks)
```

### Source Code (repository root)

```text
.github/
└── workflows/
    └── update-pr-branches.yml    # New: Auto-update workflow

.claude/
└── commands/
    └── poke-stale-prs.md         # New: Manual slash command
```

**Structure Decision**: Two new files - one GitHub Actions workflow triggered on push to main when workflow files change, one slash command for manual triggering.

## Complexity Tracking

> No violations requiring justification. This is a minimal automation feature with two simple files.

---

## Phase 0: Research ✅ COMPLETE

### Research Summary

No NEEDS CLARIFICATION items - GitHub API for updating PR branches is well-documented.

| Topic | Finding | Source |
|-------|---------|--------|
| Update branch API | `PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch` | [GitHub REST API Docs](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request-branch) |
| Required permissions | `contents: write` on workflow, uses existing `GITHUB_TOKEN` | GitHub Actions default permissions |
| Error handling | API returns 422 if branch cannot be updated (conflicts) | GitHub API response codes |
| Path filtering | `on.push.paths` supports glob patterns like `.github/workflows/**` | GitHub Actions workflow syntax |

### Research Output
→ [research.md](./research.md) - Full findings documented

---

## Phase 1: Design ✅ COMPLETE

This is a configuration-only feature - no data model or API contracts needed.

### Workflow Design

**File**: `.github/workflows/update-pr-branches.yml`

```yaml
name: Update PR Branches

on:
  push:
    branches: [main]
    paths:
      - '.github/workflows/**'

jobs:
  update-prs:
    name: Update Open PRs
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - name: Update all open PR branches
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          echo "Fetching open PRs..."
          prs=$(gh pr list --repo ${{ github.repository }} --state open --json number,headRefName -q '.[].number')

          if [ -z "$prs" ]; then
            echo "No open PRs to update"
            exit 0
          fi

          echo "Found PRs: $prs"

          for pr in $prs; do
            echo "Updating PR #$pr..."
            if gh api repos/${{ github.repository }}/pulls/$pr/update-branch -X PUT 2>/dev/null; then
              echo "✓ PR #$pr updated"
            else
              echo "⚠ PR #$pr skipped (likely has conflicts)"
            fi
          done

          echo "Done!"
```

### Slash Command Design

**File**: `.claude/commands/poke-stale-prs.md`

```markdown
# Poke Stale PRs

Update all open PR branches with the latest main branch.

## Usage

Run this command when PRs need to be updated with workflow fixes from main.

## Implementation

Run the following command:

```bash
gh pr list --state open --json number -q '.[].number' | while read pr; do
  echo "Updating PR #$pr..."
  gh api repos/$(gh repo view --json nameWithOwner -q .nameWithOwner)/pulls/$pr/update-branch -X PUT 2>/dev/null && echo "✓ Updated" || echo "⚠ Skipped (conflicts)"
done
```
```

### Phase 1 Output
→ [quickstart.md](./quickstart.md) - Step-by-step implementation guide

---

## Constitution Re-Check (Post-Design)

| Gate | Status | Notes |
|------|--------|-------|
| **Git Workflow & CI/CD Rules** | PASS | No workflow bypass |
| **Pipeline Check Bypass** | PASS | Enhances pipeline, doesn't bypass |
| **Testing & Validation** | PASS | Manual validation via PR observation |
| **Security & Access Control** | PASS | Uses existing GITHUB_TOKEN |
| **Tech Debt Tracking** | PASS | No new debt introduced |

**Gate Evaluation**: All gates PASS. Ready for `/speckit.tasks`.
