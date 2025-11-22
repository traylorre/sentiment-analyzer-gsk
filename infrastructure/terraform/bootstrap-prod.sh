#!/bin/bash
#
# Bootstrap Production Environment
# =================================
#
# Creates required AWS resources for Terraform state management in production.
#
# Prerequisites:
# - AWS CLI installed and configured
# - AWS credentials with permissions to create DynamoDB tables
# - S3 bucket 'sentiment-analyzer-terraform-state' already exists (created by dev bootstrap)
# - Preprod environment deployed and validated
#
# IMPORTANT: Only run this after preprod validation is complete!
#
# Run this ONCE before first prod deploy:
#   chmod +x bootstrap-prod.sh
#   ./bootstrap-prod.sh

set -e  # Exit on error

echo "🚀 Bootstrapping Production Environment..."
echo ""

# Safety check: Confirm production deployment
read -p "⚠️  WARNING: This will create production infrastructure. Continue? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo "❌ Aborted. Run this script again when ready for production."
    exit 1
fi

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "❌ AWS CLI not found. Please install it first."
    exit 1
fi

# Check AWS credentials
if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please run 'aws configure'."
    exit 1
fi

echo "✅ AWS CLI configured"
echo ""

# Verify we're using PROD credentials (not preprod)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "📋 AWS Account ID: ${AWS_ACCOUNT_ID}"
echo ""

read -p "Confirm this is the CORRECT AWS account for PRODUCTION (yes/no): " account_confirm
if [ "$account_confirm" != "yes" ]; then
    echo "❌ Aborted. Verify AWS credentials and try again."
    exit 1
fi

# NOTE: DynamoDB lock table is NO LONGER NEEDED
# Terraform now uses S3 native locking (use_lockfile=true in backend config)
# Lock files are stored as .tflock files directly in S3 bucket
#
# The old DynamoDB table 'terraform-state-lock-prod' can be deleted after
# confirming S3 native locking works correctly

echo "✅ Skipping DynamoDB lock table creation (using S3 native locking)"

echo ""
echo "✅ Production bootstrap complete!"
echo ""
echo "⚠️  IMPORTANT: Before deploying to production:"
echo ""
echo "1. Verify preprod deployment is stable:"
echo "   - Preprod integration tests passing"
echo "   - No CloudWatch alarms triggered"
echo "   - Manual testing complete"
echo ""
echo "2. Review production configuration:"
echo "   cd infrastructure/terraform"
echo "   terraform init -backend-config=backend-prod.hcl -reconfigure"
echo "   terraform plan -var-file=prod.tfvars"
echo ""
echo "3. Deploy production infrastructure:"
echo "   terraform apply -var-file=prod.tfvars"
echo ""
echo "4. Run canary test:"
echo "   # Test production dashboard health endpoint"
echo ""
echo "5. Monitor CloudWatch alarms for 24 hours"
echo ""
