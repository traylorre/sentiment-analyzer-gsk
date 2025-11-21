#!/bin/bash
# Setup Credential Separation for Preprod and Prod
# =================================================
#
# This script creates:
# 1. IAM users for preprod and prod deployment
# 2. IAM policies with environment-scoped resource access
# 3. AWS Secrets Manager secrets for each environment
#
# IMPORTANT: Save the output credentials securely!

set -euo pipefail

echo "=========================================="
echo "Sentiment Analyzer - Credential Setup"
echo "=========================================="
echo ""

# Check AWS CLI is configured
if ! aws sts get-caller-identity &>/dev/null; then
  echo "❌ ERROR: AWS CLI not configured or credentials invalid"
  echo "   Run: aws configure"
  exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "✅ AWS Account ID: ${AWS_ACCOUNT_ID}"
echo ""

# ============================================================================
# Step 1: Create IAM Users
# ============================================================================

echo "Step 1: Creating IAM users..."
echo ""

# Preprod deployer
if aws iam get-user --user-name sentiment-analyzer-preprod-deployer &>/dev/null; then
  echo "⚠️  IAM user 'sentiment-analyzer-preprod-deployer' already exists, skipping creation"
else
  aws iam create-user \
    --user-name sentiment-analyzer-preprod-deployer \
    --tags Key=Environment,Value=preprod \
           Key=Purpose,Value=terraform-deployment \
           Key=ManagedBy,Value=Script
  echo "✅ Created IAM user: sentiment-analyzer-preprod-deployer"
fi

# Prod deployer
if aws iam get-user --user-name sentiment-analyzer-prod-deployer &>/dev/null; then
  echo "⚠️  IAM user 'sentiment-analyzer-prod-deployer' already exists, skipping creation"
else
  aws iam create-user \
    --user-name sentiment-analyzer-prod-deployer \
    --tags Key=Environment,Value=prod \
           Key=Purpose,Value=terraform-deployment \
           Key=ManagedBy,Value=Script
  echo "✅ Created IAM user: sentiment-analyzer-prod-deployer"
fi

echo ""

# ============================================================================
# Step 2: Apply IAM Policies
# ============================================================================

echo "Step 2: Applying IAM policies..."
echo ""

# Preprod policy
aws iam put-user-policy \
  --user-name sentiment-analyzer-preprod-deployer \
  --policy-name PreprodDeploymentPolicy \
  --policy-document file://infrastructure/iam-policies/preprod-deployer-policy.json

echo "✅ Applied policy to sentiment-analyzer-preprod-deployer"

# Prod policy
aws iam put-user-policy \
  --user-name sentiment-analyzer-prod-deployer \
  --policy-name ProdDeploymentPolicy \
  --policy-document file://infrastructure/iam-policies/prod-deployer-policy.json

echo "✅ Applied policy to sentiment-analyzer-prod-deployer"
echo ""

# ============================================================================
# Step 3: Create Access Keys
# ============================================================================

echo "Step 3: Creating access keys..."
echo ""

# Preprod access key
if [ -f "preprod-deployer-credentials.json" ]; then
  echo "⚠️  preprod-deployer-credentials.json already exists, skipping"
else
  aws iam create-access-key \
    --user-name sentiment-analyzer-preprod-deployer \
    > preprod-deployer-credentials.json
  echo "✅ Created access key for preprod deployer"
  echo "   Saved to: preprod-deployer-credentials.json"
fi

# Prod access key
if [ -f "prod-deployer-credentials.json" ]; then
  echo "⚠️  prod-deployer-credentials.json already exists, skipping"
else
  aws iam create-access-key \
    --user-name sentiment-analyzer-prod-deployer \
    > prod-deployer-credentials.json
  echo "✅ Created access key for prod deployer"
  echo "   Saved to: prod-deployer-credentials.json"
fi

echo ""

# ============================================================================
# Step 4: Create Secrets Manager Secrets
# ============================================================================

echo "Step 4: Creating Secrets Manager secrets..."
echo ""

# Preprod NewsAPI secret
if aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/newsapi &>/dev/null; then
  echo "⚠️  Secret 'preprod/sentiment-analyzer/newsapi' already exists, skipping"
else
  echo "Enter your PREPROD NewsAPI key (free tier):"
  read -r PREPROD_NEWSAPI_KEY

  aws secretsmanager create-secret \
    --name preprod/sentiment-analyzer/newsapi \
    --description "NewsAPI key for preprod environment (free tier)" \
    --secret-string "{\"api_key\":\"${PREPROD_NEWSAPI_KEY}\"}" \
    --region us-east-1 \
    --tags Key=Environment,Value=preprod \
           Key=ManagedBy,Value=Script \
           Key=Purpose,Value=newsapi-integration \
    --output json > /dev/null

  echo "✅ Created secret: preprod/sentiment-analyzer/newsapi"
fi

# Prod NewsAPI secret
if aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/newsapi &>/dev/null; then
  echo "⚠️  Secret 'prod/sentiment-analyzer/newsapi' already exists, skipping"
else
  echo "Enter your PROD NewsAPI key (paid tier):"
  read -r PROD_NEWSAPI_KEY

  aws secretsmanager create-secret \
    --name prod/sentiment-analyzer/newsapi \
    --description "NewsAPI key for production environment (paid tier)" \
    --secret-string "{\"api_key\":\"${PROD_NEWSAPI_KEY}\"}" \
    --region us-east-1 \
    --tags Key=Environment,Value=prod \
           Key=ManagedBy,Value=Script \
           Key=Purpose,Value=newsapi-integration \
    --output json > /dev/null

  echo "✅ Created secret: prod/sentiment-analyzer/newsapi"
fi

# Preprod Dashboard API key
if aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/dashboard-api-key &>/dev/null; then
  echo "⚠️  Secret 'preprod/sentiment-analyzer/dashboard-api-key' already exists, skipping"
else
  PREPROD_API_KEY=$(openssl rand -base64 32)

  aws secretsmanager create-secret \
    --name preprod/sentiment-analyzer/dashboard-api-key \
    --description "Dashboard API key for preprod environment" \
    --secret-string "{\"api_key\":\"${PREPROD_API_KEY}\"}" \
    --region us-east-1 \
    --tags Key=Environment,Value=preprod \
           Key=ManagedBy,Value=Script \
           Key=Purpose,Value=dashboard-auth \
    --output json > /dev/null

  echo "✅ Created secret: preprod/sentiment-analyzer/dashboard-api-key"
  echo "   API Key: ${PREPROD_API_KEY}"
  echo "   (Save this for testing preprod dashboard)"
fi

# Prod Dashboard API key
if aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/dashboard-api-key &>/dev/null; then
  echo "⚠️  Secret 'prod/sentiment-analyzer/dashboard-api-key' already exists, skipping"
else
  PROD_API_KEY=$(openssl rand -base64 32)

  aws secretsmanager create-secret \
    --name prod/sentiment-analyzer/dashboard-api-key \
    --description "Dashboard API key for production environment" \
    --secret-string "{\"api_key\":\"${PROD_API_KEY}\"}" \
    --region us-east-1 \
    --tags Key=Environment,Value=prod \
           Key=ManagedBy,Value=Script \
           Key=Purpose,Value=dashboard-auth \
    --output json > /dev/null

  echo "✅ Created secret: prod/sentiment-analyzer/dashboard-api-key"
  echo "   API Key: ${PROD_API_KEY}"
  echo "   (Save this for testing prod dashboard)"
fi

echo ""

# ============================================================================
# Step 5: Output GitHub Secrets
# ============================================================================

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Add the following secrets to GitHub Environments:"
echo ""

echo "   Preprod Environment (Settings → Environments → preprod → Add Secret):"
echo "   -----------------------------------------------------------------------"

PREPROD_ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' preprod-deployer-credentials.json 2>/dev/null || echo "NOT_CREATED")
PREPROD_SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' preprod-deployer-credentials.json 2>/dev/null || echo "NOT_CREATED")
PREPROD_NEWSAPI_ARN=$(aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/newsapi --query ARN --output text 2>/dev/null || echo "NOT_CREATED")
PREPROD_DASHBOARD_ARN=$(aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/dashboard-api-key --query ARN --output text 2>/dev/null || echo "NOT_CREATED")

echo "   PREPROD_AWS_ACCESS_KEY_ID=${PREPROD_ACCESS_KEY}"
echo "   PREPROD_AWS_SECRET_ACCESS_KEY=${PREPROD_SECRET_KEY}"
echo "   PREPROD_NEWSAPI_SECRET_ARN=${PREPROD_NEWSAPI_ARN}"
echo "   PREPROD_DASHBOARD_API_KEY_SECRET_ARN=${PREPROD_DASHBOARD_ARN}"
echo ""

echo "   Production Environment (Settings → Environments → production → Add Secret):"
echo "   ----------------------------------------------------------------------------"

PROD_ACCESS_KEY=$(jq -r '.AccessKey.AccessKeyId' prod-deployer-credentials.json 2>/dev/null || echo "NOT_CREATED")
PROD_SECRET_KEY=$(jq -r '.AccessKey.SecretAccessKey' prod-deployer-credentials.json 2>/dev/null || echo "NOT_CREATED")
PROD_NEWSAPI_ARN=$(aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/newsapi --query ARN --output text 2>/dev/null || echo "NOT_CREATED")
PROD_DASHBOARD_ARN=$(aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/dashboard-api-key --query ARN --output text 2>/dev/null || echo "NOT_CREATED")

echo "   PROD_AWS_ACCESS_KEY_ID=${PROD_ACCESS_KEY}"
echo "   PROD_AWS_SECRET_ACCESS_KEY=${PROD_SECRET_KEY}"
echo "   PROD_NEWSAPI_SECRET_ARN=${PROD_NEWSAPI_ARN}"
echo "   PROD_DASHBOARD_API_KEY_SECRET_ARN=${PROD_DASHBOARD_ARN}"
echo ""

echo "   Production-Auto Environment (Settings → Environments → production-auto):"
echo "   ------------------------------------------------------------------------"
echo "   Copy the SAME secrets as 'production' environment above"
echo ""

echo "2. Test credential isolation:"
echo "   ./infrastructure/scripts/test-credential-isolation.sh"
echo ""

echo "3. IMPORTANT: Delete credential files after adding to GitHub:"
echo "   rm preprod-deployer-credentials.json prod-deployer-credentials.json"
echo ""
