#!/bin/bash
# Demo Setup Script for Sentiment Analyzer
#
# Usage: ./demo-setup.sh <environment>
# Example: ./demo-setup.sh dev
#
# This script prepares the environment for a demo:
# 1. Verifies all secrets exist
# 2. Triggers initial ingestion
# 3. Waits for data to populate
#
# For On-Call Engineers:
#     Run this 15-30 minutes before a demo to ensure data is available.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <environment>"
    exit 1
fi

ENVIRONMENT="$1"

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}"
    exit 1
fi

log_info "Setting up demo environment: ${ENVIRONMENT}"

# Step 1: Verify secrets
log_info "Verifying secrets..."

NEWSAPI_SECRET="${ENVIRONMENT}/sentiment-analyzer/newsapi"
DASHBOARD_SECRET="${ENVIRONMENT}/sentiment-analyzer/dashboard-api-key"

for secret in "${NEWSAPI_SECRET}" "${DASHBOARD_SECRET}"; do
    if aws secretsmanager describe-secret --secret-id "${secret}" > /dev/null 2>&1; then
        log_info "Secret exists: ${secret}"
    else
        log_error "Secret not found: ${secret}"
        log_error "Please create the secret before running the demo"
        exit 1
    fi
done

# Step 2: Verify Lambda functions
log_info "Verifying Lambda functions..."

LAMBDAS=("ingestion" "analysis" "dashboard")
for lambda in "${LAMBDAS[@]}"; do
    FUNCTION_NAME="${ENVIRONMENT}-sentiment-${lambda}"
    if aws lambda get-function --function-name "${FUNCTION_NAME}" > /dev/null 2>&1; then
        log_info "Lambda exists: ${FUNCTION_NAME}"
    else
        log_error "Lambda not found: ${FUNCTION_NAME}"
        log_error "Please deploy the Lambdas first"
        exit 1
    fi
done

# Step 3: Trigger initial ingestion
log_info "Triggering initial ingestion..."

INGESTION_FUNCTION="${ENVIRONMENT}-sentiment-ingestion"
INVOKE_RESULT=$(aws lambda invoke \
    --function-name "${INGESTION_FUNCTION}" \
    --payload '{"source": "demo-setup"}' \
    --log-type Tail \
    /tmp/demo-setup-response.json 2>&1)

if [[ $? -eq 0 ]]; then
    log_info "Ingestion triggered successfully"
    
    # Check response
    if [[ -f /tmp/demo-setup-response.json ]]; then
        RESPONSE=$(cat /tmp/demo-setup-response.json)
        log_info "Response: ${RESPONSE}"
    fi
else
    log_warn "Ingestion may have failed: ${INVOKE_RESULT}"
fi

# Step 4: Wait for analysis to complete
log_info "Waiting for analysis to complete (60 seconds)..."
sleep 60

# Step 5: Verify data in DynamoDB
log_info "Verifying data in DynamoDB..."

TABLE_NAME="${ENVIRONMENT}-sentiment-items"
ITEM_COUNT=$(aws dynamodb scan \
    --table-name "${TABLE_NAME}" \
    --select "COUNT" \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

log_info "Items in table: ${ITEM_COUNT}"

if [[ "${ITEM_COUNT}" -gt 0 ]]; then
    # Get sentiment distribution
    for sentiment in "positive" "neutral" "negative"; do
        COUNT=$(aws dynamodb query \
            --table-name "${TABLE_NAME}" \
            --index-name "by_sentiment" \
            --key-condition-expression "sentiment = :s" \
            --expression-attribute-values "{\":s\": {\"S\": \"${sentiment}\"}}" \
            --select "COUNT" \
            --query 'Count' \
            --output text 2>/dev/null || echo "0")
        log_info "  ${sentiment}: ${COUNT}"
    done
else
    log_warn "No items found. Analysis may still be in progress."
fi

# Step 6: Get dashboard URL
log_info "Getting dashboard URL..."

DASHBOARD_URL=$(aws lambda get-function-url-config \
    --function-name "${ENVIRONMENT}-sentiment-dashboard" \
    --query 'FunctionUrl' \
    --output text 2>/dev/null || echo "")

if [[ -n "${DASHBOARD_URL}" ]]; then
    log_info "Dashboard URL: ${DASHBOARD_URL}"
    
    # Test dashboard health
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${DASHBOARD_URL}health" || echo "000")
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log_info "Dashboard health check: OK"
    else
        log_warn "Dashboard health check: HTTP ${HTTP_CODE}"
    fi
else
    log_warn "Dashboard URL not found"
fi

log_info "Demo setup complete!"
echo ""
echo "Demo preparation checklist:"
echo "  [x] Secrets verified"
echo "  [x] Lambdas deployed"
echo "  [x] Initial data ingested"
echo "  [ ] Dashboard URL: ${DASHBOARD_URL:-'Not available'}"
echo ""
echo "Recommended: Run demo-validate.sh for full validation"
