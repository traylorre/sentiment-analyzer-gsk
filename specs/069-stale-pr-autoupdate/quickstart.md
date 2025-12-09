# Quickstart: Stale PR Auto-Update

**Feature**: 069-stale-pr-autoupdate
**Date**: 2025-12-08

## Prerequisites

- Write access to repository
- GitHub Actions enabled

## Implementation

### Step 1: Create Auto-Update Workflow

Create `.github/workflows/update-pr-branches.yml`:

```yaml
# Auto-update PR branches when workflow files change
# ===================================================
#
# When workflow files are fixed in main, existing PRs still run the
# old workflow from their branch. This workflow automatically updates
# all open PR branches when workflow files change.
#
# For On-Call Engineers:
#   - This workflow runs automatically on workflow file changes
#   - Check job logs to see which PRs were updated/skipped
#   - PRs with merge conflicts are skipped (not an error)

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
          prs=$(gh pr list --repo ${{ github.repository }} --state open --json number -q '.[].number')

          if [ -z "$prs" ]; then
            echo "No open PRs to update"
            exit 0
          fi

          echo "Found PRs: $prs"
          updated=0
          skipped=0

          for pr in $prs; do
            echo "Updating PR #$pr..."
            if gh api repos/${{ github.repository }}/pulls/$pr/update-branch -X PUT 2>/dev/null; then
              echo "✓ PR #$pr updated"
              ((updated++))
            else
              echo "⚠ PR #$pr skipped (likely has conflicts or is up to date)"
              ((skipped++))
            fi
          done

          echo ""
          echo "Summary: $updated updated, $skipped skipped"
```

### Step 2: Create Slash Command

Create `.claude/commands/poke-stale-prs.md`:

```markdown
# Poke Stale PRs

Update all open PR branches with the latest main branch.

## When to Use

- After merging a workflow fix to main
- When PRs show failing checks due to stale workflow files
- Before reviewing PRs to ensure they have latest main

## Implementation

Run the following bash commands to update all open PRs:

\`\`\`bash
# Get repository name
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

# List all open PRs and update each
for pr in $(gh pr list --state open --json number -q '.[].number'); do
  echo "Updating PR #$pr..."
  if gh api repos/$REPO/pulls/$pr/update-branch -X PUT 2>/dev/null; then
    echo "✓ PR #$pr updated"
  else
    echo "⚠ PR #$pr skipped (conflicts or up to date)"
  fi
done
\`\`\`
```

### Step 3: Commit and Push

```bash
git add .github/workflows/update-pr-branches.yml .claude/commands/poke-stale-prs.md
git commit -S -m "feat(069): Add stale PR auto-update workflow and slash command"
git push origin 069-stale-pr-autoupdate
```

### Step 4: Verify

1. Create a test PR
2. Merge a workflow change to main
3. Verify the test PR branch gets updated automatically
4. Test `/poke-stale-prs` command manually

## Success Criteria Verification

| Criterion | Verification |
|-----------|--------------|
| SC-001: Zero manual updates | Workflow auto-triggers on workflow changes |
| SC-002: Updates within 5 min | Workflow runs immediately on push |
| SC-003: Conflicts don't block | Error handling continues to next PR |
| SC-004: < 60s execution | Check workflow run time |
| SC-005: /poke-stale-prs works | Run command, verify PRs updated |

## Troubleshooting

### Workflow not triggering

1. Verify path filter matches changed files:
   ```bash
   git diff --name-only HEAD~1 | grep '.github/workflows/'
   ```

2. Check workflow is on main branch

### PRs not getting updated

1. Check workflow permissions:
   ```bash
   gh api repos/OWNER/REPO/actions/permissions
   ```

2. Verify GITHUB_TOKEN has write access to PR branches

### PR skipped due to conflicts

This is expected behavior. Resolve conflicts manually:
```bash
git checkout feature-branch
git fetch origin main
git rebase origin/main  # or git merge origin/main
# Resolve conflicts
git push --force-with-lease
```

## Reference

- [GitHub API: Update PR branch](https://docs.github.com/en/rest/pulls/pulls#update-a-pull-request-branch)
- [GitHub Actions: Path filtering](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#onpushpull_requestpull_request_targetpathspaths-ignore)
