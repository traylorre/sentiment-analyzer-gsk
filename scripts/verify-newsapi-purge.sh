#!/bin/bash
# Verification script for newsapi purge
# Returns 0 if no occurrences found, 1 otherwise

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== NewsAPI Purge Verification ==="
echo "Repository: $REPO_ROOT"
echo ""

# Count occurrences excluding .git directory
NEWSAPI_COUNT=$(grep -ri "newsapi" . \
    --include="*.py" \
    --include="*.md" \
    --include="*.yaml" \
    --include="*.yml" \
    --include="*.tf" \
    --include="*.sh" \
    --include="*.html" \
    2>/dev/null | grep -v "\.git/" | wc -l || echo "0")

NEWS_API_COUNT=$(grep -ri "news_api" . \
    --include="*.py" \
    --include="*.md" \
    --include="*.yaml" \
    --include="*.yml" \
    --include="*.tf" \
    --include="*.sh" \
    --include="*.html" \
    2>/dev/null | grep -v "\.git/" | wc -l || echo "0")

TOTAL=$((NEWSAPI_COUNT + NEWS_API_COUNT))

echo "Results:"
echo "  - 'newsapi' occurrences: $NEWSAPI_COUNT"
echo "  - 'news_api' occurrences: $NEWS_API_COUNT"
echo "  - Total: $TOTAL"
echo ""

if [ "$TOTAL" -eq 0 ]; then
    echo "SUCCESS: No newsapi/news_api references found!"
    exit 0
else
    echo "FAILURE: Found $TOTAL references that need to be removed"
    echo ""
    echo "Files containing 'newsapi':"
    grep -ri "newsapi" . \
        --include="*.py" \
        --include="*.md" \
        --include="*.yaml" \
        --include="*.yml" \
        --include="*.tf" \
        --include="*.sh" \
        --include="*.html" \
        2>/dev/null | grep -v "\.git/" | head -20 || true
    exit 1
fi
