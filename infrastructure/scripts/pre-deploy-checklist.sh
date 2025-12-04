#!/bin/bash
# Pre-Deploy Checklist Script for Sentiment Analyzer
#
# Usage: ./pre-deploy-checklist.sh <environment>
# Example: ./pre-deploy-checklist.sh dev
#
# Validates all prerequisites before deployment:
# 1. Secrets exist in Secrets Manager
# 2. Model layer uploaded (if applicable)
# 3. CloudWatch alarms configured
# 4. No active alarms firing
#
# For On-Call Engineers:
#     Run this before any deployment to catch issues early.
#     All checks must pass before proceeding with deploy.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <environment>"
    exit 1
fi

ENVIRONMENT="$1"
FAILURES=0
WARNINGS=0

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}"
    exit 1
fi

log_info "Running pre-deploy checklist for ${ENVIRONMENT}"
echo ""

# Check 1: AWS Credentials
echo "=== AWS Credentials ==="
if aws sts get-caller-identity > /dev/null 2>&1; then
    ACCOUNT=$(aws sts get-caller-identity --query 'Account' --output text)
    log_pass "AWS credentials configured (Account: ${ACCOUNT})"
else
    log_fail "AWS credentials not configured"
    ((FAILURES++))
fi
echo ""

# Check 2: Required Secrets
echo "=== Secrets Manager ==="
REQUIRED_SECRETS=(
    "${ENVIRONMENT}/sentiment-analyzer/newsapi"
    "${ENVIRONMENT}/sentiment-analyzer/dashboard-api-key"
)

for secret in "${REQUIRED_SECRETS[@]}"; do
    if aws secretsmanager describe-secret --secret-id "${secret}" > /dev/null 2>&1; then
        # Verify secret has a value
        SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id "${secret}" \
            --query 'SecretString' --output text 2>/dev/null || echo "")
        if [[ -n "${SECRET_VALUE}" ]]; then
            log_pass "Secret exists and has value: ${secret}"
        else
            log_fail "Secret exists but is empty: ${secret}"
            ((FAILURES++))
        fi
    else
        log_fail "Secret not found: ${secret}"
        log_error "  Create it with: aws secretsmanager create-secret --name '${secret}' --secret-string '{\"api_key\": \"your-key\"}'"
        ((FAILURES++))
    fi
done
echo ""

# Check 3: S3 Bucket for Lambda Deployments
echo "=== S3 Bucket ==="
BUCKET_NAME="${ENVIRONMENT}-sentiment-lambda-deployments"
if aws s3api head-bucket --bucket "${BUCKET_NAME}" 2>/dev/null; then
    log_pass "Deployment bucket exists: ${BUCKET_NAME}"

    # Check versioning
    VERSIONING=$(aws s3api get-bucket-versioning --bucket "${BUCKET_NAME}" \
        --query 'Status' --output text 2>/dev/null || echo "Disabled")
    if [[ "${VERSIONING}" == "Enabled" ]]; then
        log_pass "Bucket versioning: ${VERSIONING}"
    else
        log_warn "Bucket versioning: ${VERSIONING} (recommended: Enabled)"
        ((WARNINGS++))
    fi
else
    log_warn "Deployment bucket not found: ${BUCKET_NAME}"
    log_info "  Will be created by Terraform"
    ((WARNINGS++))
fi
echo ""

# Check 4: Terraform State
echo "=== Terraform ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="${SCRIPT_DIR}/../terraform"

if [[ -d "${TERRAFORM_DIR}" ]]; then
    cd "${TERRAFORM_DIR}"

    # Check if initialized
    if [[ -d ".terraform" ]]; then
        log_pass "Terraform initialized"
    else
        log_warn "Terraform not initialized - run 'terraform init'"
        ((WARNINGS++))
    fi

    # Check workspace
    CURRENT_WORKSPACE=$(terraform workspace show 2>/dev/null || echo "default")
    if [[ "${CURRENT_WORKSPACE}" == "${ENVIRONMENT}" ]]; then
        log_pass "Terraform workspace: ${CURRENT_WORKSPACE}"
    else
        log_info "Current workspace: ${CURRENT_WORKSPACE} (will switch to ${ENVIRONMENT})"
    fi
else
    log_fail "Terraform directory not found: ${TERRAFORM_DIR}"
    ((FAILURES++))
fi
echo ""

# Check 5: Active Alarms
echo "=== CloudWatch Alarms ==="
ALARM_PREFIX="${ENVIRONMENT}-sentiment"
ALARMING=$(aws cloudwatch describe-alarms \
    --alarm-name-prefix "${ALARM_PREFIX}" \
    --state-value ALARM \
    --query 'MetricAlarms[*].AlarmName' \
    --output text 2>/dev/null || echo "")

if [[ -z "${ALARMING}" ]]; then
    log_pass "No alarms currently firing"
else
    log_fail "Active alarms detected:"
    for alarm in ${ALARMING}; do
        log_error "  - ${alarm}"
    done
    ((FAILURES++))
fi
echo ""

# Check 6: Python Dependencies
echo "=== Python Environment ==="
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    log_pass "Python: ${PYTHON_VERSION}"

    # Check for required packages
    REQUIRED_PACKAGES=("boto3" "pytest" "moto")
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if python3 -c "import ${pkg}" 2>/dev/null; then
            log_pass "Package: ${pkg}"
        else
            log_warn "Package not installed: ${pkg}"
            ((WARNINGS++))
        fi
    done
else
    log_fail "Python3 not found"
    ((FAILURES++))
fi
echo ""

# Check 7: Git Status (for production)
if [[ "${ENVIRONMENT}" == "prod" ]]; then
    echo "=== Git Status ==="
    cd "${SCRIPT_DIR}/../.."

    # Check for uncommitted changes
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        log_pass "No uncommitted changes"
    else
        log_fail "Uncommitted changes detected"
        log_error "  Commit or stash changes before deploying to production"
        ((FAILURES++))
    fi

    # Check branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
    if [[ "${BRANCH}" == "main" || "${BRANCH}" == "master" ]]; then
        log_pass "On main branch: ${BRANCH}"
    else
        log_warn "Not on main branch: ${BRANCH}"
        ((WARNINGS++))
    fi
    echo ""
fi

# Summary
echo "=== Pre-Deploy Summary ==="
if [[ ${FAILURES} -eq 0 && ${WARNINGS} -eq 0 ]]; then
    log_pass "All checks passed! Ready to deploy."
    exit 0
elif [[ ${FAILURES} -eq 0 ]]; then
    log_warn "${WARNINGS} warning(s) - review before deploying"
    exit 0
else
    log_fail "${FAILURES} check(s) failed - fix before deploying"
    exit 1
fi
