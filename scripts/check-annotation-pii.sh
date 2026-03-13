#!/usr/bin/env bash
# T107/FR-184: CI gate — verify no PII leaks in X-Ray annotations.
#
# Scans all Python source files for span.set_attribute() and put_annotation()
# calls that might include PII fields (email, phone, name, address, ssn, etc.).
#
# Usage: scripts/check-annotation-pii.sh [exit 0 = pass, exit 1 = fail]

set -euo pipefail

SRC_DIR="src/lambdas"
ERRORS=0

# PII field patterns that should never appear in trace annotations
PII_PATTERNS=(
    'email'
    'phone'
    'ssn'
    'social_security'
    'credit_card'
    'card_number'
    'password'
    'secret'
    'token'
    'api_key'
    'address'
    'date_of_birth'
    'dob'
    'ip_address'
)

# Build regex alternation
PII_REGEX=$(IFS='|'; echo "${PII_PATTERNS[*]}")

# Find all annotation calls
FILES=$(grep -rl 'set_attribute\|put_annotation' "$SRC_DIR" --include='*.py' 2>/dev/null || true)

if [ -z "$FILES" ]; then
    echo "INFO: No annotation calls found in $SRC_DIR"
    exit 0
fi

for file in $FILES; do
    # Check annotation key names for PII patterns (case-insensitive)
    MATCHES=$(grep -inE "(set_attribute|put_annotation)\s*\(\s*[\"']($PII_REGEX)" "$file" 2>/dev/null || true)
    if [ -n "$MATCHES" ]; then
        echo "FAIL: $file contains potential PII in trace annotations:"
        echo "$MATCHES" | sed 's/^/  /'
        ERRORS=$((ERRORS + 1))
    fi
done

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "FAILED: $ERRORS file(s) with potential PII in trace annotations"
    echo "Fix: Use non-PII identifiers (user_id hash, config_id) instead of raw PII"
    exit 1
fi

echo "PASS: No PII detected in trace annotations across $SRC_DIR"
exit 0
