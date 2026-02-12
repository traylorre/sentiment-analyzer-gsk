#!/usr/bin/env bash
# Scan repository for banned legacy framework terms.
# Exit 0 = clean, Exit 1 = banned terms found.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# Banned terms (case-insensitive matching)
BANNED_TERMS=(
  "fastapi"
  "mangum"
  "uvicorn"
  "starlette"
  "lambda.web.adapter"
  "LambdaAdapterLayer"
  "AWS_LWA"
)

# Excluded directories and files
# Note: --exclude-dir matches directory base names at any depth.
# For nested paths like specs/archive, we exclude "archive" but only under
# specific parents, so we use a post-filter approach for precision.
GREP_EXCLUDES=(
  "--exclude-dir=.git"
  "--exclude-dir=__pycache__"
  "--exclude-dir=node_modules"
  "--exclude-dir=.venv"
  "--exclude-dir=.pytest_cache"
  "--exclude-dir=.hypothesis"
  "--exclude=CONTEXT-CARRYOVER-*"
  "--exclude=check-banned-terms.sh"
  "--binary-files=without-match"
)

# Paths to exclude (relative to repo root, matched as prefixes)
EXCLUDE_PATHS=(
  "./specs/archive/"
  "./docs/archive/"
  "./docs/archived-specs/"
  "./docs/cache/"
  "./specs/1217-fastapi-infra-purge/"
  "./.specify/"
)

# Build grep -v filter for excluded paths
build_exclude_filter() {
  local filter=""
  for path in "${EXCLUDE_PATHS[@]}"; do
    if [ -n "$filter" ]; then
      filter="$filter|"
    fi
    # Escape dots and slashes for grep pattern
    local escaped
    escaped=$(echo "$path" | sed 's/\./\\./g')
    filter="$filter$escaped"
  done
  echo "$filter"
}

EXCLUDE_FILTER=$(build_exclude_filter)

FOUND=0
TOTAL_MATCHES=0

echo "=== Banned-Term Scanner ==="
echo "Scanning: $REPO_ROOT"
echo ""

for term in "${BANNED_TERMS[@]}"; do
  MATCHES=$(grep -rni "$term" "${GREP_EXCLUDES[@]}" . 2>/dev/null | grep -Ev "$EXCLUDE_FILTER" || true)
  if [ -n "$MATCHES" ]; then
    COUNT=$(echo "$MATCHES" | wc -l)
    TOTAL_MATCHES=$((TOTAL_MATCHES + COUNT))
    FOUND=1
    echo "FAIL: '$term' found ($COUNT matches):"
    echo "$MATCHES" | while IFS= read -r line; do
      echo "  $line"
    done
    echo ""
  fi
done

if [ "$FOUND" -eq 0 ]; then
  echo "PASS: Zero banned terms found."
  exit 0
else
  echo "FAIL: $TOTAL_MATCHES total banned-term matches found."
  exit 1
fi
