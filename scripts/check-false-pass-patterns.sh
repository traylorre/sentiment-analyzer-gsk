#!/bin/bash
# check-false-pass-patterns.sh - Pre-commit hook to prevent false-pass test patterns
#
# Blocks patterns that mask test failures:
# - status_code == 500 followed by pytest.skip
# - Other patterns that hide server errors
#
# Usage: scripts/check-false-pass-patterns.sh [--staged-only]

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

STAGED_ONLY=false
if [[ "${1:-}" == "--staged-only" ]]; then
    STAGED_ONLY=true
fi

errors=0

check_file() {
    local file="$1"

    # Check for 500 error masking: status_code == 500 followed by pytest.skip
    while IFS=: read -r line_num _; do
        # Check next 5 lines for pytest.skip
        if sed -n "$((line_num+1)),$((line_num+5))p" "$file" | grep -q "pytest.skip"; then
            echo -e "${RED}ERROR${NC}: False-pass pattern in $file:$line_num"
            echo "       500 error followed by pytest.skip masks server failures"
            ((errors++))
        fi
    done < <(grep -n "status_code == 500" "$file" 2>/dev/null || true)
}

echo "Checking for false-pass test patterns..."

if $STAGED_ONLY; then
    # Check only staged Python test files
    files=$(git diff --cached --name-only --diff-filter=ACM | grep -E '^tests/.*\.py$' || true)
else
    # Check all E2E test files
    files=$(find tests/e2e -name "*.py" -type f 2>/dev/null || true)
fi

if [[ -z "$files" ]]; then
    echo -e "${GREEN}No test files to check${NC}"
    exit 0
fi

while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    check_file "$file"
done <<< "$files"

if [[ $errors -eq 0 ]]; then
    echo -e "${GREEN}No false-pass patterns detected${NC}"
    exit 0
else
    echo ""
    echo "Found $errors false-pass pattern(s)."
    echo ""
    echo "Fix: Remove 'if status_code == 500: pytest.skip()' patterns."
    echo "     Tests should FAIL on 500 errors, not skip."
    echo ""
    echo "See: specs/093-e2e-false-pass-remediation/spec.md"
    exit 1
fi
