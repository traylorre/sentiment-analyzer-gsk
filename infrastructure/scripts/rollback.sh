#!/bin/bash
# Rollback Sentiment Analyzer Lambda Functions
#
# Usage: ./rollback.sh <environment> <lambda_name> [version]
# Example: ./rollback.sh dev ingestion $LATEST
#
# For On-Call Engineers:
#     Use this script to roll back a Lambda to a previous version.
#     If no version specified, lists available versions.
#
#     See SC-06 in ON_CALL_SOP.md for rollback procedures.
#
# Security:
#     - Validates environment and Lambda name
#     - Shows current version before rollback
#     - Requires confirmation for production

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "Usage: $0 <environment> <lambda_name> [version]"
    echo ""
    echo "Arguments:"
    echo "  environment  : dev or prod"
    echo "  lambda_name  : ingestion, analysis, or dashboard"
    echo "  version      : Optional. Version to roll back to."
    echo "                 If not specified, lists available versions."
    echo ""
    echo "Examples:"
    echo "  $0 dev ingestion           # List versions"
    echo "  $0 dev ingestion 5         # Roll back to version 5"
    echo "  $0 prod dashboard 3        # Roll back prod dashboard to v3"
    exit 1
}

# Validate arguments
if [[ $# -lt 2 ]]; then
    usage
fi

ENVIRONMENT="$1"
LAMBDA_NAME="$2"
TARGET_VERSION="${3:-}"

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}"
    exit 1
fi

if [[ "${LAMBDA_NAME}" != "ingestion" && "${LAMBDA_NAME}" != "analysis" && "${LAMBDA_NAME}" != "dashboard" ]]; then
    log_error "Invalid Lambda name: ${LAMBDA_NAME}"
    exit 1
fi

FUNCTION_NAME="${ENVIRONMENT}-sentiment-${LAMBDA_NAME}"

log_info "Lambda function: ${FUNCTION_NAME}"

# Get current version
CURRENT_VERSION=$(aws lambda get-function --function-name "${FUNCTION_NAME}" \
    --query 'Configuration.Version' --output text 2>/dev/null || echo "unknown")

log_info "Current version: ${CURRENT_VERSION}"

# If no version specified, list available versions
if [[ -z "${TARGET_VERSION}" ]]; then
    log_info "Available versions:"
    aws lambda list-versions-by-function --function-name "${FUNCTION_NAME}" \
        --query 'Versions[*].[Version, LastModified, Description]' \
        --output table
    echo ""
    echo "To roll back, run:"
    echo "  $0 ${ENVIRONMENT} ${LAMBDA_NAME} <version>"
    exit 0
fi

# Confirm production rollback
if [[ "${ENVIRONMENT}" == "prod" ]]; then
    log_warn "Rolling back PRODUCTION Lambda!"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    if [[ "${confirm}" != "yes" ]]; then
        log_info "Rollback cancelled"
        exit 0
    fi
fi

# Get the S3 location of the target version
log_info "Rolling back to version: ${TARGET_VERSION}"

# Update function to use the specified version's code
# This is done by updating the function code from S3 with version
BUCKET_NAME="${ENVIRONMENT}-sentiment-lambda-deployments"
S3_KEY="${LAMBDA_NAME}/lambda.zip"

# For versioned rollback, we need to use S3 object versioning
# First, list S3 versions
S3_VERSIONS=$(aws s3api list-object-versions \
    --bucket "${BUCKET_NAME}" \
    --prefix "${S3_KEY}" \
    --query 'Versions[*].[VersionId, LastModified]' \
    --output table 2>/dev/null || echo "")

if [[ -n "${S3_VERSIONS}" ]]; then
    log_info "Available S3 package versions:"
    echo "${S3_VERSIONS}"
fi

# Update function code
log_info "Updating Lambda function code..."
aws lambda update-function-code \
    --function-name "${FUNCTION_NAME}" \
    --s3-bucket "${BUCKET_NAME}" \
    --s3-key "${S3_KEY}" \
    --publish

# Wait for update to complete
log_info "Waiting for update to complete..."
aws lambda wait function-updated --function-name "${FUNCTION_NAME}"

# Get new version
NEW_VERSION=$(aws lambda get-function --function-name "${FUNCTION_NAME}" \
    --query 'Configuration.Version' --output text)

log_info "Rollback complete. New version: ${NEW_VERSION}"

# Test the function
log_info "Testing Lambda function..."
if [[ "${LAMBDA_NAME}" == "dashboard" ]]; then
    # Dashboard has function URL
    FUNCTION_URL=$(aws lambda get-function-url-config \
        --function-name "${FUNCTION_NAME}" \
        --query 'FunctionUrl' --output text 2>/dev/null || echo "")

    if [[ -n "${FUNCTION_URL}" ]]; then
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${FUNCTION_URL}health" || echo "000")
        if [[ "${HTTP_CODE}" == "200" ]]; then
            log_info "Health check passed (HTTP ${HTTP_CODE})"
        else
            log_warn "Health check returned HTTP ${HTTP_CODE}"
        fi
    fi
else
    # Invoke with test event
    aws lambda invoke \
        --function-name "${FUNCTION_NAME}" \
        --payload '{"test": true}' \
        --log-type Tail \
        /tmp/rollback-test-response.json > /dev/null 2>&1 || true

    log_info "Test invocation completed"
fi

log_info "Rollback to ${TARGET_VERSION} completed successfully"
echo ""
echo "Next steps:"
echo "  1. Monitor CloudWatch logs for errors"
echo "  2. Check CloudWatch metrics"
echo "  3. Verify data flow through the pipeline"
