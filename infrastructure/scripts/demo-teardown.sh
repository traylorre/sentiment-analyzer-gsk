#!/bin/bash
# Demo Teardown Script for Sentiment Analyzer
#
# Usage: ./demo-teardown.sh <environment>
# Example: ./demo-teardown.sh dev
#
# Optional cleanup script to remove data after demo.
# Use with caution - this deletes data!
#
# For On-Call Engineers:
#     Only use this in dev environment for cleanup.
#     NEVER run in production without explicit approval.

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

# Production safety check
if [[ "${ENVIRONMENT}" == "prod" ]]; then
    log_error "Teardown is not allowed in production!"
    log_error "If you really need to clean prod data, do it manually."
    exit 1
fi

log_warn "This will delete demo data from ${ENVIRONMENT} environment!"
read -p "Are you sure? Type 'yes' to continue: " confirm
if [[ "${confirm}" != "yes" ]]; then
    log_info "Teardown cancelled"
    exit 0
fi

log_info "Starting teardown for ${ENVIRONMENT}"

# Delete items from DynamoDB (optional)
TABLE_NAME="${ENVIRONMENT}-sentiment-items"

log_info "Clearing DynamoDB table: ${TABLE_NAME}"

# Scan and delete all items (for dev only)
# This is slow but safe for small tables
ITEMS=$(aws dynamodb scan \
    --table-name "${TABLE_NAME}" \
    --projection-expression "source_id, #ts" \
    --expression-attribute-names '{"#ts": "timestamp"}' \
    --output json 2>/dev/null || echo '{"Items": []}')

ITEM_COUNT=$(echo "${ITEMS}" | jq '.Items | length')
log_info "Found ${ITEM_COUNT} items to delete"

if [[ "${ITEM_COUNT}" -gt 0 ]]; then
    echo "${ITEMS}" | jq -c '.Items[]' | while read -r item; do
        source_id=$(echo "${item}" | jq -r '.source_id.S')
        timestamp=$(echo "${item}" | jq -r '.timestamp.S')

        aws dynamodb delete-item \
            --table-name "${TABLE_NAME}" \
            --key "{\"source_id\": {\"S\": \"${source_id}\"}, \"timestamp\": {\"S\": \"${timestamp}\"}}" \
            > /dev/null 2>&1

        echo -n "."
    done
    echo ""
    log_info "Deleted ${ITEM_COUNT} items"
fi

# Verify cleanup
REMAINING=$(aws dynamodb scan \
    --table-name "${TABLE_NAME}" \
    --select "COUNT" \
    --query 'Count' \
    --output text 2>/dev/null || echo "0")

log_info "Items remaining: ${REMAINING}"

log_info "Teardown complete"
echo ""
echo "Note: Lambda functions and infrastructure remain intact."
echo "To fully remove, run: terraform destroy -var='environment=${ENVIRONMENT}'"
