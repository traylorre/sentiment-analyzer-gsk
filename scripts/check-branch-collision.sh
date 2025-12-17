#!/usr/bin/env bash
# Check for orphaned remote branches before push
#
# This hook prevents branch name collisions and orphaned branches by:
# 1. Checking if the current branch already exists on remote
# 2. If it does, verifying there's an associated PR
# 3. If no PR exists, warning about potential orphan
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

# Get current branch name
BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Skip check for main/master branches
if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
    exit 0
fi

# Check if branch exists on remote
REMOTE_EXISTS=$(git ls-remote --heads origin "$BRANCH" 2>/dev/null | wc -l)

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
    echo "    git push origin --delete $BRANCH"
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
