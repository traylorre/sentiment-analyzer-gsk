#!/bin/bash
# Quick workflow status checker
# Usage: ./scripts/check-workflows.sh [commit-sha or PR-number]

set -euo pipefail

REPO="traylorre/sentiment-analyzer-gsk"

if [[ $# -eq 0 ]]; then
    # No arguments - check latest main commit
    echo "Checking latest main commit workflows..."
    COMMIT=$(git rev-parse origin/main)
else
    ARG=$1
    if [[ $ARG =~ ^[0-9]+$ ]]; then
        # Argument is a number - treat as PR number
        echo "Checking PR #$ARG workflows..."
        COMMIT=$(gh pr view "$ARG" --repo "$REPO" --json headRefOid --jq '.headRefOid')
    else
        # Argument is a commit SHA
        echo "Checking commit $ARG workflows..."
        COMMIT=$ARG
    fi
fi

echo "Commit: $COMMIT"
echo ""
echo "======================================================================"
echo "WORKFLOW STATUS"
echo "======================================================================"

# Get all workflows for this commit
gh run list --repo "$REPO" --commit "$COMMIT" --json name,conclusion,databaseId,workflowName,createdAt --limit 20 | \
    jq -r '.[] |
        "\(.workflowName): \(.conclusion // "running") (ID: \(.databaseId))"' | \
    sed 's/success/✅ SUCCESS/g' | \
    sed 's/failure/❌ FAILURE/g' | \
    sed 's/skipped/⏭️  SKIPPED/g' | \
    sed 's/running/🔄 RUNNING/g'

echo ""
echo "======================================================================"
echo "FAILED WORKFLOWS (if any)"
echo "======================================================================"

# Get failed workflows and show brief error summary
FAILED_RUNS=$(gh run list --repo "$REPO" --commit "$COMMIT" --json conclusion,databaseId,workflowName --limit 20 | \
    jq -r '.[] | select(.conclusion == "failure") | .databaseId')

if [[ -z "$FAILED_RUNS" ]]; then
    echo "✅ No failed workflows"
else
    for RUN_ID in $FAILED_RUNS; do
        WORKFLOW_NAME=$(gh run view "$RUN_ID" --repo "$REPO" --json workflowName --jq '.workflowName')
        echo ""
        echo "❌ FAILED: $WORKFLOW_NAME (ID: $RUN_ID)"
        echo "   View logs: gh run view $RUN_ID --repo $REPO --log-failed"
        echo "   Full URL: https://github.com/$REPO/actions/runs/$RUN_ID"
        echo ""
        echo "   Failed jobs:"
        gh api "repos/$REPO/actions/runs/$RUN_ID/jobs" --jq \
            '.jobs[] | select(.conclusion == "failure") | "   - \(.name)"'
    done
fi

echo ""
echo "======================================================================"
echo "QUICK COMMANDS"
echo "======================================================================"
echo "View specific workflow logs:"
echo "  gh run view <RUN_ID> --repo $REPO --log-failed"
echo ""
echo "Re-run failed workflows:"
echo "  gh run rerun <RUN_ID> --repo $REPO"
