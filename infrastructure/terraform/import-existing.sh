#!/bin/bash
# Import existing AWS resources into Terraform state
#
# Run this ONCE after setting up the S3 backend to import all existing
# resources that were created before state management was configured.
#
# Usage:
#   cd infrastructure/terraform
#   chmod +x import-existing.sh
#   ./import-existing.sh
#
# Prerequisites:
#   - AWS CLI configured with appropriate credentials
#   - Terraform initialized with S3 backend
#   - All resources already exist in AWS

set -e

ENVIRONMENT="dev"
AWS_REGION="us-east-1"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "================================================"
echo "Terraform Import Script"
echo "================================================"
echo "Environment: $ENVIRONMENT"
echo "Region: $AWS_REGION"
echo "Account: $ACCOUNT_ID"
echo "================================================"
echo ""

# Ensure we're in the right directory
if [ ! -f "main.tf" ]; then
    echo "Error: Run this script from infrastructure/terraform directory"
    exit 1
fi

# Initialize terraform
echo "Initializing Terraform..."
terraform init -input=false

# Function to import a resource (skips if already in state)
import_resource() {
    local resource_addr="$1"
    local resource_id="$2"

    echo ""
    echo "Importing: $resource_addr"

    # Check if already in state
    if terraform state show "$resource_addr" &>/dev/null; then
        echo "  ✓ Already in state, skipping"
        return 0
    fi

    # Import
    if terraform import -var="environment=$ENVIRONMENT" "$resource_addr" "$resource_id"; then
        echo "  ✓ Imported successfully"
    else
        echo "  ✗ Import failed (resource may not exist)"
        return 1
    fi
}

echo ""
echo "========== Importing Secrets Manager =========="
import_resource "module.secrets.aws_secretsmanager_secret.newsapi" "$ENVIRONMENT/sentiment-analyzer/newsapi" || true
import_resource "module.secrets.aws_secretsmanager_secret.dashboard_api_key" "$ENVIRONMENT/sentiment-analyzer/dashboard-api-key" || true

echo ""
echo "========== Importing DynamoDB =========="
import_resource "module.dynamodb.aws_dynamodb_table.sentiment_items" "$ENVIRONMENT-sentiment-items" || true
import_resource "module.dynamodb.aws_backup_vault.dynamodb" "$ENVIRONMENT-dynamodb-backup-vault" || true
import_resource "module.dynamodb.aws_iam_role.backup" "$ENVIRONMENT-dynamodb-backup-role" || true

echo ""
echo "========== Importing IAM Roles =========="
import_resource "module.iam.aws_iam_role.ingestion_lambda" "$ENVIRONMENT-ingestion-lambda-role" || true
import_resource "module.iam.aws_iam_role.analysis_lambda" "$ENVIRONMENT-analysis-lambda-role" || true
import_resource "module.iam.aws_iam_role.dashboard_lambda" "$ENVIRONMENT-dashboard-lambda-role" || true
import_resource "module.iam.aws_iam_role.metrics_lambda" "$ENVIRONMENT-metrics-lambda-role" || true
import_resource "module.iam.aws_iam_role.notification_lambda" "$ENVIRONMENT-notification-lambda-role" || true
import_resource "module.iam.aws_iam_role.sse_streaming_lambda" "$ENVIRONMENT-sse-streaming-lambda-role" || true

echo ""
echo "========== Importing S3 Buckets =========="
import_resource "aws_s3_bucket.lambda_deployments" "$ENVIRONMENT-sentiment-lambda-deployments" || true

echo ""
echo "========== Importing SNS Topics =========="
import_resource "module.sns.aws_sns_topic.analysis_requests" "arn:aws:sns:$AWS_REGION:$ACCOUNT_ID:$ENVIRONMENT-sentiment-analysis" || true

echo ""
echo "========== Importing EventBridge =========="
import_resource "module.eventbridge.aws_cloudwatch_event_rule.ingestion_schedule" "$ENVIRONMENT-sentiment-ingestion-schedule" || true

echo ""
echo "========== Importing Budgets =========="
# Budget imports require account ID prefix
import_resource "module.monitoring.aws_budgets_budget.monthly" "$ACCOUNT_ID:$ENVIRONMENT-sentiment-monthly-budget" || true

echo ""
echo "========== Importing CloudWatch Alarms =========="
import_resource "module.monitoring.aws_cloudwatch_metric_alarm.high_error_rate" "$ENVIRONMENT-sentiment-high-error-rate" || true
import_resource "module.monitoring.aws_cloudwatch_metric_alarm.lambda_throttles" "$ENVIRONMENT-sentiment-lambda-throttles" || true

echo ""
echo "========== Importing CloudWatch Log Groups =========="
import_resource "module.analysis_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-analysis" || true
import_resource "module.dashboard_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-dashboard" || true
import_resource "module.ingestion_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-ingestion" || true
import_resource "module.metrics_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-metrics" || true
import_resource "module.notification_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-notification" || true
import_resource "module.sse_streaming_lambda.aws_cloudwatch_log_group.lambda" "/aws/lambda/$ENVIRONMENT-sentiment-sse-streaming" || true

echo ""
echo "========== Importing Backup Plans =========="
# Get backup plan ID dynamically
BACKUP_PLAN_ID=$(aws backup list-backup-plans --region $AWS_REGION --query "BackupPlansList[?BackupPlanName=='$ENVIRONMENT-dynamodb-daily-backup'].BackupPlanId" --output text 2>/dev/null || echo "")
if [ -n "$BACKUP_PLAN_ID" ] && [ "$BACKUP_PLAN_ID" != "None" ]; then
    import_resource "module.dynamodb.aws_backup_plan.dynamodb_daily" "$BACKUP_PLAN_ID" || true

    # Import backup selection
    SELECTION_ID=$(aws backup list-backup-selections --backup-plan-id "$BACKUP_PLAN_ID" --region $AWS_REGION --query "BackupSelectionsList[?SelectionName=='$ENVIRONMENT-dynamodb-backup-selection'].SelectionId" --output text 2>/dev/null || echo "")
    if [ -n "$SELECTION_ID" ] && [ "$SELECTION_ID" != "None" ]; then
        import_resource "module.dynamodb.aws_backup_selection.dynamodb" "$BACKUP_PLAN_ID|$SELECTION_ID" || true
    fi
else
    echo "  Backup plan not found, skipping"
fi

echo ""
echo "================================================"
echo "Import complete!"
echo ""
echo "Next steps:"
echo "1. Run 'terraform plan -var=\"environment=$ENVIRONMENT\"' to verify"
echo "2. Review any differences and adjust as needed"
echo "3. Commit any changes to terraform configuration"
echo "================================================"
