#!/bin/bash
# Setup GitHub Environment Secrets
# This script creates all required secrets for dev, preprod, and production environments

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  GitHub Environment Secrets Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}Error: Not authenticated with GitHub CLI${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo -e "${GREEN}Repository: ${REPO}${NC}"
echo ""

# Function to create environment if it doesn't exist
create_environment() {
    local env=$1
    echo -e "${BLUE}Checking environment: ${env}${NC}"
    gh api -X PUT "repos/${REPO}/environments/${env}" 2>/dev/null || true
    echo -e "${GREEN}✓ Environment '${env}' ready${NC}"
}

# Function to set a secret
set_secret() {
    local env=$1
    local name=$2
    local value=$3

    echo -e "${YELLOW}Setting ${name} for ${env}...${NC}"
    echo -n "$value" | gh secret set "$name" --env "$env"
    echo -e "${GREEN}✓ ${name} set for ${env}${NC}"
}

# Function to prompt for secret value with detailed explanation
prompt_secret() {
    local env=$1
    local secret_name=$2
    local description=$3
    local example=$4
    local secret_value

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}Environment: ${env}${NC}"
    echo -e "${BLUE}Secret: ${secret_name}${NC}"
    echo -e "${YELLOW}What it is: ${description}${NC}"
    if [ -n "$example" ]; then
        echo -e "${CYAN}Example: ${example}${NC}"
    fi
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}Enter value (hidden):${NC}"
    read -s secret_value
    echo ""
    echo "$secret_value"
}

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 1: Create Environments${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

create_environment "dev"
create_environment "preprod"
create_environment "production"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 2: Gather Secret Values${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}I'll now ask for each secret value with a clear description.${NC}"
echo -e "${YELLOW}Values will be hidden as you type.${NC}"

# ====================
# DEV SECRETS
# ====================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         DEV Environment (4 secrets)         ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

DEV_AWS_ACCESS_KEY_ID=$(prompt_secret "DEV" "AWS_ACCESS_KEY_ID" \
    "AWS IAM user access key for deploying to DEV" \
    "AKIAIOSFODNN7EXAMPLE")

DEV_AWS_SECRET_ACCESS_KEY=$(prompt_secret "DEV" "AWS_SECRET_ACCESS_KEY" \
    "AWS IAM user secret key for deploying to DEV" \
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

DEV_DASHBOARD_API_KEY=$(prompt_secret "DEV" "DASHBOARD_API_KEY" \
    "API key for authenticating to DEV dashboard (generate with: openssl rand -hex 32)" \
    "a1b2c3d4e5f6...")

DEV_NEWSAPI_SECRET_ARN=$(prompt_secret "DEV" "NEWSAPI_SECRET_ARN" \
    "ARN of NewsAPI secret in AWS Secrets Manager for DEV (get with: aws secretsmanager describe-secret --secret-id dev/sentiment-analyzer/newsapi --query ARN)" \
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:dev/sentiment-analyzer/newsapi-AbCdEf")

# ====================
# PREPROD SECRETS
# ====================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║       PREPROD Environment (4 secrets)       ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

PREPROD_AWS_ACCESS_KEY_ID=$(prompt_secret "PREPROD" "AWS_ACCESS_KEY_ID" \
    "AWS IAM user access key for deploying to PREPROD" \
    "AKIAIOSFODNN7EXAMPLE")

PREPROD_AWS_SECRET_ACCESS_KEY=$(prompt_secret "PREPROD" "AWS_SECRET_ACCESS_KEY" \
    "AWS IAM user secret key for deploying to PREPROD" \
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

PREPROD_DASHBOARD_API_KEY=$(prompt_secret "PREPROD" "DASHBOARD_API_KEY" \
    "API key for authenticating to PREPROD dashboard (get existing: aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/dashboard-api-key --query SecretString)" \
    "a1b2c3d4e5f6...")

PREPROD_NEWSAPI_SECRET_ARN=$(prompt_secret "PREPROD" "NEWSAPI_SECRET_ARN" \
    "ARN of NewsAPI secret in AWS Secrets Manager for PREPROD (get with: aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/newsapi --query ARN)" \
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:preprod/sentiment-analyzer/newsapi-AbCdEf")

# ====================
# PROD SECRETS
# ====================
echo ""
echo -e "${GREEN}╔════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     PRODUCTION Environment (4 secrets)      ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════╝${NC}"

PROD_AWS_ACCESS_KEY_ID=$(prompt_secret "PRODUCTION" "AWS_ACCESS_KEY_ID" \
    "AWS IAM user access key for deploying to PRODUCTION" \
    "AKIAIOSFODNN7EXAMPLE")

PROD_AWS_SECRET_ACCESS_KEY=$(prompt_secret "PRODUCTION" "AWS_SECRET_ACCESS_KEY" \
    "AWS IAM user secret key for deploying to PRODUCTION" \
    "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

PROD_DASHBOARD_API_KEY=$(prompt_secret "PRODUCTION" "DASHBOARD_API_KEY" \
    "API key for authenticating to PRODUCTION dashboard (generate with: openssl rand -hex 32)" \
    "a1b2c3d4e5f6...")

PROD_NEWSAPI_SECRET_ARN=$(prompt_secret "PRODUCTION" "NEWSAPI_SECRET_ARN" \
    "ARN of NewsAPI secret in AWS Secrets Manager for PRODUCTION (get with: aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/newsapi --query ARN)" \
    "arn:aws:secretsmanager:us-east-1:123456789012:secret:prod/sentiment-analyzer/newsapi-AbCdEf")

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Step 3: Create Secrets in GitHub${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ====================
# CREATE DEV SECRETS
# ====================
echo -e "${BLUE}--- Creating DEV Secrets ---${NC}"
set_secret "dev" "AWS_ACCESS_KEY_ID" "$DEV_AWS_ACCESS_KEY_ID"
set_secret "dev" "AWS_SECRET_ACCESS_KEY" "$DEV_AWS_SECRET_ACCESS_KEY"
set_secret "dev" "DASHBOARD_API_KEY" "$DEV_DASHBOARD_API_KEY"
set_secret "dev" "NEWSAPI_SECRET_ARN" "$DEV_NEWSAPI_SECRET_ARN"

echo ""

# ====================
# CREATE PREPROD SECRETS
# ====================
echo -e "${BLUE}--- Creating PREPROD Secrets ---${NC}"
set_secret "preprod" "AWS_ACCESS_KEY_ID" "$PREPROD_AWS_ACCESS_KEY_ID"
set_secret "preprod" "AWS_SECRET_ACCESS_KEY" "$PREPROD_AWS_SECRET_ACCESS_KEY"
set_secret "preprod" "DASHBOARD_API_KEY" "$PREPROD_DASHBOARD_API_KEY"
set_secret "preprod" "NEWSAPI_SECRET_ARN" "$PREPROD_NEWSAPI_SECRET_ARN"

echo ""

# ====================
# CREATE PROD SECRETS
# ====================
echo -e "${BLUE}--- Creating PRODUCTION Secrets ---${NC}"
set_secret "production" "AWS_ACCESS_KEY_ID" "$PROD_AWS_ACCESS_KEY_ID"
set_secret "production" "AWS_SECRET_ACCESS_KEY" "$PROD_AWS_SECRET_ACCESS_KEY"
set_secret "production" "DASHBOARD_API_KEY" "$PROD_DASHBOARD_API_KEY"
set_secret "production" "NEWSAPI_SECRET_ARN" "$PROD_NEWSAPI_SECRET_ARN"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  ✅ All Secrets Created Successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${YELLOW}Summary:${NC}"
echo -e "  ${GREEN}✓${NC} DEV: 4 secrets created"
echo -e "  ${GREEN}✓${NC} PREPROD: 4 secrets created"
echo -e "  ${GREEN}✓${NC} PRODUCTION: 4 secrets created"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Verify secrets: https://github.com/${REPO}/settings/environments"
echo "  2. Delete old prefixed secrets (PREPROD_*, PROD_*) in GitHub UI"
echo "  3. Test deployment by pushing to main"
echo ""
