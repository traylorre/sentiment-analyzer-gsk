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

# Create DynamoDB table for preprod state locking
echo "📦 Creating DynamoDB lock table for preprod..."

if aws dynamodb describe-table --table-name terraform-state-lock-preprod --region us-east-1 &> /dev/null; then
    echo "✅ DynamoDB lock table 'terraform-state-lock-preprod' already exists"
else
    aws dynamodb create-table \
        --table-name terraform-state-lock-preprod \
        --attribute-definitions AttributeName=LockID,AttributeType=S \
        --key-schema AttributeName=LockID,KeyType=HASH \
        --billing-mode PAY_PER_REQUEST \
        --region us-east-1 \
        --tags Key=Environment,Value=preprod Key=ManagedBy,Value=Terraform

    echo "✅ Created DynamoDB lock table 'terraform-state-lock-preprod'"
fi

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
