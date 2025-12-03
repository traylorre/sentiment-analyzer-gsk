#!/usr/bin/env bash
# IAM Resource Pattern Validator
#
# Validates:
# - Property: resource_name_pattern - All resources use {env}-sentiment-{service}
# - Property: iam_pattern_coverage - IAM ARN patterns cover all resource names
#
# Usage: ./scripts/check-iam-patterns.sh [--fix]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TF_DIR="$REPO_ROOT/infrastructure/terraform"
IAM_POLICY_FILE="$TF_DIR/ci-user-policy.tf"

# Valid naming pattern: {env}-sentiment-{service}
# After normalization, ${var.environment} becomes {env}
VALID_PATTERN='^(\{env\}|preprod|prod)-sentiment-[a-z0-9-]+$'
LEGACY_PATTERN='^sentiment-analyzer-'

# Track errors
ERRORS=0
WARNINGS=0

echo "=========================================="
echo "IAM Resource Pattern Validator"
echo "=========================================="
echo ""

# Check if terraform directory exists
if [[ ! -d "$TF_DIR" ]]; then
    echo -e "${RED}ERROR: Terraform directory not found: $TF_DIR${NC}"
    exit 1
fi

# Check if IAM policy file exists
if [[ ! -f "$IAM_POLICY_FILE" ]]; then
    echo -e "${RED}ERROR: IAM policy file not found: $IAM_POLICY_FILE${NC}"
    exit 1
fi

echo "Checking Terraform files in: $TF_DIR"
echo "IAM Policy file: $IAM_POLICY_FILE"
echo ""

# =============================================================================
# Step 1: Extract resource names from Terraform files
# =============================================================================
echo "Step 1: Extracting resource names from Terraform..."
echo "-------------------------------------------"

declare -A RESOURCE_NAMES
declare -a LEGACY_RESOURCES=()
declare -a INVALID_RESOURCES=()

# Normalize name: replace ${var.environment} with {env} for pattern validation
normalize_name() {
    local name="$1"
    # Replace Terraform variable interpolation with placeholder using sed
    # Bash parameter expansion has issues with nested braces
    name=$(echo "$name" | sed 's/\${var\.environment}/{env}/g')
    # Remove path prefixes for CloudWatch log groups
    name="${name#/aws/lambda/}"
    name="${name#/aws/apigateway/}"
    name="${name#/aws/fis/}"
    echo "$name"
}

# Extract function_name, table names, topic names, queue names from TF files
while IFS= read -r line; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue

    # Extract resource names from common patterns
    if [[ "$line" =~ function_name[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
        name="${BASH_REMATCH[1]}"
        # Skip local/module references
        [[ "$name" =~ ^local\. ]] && continue
        [[ "$name" =~ ^module\. ]] && continue
        [[ "$name" =~ ^var\. ]] && continue
        # Normalize and store
        normalized=$(normalize_name "$name")
        RESOURCE_NAMES["lambda:$normalized"]="$name"
    elif [[ "$line" =~ name[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
        name="${BASH_REMATCH[1]}"
        # Skip local/module references
        [[ "$name" =~ ^local\. ]] && continue
        [[ "$name" =~ ^module\. ]] && continue
        [[ "$name" =~ ^var\. ]] && continue
        [[ "$name" =~ ^[A-Z] ]] && continue  # Skip display names like "CIDeployCore"
        # Normalize and check if it looks like a resource name
        normalized=$(normalize_name "$name")
        if [[ "$normalized" =~ -sentiment- ]] || [[ "$normalized" =~ ^sentiment-analyzer- ]]; then
            RESOURCE_NAMES["resource:$normalized"]="$name"
        fi
    fi
done < <(grep -rh "function_name\|^\s*name\s*=" "$TF_DIR"/*.tf "$TF_DIR"/modules/*/*.tf 2>/dev/null || true)

# Also check for table_name in DynamoDB
while IFS= read -r line; do
    if [[ "$line" =~ table_name[[:space:]]*=[[:space:]]*\"([^\"]+)\" ]]; then
        name="${BASH_REMATCH[1]}"
        [[ "$name" =~ ^local\. ]] && continue
        [[ "$name" =~ ^module\. ]] && continue
        [[ "$name" =~ ^var\. ]] && continue
        normalized=$(normalize_name "$name")
        RESOURCE_NAMES["dynamodb:$normalized"]="$name"
    fi
done < <(grep -rh "table_name" "$TF_DIR"/*.tf "$TF_DIR"/modules/*/*.tf 2>/dev/null || true)

echo "Found ${#RESOURCE_NAMES[@]} resource names"
echo ""

# =============================================================================
# Step 2: Validate resource names follow {env}-sentiment-{service} pattern
# =============================================================================
echo "Step 2: Validating resource naming pattern..."
echo "-------------------------------------------"

for key in "${!RESOURCE_NAMES[@]}"; do
    name="${key#*:}"
    type="${key%%:*}"

    if [[ "$name" =~ $LEGACY_PATTERN ]]; then
        echo -e "${RED}LEGACY: $type - $name${NC}"
        echo "        Should use: {env}-sentiment-{service} pattern"
        LEGACY_RESOURCES+=("$name")
        ERRORS=$((ERRORS + 1))
    elif [[ ! "$name" =~ $VALID_PATTERN ]]; then
        # Only flag if it contains sentiment (to avoid false positives)
        if [[ "$name" =~ sentiment ]]; then
            echo -e "${YELLOW}INVALID: $type - $name${NC}"
            echo "         Expected pattern: {env}-sentiment-{service}"
            INVALID_RESOURCES+=("$name")
            WARNINGS=$((WARNINGS + 1))
        fi
    else
        echo -e "${GREEN}OK: $type - $name${NC}"
    fi
done

echo ""

# =============================================================================
# Step 3: Extract IAM ARN patterns from ci-user-policy.tf
# =============================================================================
echo "Step 3: Extracting IAM ARN patterns..."
echo "-------------------------------------------"

declare -a IAM_PATTERNS

while IFS= read -r line; do
    # Extract ARN patterns from resources blocks
    if [[ "$line" =~ \"arn:aws:[^\"]+\" ]]; then
        pattern="${BASH_REMATCH[0]}"
        pattern="${pattern//\"/}"
        IAM_PATTERNS+=("$pattern")
    fi
done < "$IAM_POLICY_FILE"

echo "Found ${#IAM_PATTERNS[@]} IAM ARN patterns"
echo ""

# =============================================================================
# Step 4: Check for legacy patterns in IAM policy
# =============================================================================
echo "Step 4: Checking for legacy patterns in IAM policy..."
echo "-------------------------------------------"

LEGACY_ARN_COUNT=0
LEGACY_USER_COUNT=0
while IFS= read -r line; do
    if [[ "$line" =~ sentiment-analyzer- ]] && [[ ! "$line" =~ ^[[:space:]]*# ]]; then
        # Distinguish between ARN patterns (fixable) and user references (AWS resource)
        if [[ "$line" =~ user[[:space:]]*= ]] || [[ "$line" =~ \"sentiment-analyzer-.*-deployer\" ]]; then
            echo -e "${YELLOW}LEGACY USER REF: $line${NC}"
            LEGACY_USER_COUNT=$((LEGACY_USER_COUNT + 1))
        else
            echo -e "${RED}LEGACY ARN PATTERN: $line${NC}"
            LEGACY_ARN_COUNT=$((LEGACY_ARN_COUNT + 1))
        fi
    fi
done < "$IAM_POLICY_FILE"

if [[ $LEGACY_ARN_COUNT -eq 0 ]] && [[ $LEGACY_USER_COUNT -eq 0 ]]; then
    echo -e "${GREEN}No legacy patterns found in IAM policy${NC}"
else
    echo ""
    if [[ $LEGACY_ARN_COUNT -gt 0 ]]; then
        echo -e "${RED}Found $LEGACY_ARN_COUNT legacy ARN patterns - MUST be removed${NC}"
        ERRORS=$((ERRORS + LEGACY_ARN_COUNT))
    fi
    if [[ $LEGACY_USER_COUNT -gt 0 ]]; then
        echo -e "${YELLOW}Found $LEGACY_USER_COUNT legacy IAM user references (AWS resources, can't rename in-place)${NC}"
        # Don't add to errors/warnings - these are AWS resources that exist
    fi
fi

echo ""

# =============================================================================
# Step 5: Verify IAM patterns cover resource naming convention
# =============================================================================
echo "Step 5: Verifying IAM pattern coverage..."
echo "-------------------------------------------"

# Check that *-sentiment-* pattern exists for key services
REQUIRED_PATTERNS=(
    "lambda:*-sentiment-*"
    "dynamodb:*-sentiment-*"
    "sns:*-sentiment-*"
    "sqs:*-sentiment-*"
    "logs:*-sentiment-*"
    "secretsmanager:*/sentiment-analyzer/*"
)

for req in "${REQUIRED_PATTERNS[@]}"; do
    service="${req%%:*}"
    pattern="${req#*:}"

    if grep -q "$pattern" "$IAM_POLICY_FILE" 2>/dev/null; then
        echo -e "${GREEN}OK: $service has pattern '$pattern'${NC}"
    else
        echo -e "${RED}MISSING: $service needs pattern '$pattern'${NC}"
        ERRORS=$((ERRORS + 1))
    fi
done

echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "Resources checked: ${#RESOURCE_NAMES[@]}"
echo "Legacy resources:  ${#LEGACY_RESOURCES[@]}"
echo "Invalid resources: ${#INVALID_RESOURCES[@]}"
echo ""
echo -e "Errors:   ${RED}$ERRORS${NC}"
echo -e "Warnings: ${YELLOW}$WARNINGS${NC}"
echo ""

if [[ $ERRORS -gt 0 ]]; then
    echo -e "${RED}FAILED: $ERRORS error(s) found${NC}"
    echo ""
    echo "To fix:"
    echo "  1. Rename legacy resources to use {env}-sentiment-{service} pattern"
    echo "  2. Update IAM patterns to include *-sentiment-* for all services"
    echo "  3. Remove legacy sentiment-analyzer-* patterns after migration"
    exit 1
elif [[ $WARNINGS -gt 0 ]]; then
    echo -e "${YELLOW}PASSED with warnings${NC}"
    exit 0
else
    echo -e "${GREEN}PASSED: All checks passed${NC}"
    exit 0
fi
