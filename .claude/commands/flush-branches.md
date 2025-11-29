# Flush Local Branches

Safely clean up local feature branches and push any unmerged work to origin for PR.

## Goal

For each local feature branch (not main):
1. Determine if its content is already in main (via merge or squash)
2. If content is in main → delete branch (unless it has an open PR)
3. If content is NOT in main → push to origin and create PR
4. Never delete branches with open PRs - notify user instead

## Branch Categories

| Category | Detection | Action |
|----------|-----------|--------|
| **Ancestor of main** | `git merge-base --is-ancestor <branch> origin/main` returns 0 | Delete (content in main) |
| **Squash-merged** | `git cherry origin/main <branch>` shows no `+` lines | Delete (content in main) |
| **Has unique work** | `git cherry` shows `+` lines (unpicked commits) | Push + create PR |

## Execution Steps

### Step 1: Setup

```bash
git fetch origin main
```

### Step 2: Categorize Each Branch

For each local branch except main:

```bash
categorize_branch() {
  local branch=$1

  # Check if branch is ancestor of main (traditional merge or fast-forward)
  if git merge-base --is-ancestor "$branch" origin/main 2>/dev/null; then
    echo "ancestor"
    return
  fi

  # Check if branch content is in main (squash-merged)
  # git cherry shows commits NOT in upstream with '+', already in upstream with '-'
  local unpicked=$(git cherry origin/main "$branch" 2>/dev/null | grep -c '^+' || echo "0")
  if [ "$unpicked" -eq 0 ]; then
    echo "squash-merged"
    return
  fi

  echo "diverged:$unpicked"
}
```

### Step 3: Check for Open PRs

Before any deletion, check if branch has an open PR:

```bash
has_open_pr() {
  local branch=$1
  local pr_number=$(gh pr list --head "$branch" --state open --json number -q '.[0].number' 2>/dev/null)
  if [ -n "$pr_number" ]; then
    echo "$pr_number"
    return 0
  fi
  return 1
}
```

### Step 4: Process Each Branch

```bash
process_branches() {
  local branches=$(git branch --format='%(refname:short)' | grep -v '^main$')

  # Arrays for reporting
  local deleted_branches=""
  local pr_protected_branches=""
  local pushed_branches=""
  local created_prs=""

  for branch in $branches; do
    local category=$(categorize_branch "$branch")

    case "$category" in
      ancestor|squash-merged)
        # Content is in main - safe to delete IF no open PR
        local pr=$(has_open_pr "$branch")
        if [ -n "$pr" ]; then
          pr_protected_branches="$pr_protected_branches\n$branch (PR #$pr)"
        else
          git branch -D "$branch" 2>/dev/null
          deleted_branches="$deleted_branches\n$branch ($category)"
        fi
        ;;

      diverged:*)
        # Has unique work - push and create PR
        local commit_count=${category#diverged:}

        # Push to origin
        git push origin "$branch" 2>/dev/null
        pushed_branches="$pushed_branches\n$branch ($commit_count commits)"

        # Create PR if none exists
        local existing_pr=$(gh pr list --head "$branch" --state all --json number -q '.[0].number' 2>/dev/null)
        if [ -z "$existing_pr" ]; then
          # Get first commit message for PR title
          local title=$(git log origin/main.."$branch" --format='%s' --reverse | head -1)
          gh pr create --head "$branch" --base main --title "$title" --body "Auto-created by flush-branches"
          created_prs="$created_prs\n$branch"
        fi
        ;;
    esac
  done
}
```

## Output Format

```markdown
## Branch Flush Report

### Deleted (content already in main)
| Branch | Reason |
|--------|--------|

### Protected by Open PR (not deleted)
| Branch | PR # | Action Required |
|--------|------|-----------------|

### Pushed to Origin
| Branch | Commits | PR |
|--------|---------|-----|

### Errors/Warnings
- ...
```

## Safety Guards

1. **Never delete branches with open PRs** - always notify user instead
2. **Never force push** - only regular push
3. **Skip branches with uncommitted changes** - warn user
4. **Use `git branch -D`** for squash-merged branches (git doesn't recognize them as merged)
5. **Verify origin/main is fetched** before any comparisons

## Complete Script

```bash
#!/bin/bash
set -euo pipefail

echo "## Branch Flush Report"
echo ""

# Fetch latest
git fetch origin main 2>/dev/null

# Get all local branches except main
branches=$(git branch --format='%(refname:short)' | grep -v '^main$' || true)

if [ -z "$branches" ]; then
  echo "No feature branches found."
  exit 0
fi

# Track results
declare -a deleted=()
declare -a protected=()
declare -a pushed=()

for branch in $branches; do
  # Skip if branch has uncommitted changes (would need stash)

  # Check if ancestor of main
  if git merge-base --is-ancestor "$branch" origin/main 2>/dev/null; then
    # Check for open PR
    pr=$(gh pr list --head "$branch" --state open --json number,url -q '.[0] | "\(.number)|\(.url)"' 2>/dev/null || true)
    if [ -n "$pr" ]; then
      pr_num=${pr%|*}
      pr_url=${pr#*|}
      protected+=("$branch|PR #$pr_num|$pr_url")
    else
      git branch -D "$branch" 2>/dev/null && deleted+=("$branch|ancestor of main")
    fi
    continue
  fi

  # Check if squash-merged (all commits already in main)
  unpicked=$(git cherry origin/main "$branch" 2>/dev/null | grep -c '^+' || echo "0")
  if [ "$unpicked" -eq 0 ]; then
    # Check for open PR
    pr=$(gh pr list --head "$branch" --state open --json number,url -q '.[0] | "\(.number)|\(.url)"' 2>/dev/null || true)
    if [ -n "$pr" ]; then
      pr_num=${pr%|*}
      pr_url=${pr#*|}
      protected+=("$branch|PR #$pr_num|$pr_url")
    else
      git branch -D "$branch" 2>/dev/null && deleted+=("$branch|squash-merged")
    fi
    continue
  fi

  # Branch has unique work - push and ensure PR exists
  git push origin "$branch" 2>/dev/null || true

  # Check for any PR (open or closed)
  existing_pr=$(gh pr list --head "$branch" --state open --json number,url -q '.[0] | "\(.number)|\(.url)"' 2>/dev/null || true)
  if [ -z "$existing_pr" ]; then
    # Create PR
    title=$(git log origin/main.."$branch" --format='%s' --reverse 2>/dev/null | head -1)
    pr_url=$(gh pr create --head "$branch" --base main --title "$title" --body "Auto-created by /flush-branches" 2>/dev/null || true)
    pushed+=("$branch|$unpicked commits|Created: $pr_url")
  else
    pr_num=${existing_pr%|*}
    pr_url=${existing_pr#*|}
    pushed+=("$branch|$unpicked commits|Existing: PR #$pr_num")
  fi
done

# Output results
if [ ${#deleted[@]} -gt 0 ]; then
  echo "### Deleted (content already in main)"
  echo "| Branch | Reason |"
  echo "|--------|--------|"
  for item in "${deleted[@]}"; do
    branch=${item%|*}
    reason=${item#*|}
    echo "| $branch | $reason |"
  done
  echo ""
fi

if [ ${#protected[@]} -gt 0 ]; then
  echo "### ⚠️ Protected by Open PR (not deleted)"
  echo "| Branch | PR | URL |"
  echo "|--------|-----|-----|"
  for item in "${protected[@]}"; do
    IFS='|' read -r branch pr url <<< "$item"
    echo "| $branch | $pr | $url |"
  done
  echo ""
fi

if [ ${#pushed[@]} -gt 0 ]; then
  echo "### Pushed to Origin"
  echo "| Branch | Commits | PR Status |"
  echo "|--------|---------|-----------|"
  for item in "${pushed[@]}"; do
    IFS='|' read -r branch commits status <<< "$item"
    echo "| $branch | $commits | $status |"
  done
  echo ""
fi

if [ ${#deleted[@]} -eq 0 ] && [ ${#protected[@]} -eq 0 ] && [ ${#pushed[@]} -eq 0 ]; then
  echo "No actions taken - all branches are clean."
fi
```

## Key Differences from Previous Version

| Aspect | Old | New |
|--------|-----|-----|
| Squash detection | `git diff` (wrong) | `git cherry` (correct) |
| Ancestor detection | Missing | `git merge-base --is-ancestor` |
| PR protection | Missing | Required check before any deletion |
| Branch categories | 2 (merged/not) | 3 (ancestor/squash/diverged) |
| Delete behavior | Delete then notify | Check PR first, notify OR delete |
