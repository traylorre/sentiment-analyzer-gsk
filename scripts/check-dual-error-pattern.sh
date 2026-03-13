#!/usr/bin/env bash
# T049/SC-100: CI gate — verify all OTel span except blocks in SSE Lambda
# use both set_status() AND record_exception() (FR-144, FR-150).
#
# Without both calls, X-Ray shows fault: false for genuine errors.
#
# Usage: scripts/check-dual-error-pattern.sh [exit 0 = pass, exit 1 = fail]

set -euo pipefail

SSE_DIR="src/lambdas/sse_streaming"
ERRORS=0

# Find Python files in SSE streaming that import OTel tracing
FILES=$(grep -rl 'get_tracer\|start_span\|start_as_current_span' "$SSE_DIR" --include='*.py' 2>/dev/null || true)

if [ -z "$FILES" ]; then
    echo "WARN: No OTel-instrumented files found in $SSE_DIR"
    exit 0
fi

for file in $FILES; do
    # Extract except blocks that reference spans (span variable in scope)
    # Look for except blocks that have span access but missing one of the dual calls

    # Count set_status and record_exception calls
    # Note: grep -c exits 1 when count is 0, so we use "|| true" and default
    SET_STATUS_COUNT=$(grep -c 'set_status(StatusCode\.ERROR' "$file" 2>/dev/null || true)
    SET_STATUS_COUNT=${SET_STATUS_COUNT:-0}
    RECORD_EXCEPTION_COUNT=$(grep -c 'record_exception(' "$file" 2>/dev/null || true)
    RECORD_EXCEPTION_COUNT=${RECORD_EXCEPTION_COUNT:-0}

    if [ "$SET_STATUS_COUNT" -ne "$RECORD_EXCEPTION_COUNT" ]; then
        echo "FAIL: $file — set_status count ($SET_STATUS_COUNT) != record_exception count ($RECORD_EXCEPTION_COUNT)"
        echo "      Every except block with OTel span error attribution MUST call BOTH:"
        echo "        span.set_status(StatusCode.ERROR, str(e))"
        echo "        span.record_exception(e)"
        ERRORS=$((ERRORS + 1))
    fi
done

# Also verify no except blocks have set_status without record_exception nearby
# Use awk to check paired usage within except blocks
for file in $FILES; do
    # Find except blocks containing set_status but NOT record_exception within 3 lines
    awk '
    /except.*:/ { in_except=1; has_set_status=0; has_record_exception=0; except_line=NR; next }
    in_except && /set_status\(StatusCode\.ERROR/ { has_set_status=1 }
    in_except && /record_exception\(/ { has_record_exception=1 }
    in_except && /^[^ ]/ && NR > except_line {
        if (has_set_status && !has_record_exception) {
            print "FAIL: " FILENAME ":" except_line " — set_status without record_exception"
            exit_code=1
        }
        if (!has_set_status && has_record_exception) {
            print "FAIL: " FILENAME ":" except_line " — record_exception without set_status"
            exit_code=1
        }
        in_except=0
    }
    END { exit exit_code }
    ' "$file" 2>/dev/null || ERRORS=$((ERRORS + 1))
done

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "FAILED: $ERRORS file(s) with incomplete dual-error pattern"
    echo "Fix: Every OTel-instrumented except block must call BOTH set_status AND record_exception"
    exit 1
fi

echo "PASS: All OTel except blocks in $SSE_DIR use dual-error pattern (set_status + record_exception)"
exit 0
