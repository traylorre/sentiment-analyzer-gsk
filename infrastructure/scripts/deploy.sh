#!/bin/bash
# Deploy Sentiment Analyzer Lambda Functions
#
# Usage: ./deploy.sh <environment>
# Example: ./deploy.sh dev
#
# For On-Call Engineers:
#     If deployment fails, check:
#     1. AWS credentials are configured
#     2. S3 bucket exists for Lambda packages
#     3. All secrets exist in Secrets Manager
#     4. IAM roles have correct permissions
#
#     See SC-06 in ON_CALL_SOP.md for deployment issues.
#
# Security:
#     - Validates environment parameter
#     - Checks required secrets before deploy
#     - Uses Terraform workspaces for isolation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TERRAFORM_DIR="${PROJECT_ROOT}/infrastructure/terraform"
SRC_DIR="${PROJECT_ROOT}/src"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
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
    echo "Usage: $0 <environment>"
    echo "  environment: dev or prod"
    echo ""
    echo "Examples:"
    echo "  $0 dev    # Deploy to dev environment"
    echo "  $0 prod   # Deploy to prod environment"
    exit 1
}

# Validate arguments
if [[ $# -ne 1 ]]; then
    usage
fi

ENVIRONMENT="$1"

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}. Must be 'dev' or 'prod'."
    exit 1
fi

log_info "Starting deployment to ${ENVIRONMENT} environment"

# Step 1: Run pre-deploy checklist
log_info "Running pre-deploy checklist..."
if [[ -f "${SCRIPT_DIR}/pre-deploy-checklist.sh" ]]; then
    "${SCRIPT_DIR}/pre-deploy-checklist.sh" "${ENVIRONMENT}"
else
    log_warn "Pre-deploy checklist not found, skipping..."
fi

# Step 2: Build Lambda packages
log_info "Building Lambda deployment packages..."

LAMBDAS=("ingestion" "metrics" "notification")
BUILD_DIR="${PROJECT_ROOT}/build"
mkdir -p "${BUILD_DIR}"

for lambda in "${LAMBDAS[@]}"; do
    log_info "Packaging ${lambda} Lambda..."

    LAMBDA_SRC="${SRC_DIR}/lambdas/${lambda}"
    PACKAGE_DIR="${BUILD_DIR}/${lambda}"
    ZIP_FILE="${BUILD_DIR}/${lambda}.zip"

    # Clean previous build
    rm -rf "${PACKAGE_DIR}" "${ZIP_FILE}"
    mkdir -p "${PACKAGE_DIR}"

    # Copy Lambda code
    if [[ -d "${LAMBDA_SRC}" ]]; then
        cp -r "${LAMBDA_SRC}"/* "${PACKAGE_DIR}/"
    else
        log_warn "Lambda source directory not found: ${LAMBDA_SRC}"
        continue
    fi

    # Copy shared modules
    SHARED_DIR="${SRC_DIR}/lambdas/shared"
    if [[ -d "${SHARED_DIR}" ]]; then
        cp -r "${SHARED_DIR}" "${PACKAGE_DIR}/"
    fi

    # Copy lib modules
    LIB_DIR="${SRC_DIR}/lib"
    if [[ -d "${LIB_DIR}" ]]; then
        cp -r "${LIB_DIR}" "${PACKAGE_DIR}/"
    fi

    # Install dependencies (if requirements.txt exists)
    if [[ -f "${LAMBDA_SRC}/requirements.txt" ]]; then
        pip install -r "${LAMBDA_SRC}/requirements.txt" -t "${PACKAGE_DIR}" --quiet
    fi

    # Create ZIP package
    cd "${PACKAGE_DIR}"
    zip -r "${ZIP_FILE}" . -x "*.pyc" -x "__pycache__/*" -x "*.egg-info/*" > /dev/null
    cd - > /dev/null

    log_info "Created ${ZIP_FILE}"
done

# Step 3: Upload packages to S3
log_info "Uploading packages to S3..."

# Get S3 bucket name from Terraform
cd "${TERRAFORM_DIR}"
terraform init -input=false > /dev/null 2>&1

# Select workspace
terraform workspace select "${ENVIRONMENT}" 2>/dev/null || terraform workspace new "${ENVIRONMENT}"

BUCKET_NAME="${ENVIRONMENT}-sentiment-lambda-deployments"

for lambda in "${LAMBDAS[@]}"; do
    ZIP_FILE="${BUILD_DIR}/${lambda}.zip"
    if [[ -f "${ZIP_FILE}" ]]; then
        S3_KEY="${lambda}/lambda.zip"
        log_info "Uploading ${lambda}.zip to s3://${BUCKET_NAME}/${S3_KEY}"
        aws s3 cp "${ZIP_FILE}" "s3://${BUCKET_NAME}/${S3_KEY}" --quiet
    fi
done

# Step 4: Apply Terraform
log_info "Applying Terraform configuration..."

cd "${TERRAFORM_DIR}"

# Plan first
terraform plan -var="environment=${ENVIRONMENT}" -out=tfplan

# Apply
terraform apply tfplan

# Cleanup plan file
rm -f tfplan

# Step 5: Verify deployment
log_info "Verifying deployment..."

# Get Lambda ARNs from Terraform output
INGESTION_ARN=$(terraform output -raw ingestion_lambda_arn 2>/dev/null || echo "")
ANALYSIS_ARN=$(terraform output -raw analysis_lambda_arn 2>/dev/null || echo "")
DASHBOARD_ARN=$(terraform output -raw dashboard_lambda_arn 2>/dev/null || echo "")
DASHBOARD_URL=$(terraform output -raw dashboard_function_url 2>/dev/null || echo "")

if [[ -n "${INGESTION_ARN}" ]]; then
    log_info "Ingestion Lambda: ${INGESTION_ARN}"
fi

if [[ -n "${ANALYSIS_ARN}" ]]; then
    log_info "Analysis Lambda: ${ANALYSIS_ARN}"
fi

if [[ -n "${DASHBOARD_ARN}" ]]; then
    log_info "Dashboard Lambda: ${DASHBOARD_ARN}"
fi

if [[ -n "${DASHBOARD_URL}" ]]; then
    log_info "Dashboard URL: ${DASHBOARD_URL}"
fi

log_info "Deployment to ${ENVIRONMENT} completed successfully!"
echo ""
echo "Next steps:"
echo "  1. Run demo-validate.sh to verify deployment"
echo "  2. Check CloudWatch logs for any errors"
echo "  3. Monitor alarms in CloudWatch"
