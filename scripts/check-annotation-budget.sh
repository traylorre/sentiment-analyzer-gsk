#!/usr/bin/env bash
# T108/FR-193: CI gate — verify annotation count stays within X-Ray limits.
#
# X-Ray limits: 50 annotations per segment, each key max 500 bytes,
# each value max 1000 bytes. This script counts unique annotation keys
# per file and flags files approaching the limit.
#
# Usage: scripts/check-annotation-budget.sh [exit 0 = pass, exit 1 = fail]

set -euo pipefail

SRC_DIR="src/lambdas"
MAX_ANNOTATIONS_PER_FILE=40  # Warn threshold (limit is 50)
ERRORS=0

# Find all files with annotations
FILES=$(grep -rl 'set_attribute\|put_annotation' "$SRC_DIR" --include='*.py' 2>/dev/null || true)

if [ -z "$FILES" ]; then
    echo "INFO: No annotation calls found in $SRC_DIR"
    exit 0
fi

for file in $FILES; do
    # Extract unique annotation key names
    KEYS=$(grep -oE "(set_attribute|put_annotation)\s*\(\s*[\"'][^\"']+[\"']" "$file" 2>/dev/null \
        | grep -oE "[\"'][^\"']+[\"']$" \
        | sort -u || true)

    KEY_COUNT=$(echo "$KEYS" | grep -c . 2>/dev/null || true)
    KEY_COUNT=${KEY_COUNT:-0}

    if [ "$KEY_COUNT" -gt "$MAX_ANNOTATIONS_PER_FILE" ]; then
        echo "FAIL: $file has $KEY_COUNT unique annotation keys (limit: 50, threshold: $MAX_ANNOTATIONS_PER_FILE)"
        echo "  Keys:"
        echo "$KEYS" | sed 's/^/    /'
        ERRORS=$((ERRORS + 1))
    fi

    # Check for annotation values that might exceed 1000 bytes
    # (heuristic: flag f-string annotations with complex expressions)
    LONG_VALUES=$(grep -nE "(set_attribute|put_annotation)\s*\(.*f[\"'].*\{.*\}.*[\"']" "$file" 2>/dev/null || true)
    if [ -n "$LONG_VALUES" ]; then
        # Only warn, don't fail — f-strings might be fine
        while IFS= read -r line; do
            LINENO_VAL=$(echo "$line" | cut -d: -f1)
            echo "WARN: $file:$LINENO_VAL — f-string annotation value (verify <1000 bytes at runtime)"
        done <<< "$LONG_VALUES"
    fi
done

if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "FAILED: $ERRORS file(s) exceed annotation budget threshold ($MAX_ANNOTATIONS_PER_FILE)"
    echo "Fix: Consolidate annotations or move metadata to span events instead"
    exit 1
fi

echo "PASS: All files within annotation budget ($MAX_ANNOTATIONS_PER_FILE per file, X-Ray limit: 50)"
exit 0
