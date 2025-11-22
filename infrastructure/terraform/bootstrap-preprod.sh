#!/bin/bash
#
# Bootstrap Preprod Environment
# ==============================
#
# Creates required AWS resources for Terraform state management in preprod.
#
# Prerequisites:
# - AWS CLI installed and configured
# - AWS credentials with permissions to create DynamoDB tables
# - S3 bucket 'sentiment-analyzer-terraform-state' already exists (created by dev bootstrap)
#
# Run this ONCE before first preprod deploy:
#   chmod +x bootstrap-preprod.sh
#   ./bootstrap-preprod.sh

set -e  # Exit on error

echo "🚀 Bootstrapping Preprod Environment..."
echo ""

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

# NOTE: DynamoDB lock table is NO LONGER NEEDED
# Terraform now uses S3 native locking (use_lockfile=true in backend config)
# Lock files are stored as .tflock files directly in S3 bucket
#
# The old DynamoDB table 'terraform-state-lock-preprod' can be deleted after
# confirming S3 native locking works correctly

echo "✅ Skipping DynamoDB lock table creation (using S3 native locking)"

echo ""
echo "✅ Preprod bootstrap complete!"
echo ""
echo "Next steps:"
echo "1. Initialize Terraform with preprod backend:"
echo "   cd infrastructure/terraform"
echo "   terraform init -backend-config=backend-preprod.hcl -reconfigure"
echo ""
echo "2. Deploy preprod infrastructure:"
echo "   terraform apply -var-file=preprod.tfvars"
echo ""
echo "3. Run integration tests against preprod:"
echo "   pytest tests/integration/test_*_preprod.py -v"
