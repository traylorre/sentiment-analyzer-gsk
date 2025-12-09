# Poke Stale PRs

Update all open PR branches with the latest main branch.

## When to Use

- After merging a workflow fix to main (if auto-update hasn't run yet)
- When PRs show failing checks due to stale workflow files
- Before reviewing PRs to ensure they have latest main
- To manually trigger what the auto-update workflow does

## What This Does

1. Lists all open PRs in the repository
2. For each PR, calls the GitHub API to update the branch with main
3. Skips PRs that have merge conflicts (they need manual rebase)
4. Reports which PRs were updated vs skipped

## Implementation

Run the following bash commands to update all open PRs:

```bash
# Get repository name
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo "Repository: $REPO"
echo ""

# List all open PRs
prs=$(gh pr list --state open --json number -q '.[].number')

if [ -z "$prs" ]; then
  echo "No open PRs to update"
  exit 0
fi

echo "Found open PRs: $prs"
echo ""

# Update each PR
updated=0
skipped=0

for pr in $prs; do
  echo "Updating PR #$pr..."
  if gh api repos/$REPO/pulls/$pr/update-branch -X PUT 2>/dev/null; then
    echo "  ✓ Updated"
    ((updated++))
  else
    echo "  ⚠ Skipped (conflicts or up to date)"
    ((skipped++))
  fi
done

echo ""
echo "=== Summary ==="
echo "Updated: $updated"
echo "Skipped: $skipped"
```

## Related

- **Automatic version**: `.github/workflows/update-pr-branches.yml` runs automatically when workflow files change in main
- **GitHub API**: Uses `PUT /repos/{owner}/{repo}/pulls/{pull_number}/update-branch`

## Troubleshooting

### PR skipped due to conflicts

The PR branch has merge conflicts with main. Fix manually:

```bash
git checkout feature-branch
git fetch origin main
git rebase origin/main  # or git merge origin/main
# Resolve conflicts
git push --force-with-lease
```

### Permission denied

Ensure you're authenticated with `gh`:

```bash
gh auth status
gh auth login  # if needed
```
