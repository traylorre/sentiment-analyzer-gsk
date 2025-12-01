#!/bin/bash
#
# Setup script to install git hooks for this project
# Run this after cloning the repository: ./scripts/setup-git-hooks.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "Installing git hooks for sentiment-analyzer-gsk..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Install pre-push hook
cat > "$HOOKS_DIR/pre-push" << 'HOOK_EOF'
#!/bin/bash
#
# Pre-push hook to:
# 1. Ensure feature branches are rebased on main
# 2. Run unit tests before pushing (prevents CI failures)
#
# This prevents merge commits and ensures Deploy Pipeline triggers correctly
#

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get current branch
current_branch=$(git rev-parse --abbrev-ref HEAD)

# Skip check for main branch itself
if [ "$current_branch" = "main" ]; then
    echo -e "${GREEN}✓ Pushing to main - no rebase check needed${NC}"
    exit 0
fi

# Check if this is a feature branch
if [[ "$current_branch" =~ ^(feat|fix|docs|chore|refactor|test|style|perf)/ ]]; then
    echo -e "${YELLOW}Checking if branch is rebased on main...${NC}"

    # Fetch latest main (but don't change working tree)
    git fetch origin main:refs/remotes/origin/main --quiet 2>/dev/null

    # Get merge base (common ancestor)
    merge_base=$(git merge-base HEAD origin/main)

    # Get latest commit on origin/main
    main_head=$(git rev-parse origin/main)

    # Check if branch is rebased (merge base should equal main head)
    if [ "$merge_base" != "$main_head" ]; then
        echo -e "${RED}✗ ERROR: Branch is not rebased on latest main!${NC}"
        echo ""
        echo "Your branch has diverged from main. You must rebase before pushing."
        echo ""
        echo "To fix this, run:"
        echo -e "${YELLOW}  git fetch origin main${NC}"
        echo -e "${YELLOW}  git rebase origin/main${NC}"
        echo ""
        echo "After resolving any conflicts:"
        echo -e "${YELLOW}  git push origin $current_branch --force-with-lease${NC}"
        echo ""
        exit 1
    fi

    echo -e "${GREEN}✓ Branch is rebased on latest main${NC}"
fi

# ============================================================================
# Run Unit Tests Before Push
# ============================================================================
# This catches test failures BEFORE they reach CI, saving time and preventing
# broken builds on main.
#
# Skip with: git push --no-verify (NOT recommended)
# ============================================================================

echo ""
echo -e "${YELLOW}🧪 Running unit tests before push...${NC}"
echo ""

# Run pytest with:
# - tests/unit/ only (fast, no preprod tests)
# - -x: stop on first failure (fast feedback)
# - --tb=short: concise tracebacks
# - -q: quiet output
# - -m "not preprod": exclude preprod tests (require real AWS)
if ! python3 -m pytest tests/unit/ -x --tb=short -q -m "not preprod" 2>&1; then
    echo ""
    echo -e "${RED}✗ ERROR: Unit tests failed!${NC}"
    echo ""
    echo "Fix the failing tests before pushing."
    echo ""
    echo "To run tests manually:"
    echo -e "${YELLOW}  pytest tests/unit/ -v${NC}"
    echo ""
    echo "To skip this check (NOT recommended):"
    echo -e "${YELLOW}  git push --no-verify${NC}"
    echo ""
    exit 1
fi

echo ""
echo -e "${GREEN}✓ All unit tests passed${NC}"
echo ""

exit 0
HOOK_EOF

chmod +x "$HOOKS_DIR/pre-push"

echo "✓ Installed pre-push hook"
echo ""
echo "Git hooks installed successfully!"
echo ""
echo "The pre-push hook will:"
echo "  - Ensure feature branches are rebased on main before pushing"
echo "  - Run unit tests to catch failures before CI"
echo "  - Prevent accidental merge commits"
echo ""
echo "To bypass the hook (not recommended): git push --no-verify"
