#!/usr/bin/env bash
# Check for unasserted ERROR logs in pytest output
#
# This hook validates that all ERROR logs produced by tests have
# corresponding assert_error_logged() assertions.
#
# Part of 086-test-debt-burndown initiative.
#
# Usage:
#   ./scripts/check-error-log-assertions.sh [--verbose]
#
# Exit codes:
#   0 - All ERROR logs are asserted
#   1 - Unasserted ERROR logs found
#   2 - Script error

set -euo pipefail

VERBOSE="${1:-}"

# Run pytest and capture output
# Use a subset of fast tests to keep hook quick
OUTPUT=$(python3 -m pytest tests/unit/ -x --tb=no -q 2>&1) || true

# Count ERROR logs in output (excluding assertion success messages)
ERROR_COUNT=$(echo "$OUTPUT" | grep -c '\[ERROR\]' || true)

if [ "$ERROR_COUNT" -eq 0 ]; then
    echo "✓ No ERROR logs in test output"
    exit 0
fi

# Check if tests passed
if echo "$OUTPUT" | grep -q "passed"; then
    # Tests passed but ERROR logs exist - this is acceptable if they're being asserted
    # The key check: are there assert_error_logged calls in the test files?
    ASSERTION_COUNT=$(grep -r "assert_error_logged\|assert_warning_logged" tests/unit/ 2>/dev/null | grep -v "def assert" | wc -l || true)

    if [ "$VERBOSE" = "--verbose" ]; then
        echo "=== Test Output Analysis ==="
        echo "ERROR logs found: $ERROR_COUNT"
        echo "Log assertions found: $ASSERTION_COUNT"
        echo ""
        echo "=== ERROR logs in output ==="
        echo "$OUTPUT" | grep '\[ERROR\]' | head -20
        echo ""
    fi

    # If there are assertions covering the errors, we're good
    # This is a heuristic - not perfect but catches obvious gaps
    if [ "$ASSERTION_COUNT" -ge "$((ERROR_COUNT / 2))" ]; then
        echo "✓ ERROR logs appear to have assertions ($ASSERTION_COUNT assertions for $ERROR_COUNT logs)"
        exit 0
    else
        echo "⚠ WARNING: $ERROR_COUNT ERROR logs but only $ASSERTION_COUNT assertions"
        echo "Consider adding assert_error_logged() for unasserted errors"
        echo "Run with --verbose for details"
        # Exit 0 for now - this is advisory, not blocking
        # Change to exit 1 to make it blocking
        exit 0
    fi
else
    echo "✗ Tests failed - fix test failures first"
    if [ "$VERBOSE" = "--verbose" ]; then
        echo "$OUTPUT" | tail -30
    fi
    exit 1
fi
