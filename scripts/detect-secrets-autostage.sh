#!/bin/bash
# Wrapper for detect-secrets that auto-stages baseline updates
# This eliminates the infinite loop where baseline updates keep failing
#
# Problem: detect-secrets updates line numbers in baseline on each scan,
#          causing pre-commit to fail requesting `git add .secrets.baseline`
#
# Solution: This wrapper auto-stages baseline changes and re-runs the hook
#           to ensure the commit includes the latest baseline.

set -e

BASELINE=".secrets.baseline"
MAX_RETRIES=3

run_hook() {
    detect-secrets-hook --baseline "$BASELINE" "$@"
}

# Run detect-secrets
for i in $(seq 1 $MAX_RETRIES); do
    if run_hook "$@"; then
        exit 0
    fi

    HOOK_EXIT=$?

    # Exit code 3: baseline was updated
    # Exit code 1: baseline not staged OR secrets found
    if [ $HOOK_EXIT -eq 3 ] || [ $HOOK_EXIT -eq 1 ]; then
        # Check if baseline actually changed
        if git diff --quiet "$BASELINE" 2>/dev/null; then
            # No changes - must be actual secrets found
            echo "ERROR: Secrets detected that are not in baseline"
            exit 1
        fi

        echo "Auto-staging updated baseline (attempt $i/$MAX_RETRIES)..."
        git add "$BASELINE"
    else
        # Other error
        exit $HOOK_EXIT
    fi
done

echo "ERROR: Could not stabilize baseline after $MAX_RETRIES attempts"
exit 1
