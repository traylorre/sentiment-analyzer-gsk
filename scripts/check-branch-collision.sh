#!/usr/bin/env bash
# Check for orphaned remote branches before push
#
# This hook prevents branch name collisions and orphaned branches by:
# 1. Checking if the branch being pushed already exists on remote
# 2. If it does, verifying there's an associated PR
# 3. If no PR exists, warning about potential orphan
#
# The branch judged is the push's remote ref. pre-commit's pre-push stage
# consumes git's stdin and exports that ref as PRE_COMMIT_REMOTE_BRANCH, for
# the first ref carrying commits the remote lacks. Run by hand, the
# checked-out branch stands in.
#
# card-<n> branches are Hydrostat claim refs: one exists on the remote for
# every live card and never has a PR.
#
# Part of 143-orphan-branch-prevention initiative.
#
# Usage:
#   ./scripts/check-branch-collision.sh
#
# Exit codes:
#   0 - Safe to push (new branch or has PR)
#   1 - Orphan detected (branch exists without PR)
#   2 - Script error

set -euo pipefail

REMOTE="${PRE_COMMIT_REMOTE_NAME:-origin}"

if [[ -n "${PRE_COMMIT_REMOTE_BRANCH:-}" ]]; then
    case "$PRE_COMMIT_REMOTE_BRANCH" in
        refs/heads/*) BRANCH="${PRE_COMMIT_REMOTE_BRANCH#refs/heads/}" ;;
        *)
            echo "✓ '$PRE_COMMIT_REMOTE_BRANCH' is not a branch - nothing to check"
            exit 0
            ;;
    esac
else
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
fi

# Skip check for main/master branches
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    exit 0
fi

if [[ "$BRANCH" =~ ^card-[0-9]+$ ]]; then
    echo "✓ '$BRANCH' is a Hydrostat claim ref - safe to push"
    exit 0
fi

# Check if branch exists on remote
REMOTE_EXISTS=$(git ls-remote "$REMOTE" "refs/heads/$BRANCH" 2>/dev/null | wc -l)

if [ "$REMOTE_EXISTS" -eq 0 ]; then
    # Branch doesn't exist on remote - new branch, safe to push
    echo "✓ New branch '$BRANCH' - safe to push"
    exit 0
fi

# Branch exists on remote - check if there's an associated PR
if ! command -v gh &> /dev/null; then
    echo "⚠ gh CLI not found - skipping PR check"
    exit 0
fi

PR_COUNT=$(gh pr list --state all --head "$BRANCH" --json number --jq 'length' 2>/dev/null || echo "0")

if [ "$PR_COUNT" -eq 0 ]; then
    echo ""
    echo "⚠ ORPHAN BRANCH DETECTED"
    echo "========================"
    echo "Branch '$BRANCH' exists on remote but has no associated PR."
    echo ""
    echo "This can happen when:"
    echo "  1. A push failed and you created a new branch"
    echo "  2. The original branch was left orphaned on remote"
    echo ""
    echo "To fix:"
    echo "  Option 1: Delete the remote orphan and push"
    echo "    git push $REMOTE --delete $BRANCH"
    echo "    git push -u origin HEAD"
    echo ""
    echo "  Option 2: Use a different branch name"
    echo "    git checkout -b NEW-BRANCH-NAME"
    echo "    git push -u origin HEAD"
    echo ""
    echo "  Option 3: Skip this check (not recommended)"
    echo "    git push --no-verify"
    echo ""
    exit 1
fi

# Branch has PR - safe to push (update existing PR)
echo "✓ Branch '$BRANCH' has PR - safe to push"
exit 0
