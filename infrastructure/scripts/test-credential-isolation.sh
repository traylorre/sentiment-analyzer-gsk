#!/bin/bash
# Test Credential Isolation
# ==========================
#
# This script validates that preprod and prod credentials are properly isolated.
# Tests that preprod credentials CANNOT access prod resources and vice versa.

set -euo pipefail

echo "=========================================="
echo "Credential Isolation Test"
echo "=========================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test results
PASS_COUNT=0
FAIL_COUNT=0

# ============================================================================
# Helper Functions
# ============================================================================

test_pass() {
  echo -e "${GREEN}✅ PASS${NC}: $1"
  ((PASS_COUNT++))
}

test_fail() {
  echo -e "${RED}❌ FAIL${NC}: $1"
  ((FAIL_COUNT++))
}

test_info() {
  echo -e "${YELLOW}ℹ️  INFO${NC}: $1"
}

# ============================================================================
# Load Credentials
# ============================================================================

echo "Loading credentials..."
echo ""

if [ ! -f "preprod-deployer-credentials.json" ]; then
  echo -e "${RED}ERROR${NC}: preprod-deployer-credentials.json not found"
  echo "Run: ./infrastructure/scripts/setup-credentials.sh first"
  exit 1
fi

if [ ! -f "prod-deployer-credentials.json" ]; then
  echo -e "${RED}ERROR${NC}: prod-deployer-credentials.json not found"
  echo "Run: ./infrastructure/scripts/setup-credentials.sh first"
  exit 1
fi

PREPROD_ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' preprod-deployer-credentials.json)
PREPROD_SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' preprod-deployer-credentials.json)

PROD_ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' prod-deployer-credentials.json)
PROD_SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' prod-deployer-credentials.json)

test_info "Loaded preprod credentials: ${PREPROD_ACCESS_KEY:0:10}..."
test_info "Loaded prod credentials: ${PROD_ACCESS_KEY:0:10}..."
echo ""

# ============================================================================
# Test 1: Preprod Credentials - Access Preprod Resources (Should SUCCEED)
# ============================================================================

echo "Test 1: Preprod credentials accessing preprod resources..."

export AWS_ACCESS_KEY_ID="${PREPROD_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${PREPROD_SECRET_KEY}"
export AWS_DEFAULT_REGION="us-east-1"

# Test: List preprod secrets
if aws secretsmanager list-secrets --filters Key=name,Values=preprod/ --query 'SecretList[].Name' --output text &>/dev/null; then
  test_pass "Preprod credentials can list preprod secrets"
else
  test_fail "Preprod credentials CANNOT list preprod secrets (should work!)"
fi

# Test: Read preprod NewsAPI secret
if aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/newsapi --query SecretString --output text &>/dev/null; then
  test_pass "Preprod credentials can read preprod NewsAPI secret"
else
  test_fail "Preprod credentials CANNOT read preprod NewsAPI secret (should work!)"
fi

echo ""

# ============================================================================
# Test 2: Preprod Credentials - Access Prod Resources (Should FAIL)
# ============================================================================

echo "Test 2: Preprod credentials accessing prod resources (should be DENIED)..."

export AWS_ACCESS_KEY_ID="${PREPROD_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${PREPROD_SECRET_KEY}"
export AWS_DEFAULT_REGION="us-east-1"

# Test: Try to read prod secrets (should fail)
if aws secretsmanager get-secret-value --secret-id prod/sentiment-analyzer/newsapi --query SecretString --output text &>/dev/null; then
  test_fail "Preprod credentials CAN read prod secrets (SECURITY ISSUE!)"
else
  test_pass "Preprod credentials CANNOT read prod secrets (correctly denied)"
fi

# Test: Try to list prod Lambda functions (should fail)
if aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `prod-`)].FunctionName' --output text 2>/dev/null | grep -q "prod-"; then
  test_fail "Preprod credentials CAN list prod Lambda functions (SECURITY ISSUE!)"
else
  test_pass "Preprod credentials CANNOT list prod Lambda functions (correctly denied)"
fi

# Test: Try to describe prod DynamoDB table (should fail)
if aws dynamodb describe-table --table-name prod-sentiment-items &>/dev/null; then
  test_fail "Preprod credentials CAN access prod DynamoDB table (SECURITY ISSUE!)"
else
  test_pass "Preprod credentials CANNOT access prod DynamoDB table (correctly denied)"
fi

echo ""

# ============================================================================
# Test 3: Prod Credentials - Access Prod Resources (Should SUCCEED)
# ============================================================================

echo "Test 3: Prod credentials accessing prod resources..."

export AWS_ACCESS_KEY_ID="${PROD_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${PROD_SECRET_KEY}"
export AWS_DEFAULT_REGION="us-east-1"

# Test: List prod secrets
if aws secretsmanager list-secrets --filters Key=name,Values=prod/ --query 'SecretList[].Name' --output text &>/dev/null; then
  test_pass "Prod credentials can list prod secrets"
else
  test_fail "Prod credentials CANNOT list prod secrets (should work!)"
fi

# Test: Read prod NewsAPI secret
if aws secretsmanager get-secret-value --secret-id prod/sentiment-analyzer/newsapi --query SecretString --output text &>/dev/null; then
  test_pass "Prod credentials can read prod NewsAPI secret"
else
  test_fail "Prod credentials CANNOT read prod NewsAPI secret (should work!)"
fi

echo ""

# ============================================================================
# Test 4: Prod Credentials - Access Preprod Resources (Should FAIL)
# ============================================================================

echo "Test 4: Prod credentials accessing preprod resources (should be DENIED)..."

export AWS_ACCESS_KEY_ID="${PROD_ACCESS_KEY}"
export AWS_SECRET_ACCESS_KEY="${PROD_SECRET_KEY}"
export AWS_DEFAULT_REGION="us-east-1"

# Test: Try to read preprod secrets (should fail)
if aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/newsapi --query SecretString --output text &>/dev/null; then
  test_fail "Prod credentials CAN read preprod secrets (SECURITY ISSUE!)"
else
  test_pass "Prod credentials CANNOT read preprod secrets (correctly denied)"
fi

# Test: Try to list preprod Lambda functions (should fail)
if aws lambda list-functions --query 'Functions[?starts_with(FunctionName, `preprod-`)].FunctionName' --output text 2>/dev/null | grep -q "preprod-"; then
  test_fail "Prod credentials CAN list preprod Lambda functions (SECURITY ISSUE!)"
else
  test_pass "Prod credentials CANNOT list preprod Lambda functions (correctly denied)"
fi

# Test: Try to describe preprod DynamoDB table (should fail)
if aws dynamodb describe-table --table-name preprod-sentiment-items &>/dev/null; then
  test_fail "Prod credentials CAN access preprod DynamoDB table (SECURITY ISSUE!)"
else
  test_pass "Prod credentials CANNOT access preprod DynamoDB table (correctly denied)"
fi

echo ""

# ============================================================================
# Results Summary
# ============================================================================

TOTAL_TESTS=$((PASS_COUNT + FAIL_COUNT))

echo "=========================================="
echo "Test Results"
echo "=========================================="
echo ""
echo "Total Tests: ${TOTAL_TESTS}"
echo -e "Passed: ${GREEN}${PASS_COUNT}${NC}"
echo -e "Failed: ${RED}${FAIL_COUNT}${NC}"
echo ""

if [ "${FAIL_COUNT}" -eq 0 ]; then
  echo -e "${GREEN}✅ ALL TESTS PASSED${NC}"
  echo ""
  echo "Credential isolation is working correctly!"
  echo "Preprod credentials cannot access prod resources."
  echo "Prod credentials cannot access preprod resources."
  echo ""
  exit 0
else
  echo -e "${RED}❌ SOME TESTS FAILED${NC}"
  echo ""
  echo "CRITICAL: Fix IAM policies before deploying!"
  echo "Review: infrastructure/docs/CREDENTIAL_SEPARATION_SETUP.md"
  echo ""
  exit 1
fi
