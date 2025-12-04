#!/bin/bash
# Demo Validation Script for Sentiment Analyzer
#
# Usage: ./demo-validate.sh <environment>
# Example: ./demo-validate.sh dev
#
# Performs comprehensive validation:
# 1. All Lambdas deployed and accessible
# 2. DynamoDB has items
# 3. Dashboard loads and responds
# 4. CloudWatch alarms configured
#
# For On-Call Engineers:
#     Run this before any demo or after deployment to verify system health.

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
log_fail() { echo -e "${RED}[FAIL]${NC} $1"; }

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <environment>"
    exit 1
fi

ENVIRONMENT="$1"
FAILURES=0

if [[ "${ENVIRONMENT}" != "dev" && "${ENVIRONMENT}" != "prod" ]]; then
    log_error "Invalid environment: ${ENVIRONMENT}"
    exit 1
fi

log_info "Validating ${ENVIRONMENT} environment"
echo ""

# Test 1: Lambda Functions
echo "=== Lambda Functions ==="
LAMBDAS=("ingestion" "analysis" "dashboard")
for lambda in "${LAMBDAS[@]}"; do
    FUNCTION_NAME="${ENVIRONMENT}-sentiment-${lambda}"
    if aws lambda get-function --function-name "${FUNCTION_NAME}" > /dev/null 2>&1; then
        STATE=$(aws lambda get-function --function-name "${FUNCTION_NAME}" \
            --query 'Configuration.State' --output text)
        if [[ "${STATE}" == "Active" ]]; then
            log_pass "${FUNCTION_NAME}: Active"
        else
            log_fail "${FUNCTION_NAME}: ${STATE}"
            ((FAILURES++))
        fi
    else
        log_fail "${FUNCTION_NAME}: Not found"
        ((FAILURES++))
    fi
done
echo ""

# Test 2: DynamoDB Table
echo "=== DynamoDB Table ==="
TABLE_NAME="${ENVIRONMENT}-sentiment-items"
if aws dynamodb describe-table --table-name "${TABLE_NAME}" > /dev/null 2>&1; then
    TABLE_STATUS=$(aws dynamodb describe-table --table-name "${TABLE_NAME}" \
        --query 'Table.TableStatus' --output text)
    ITEM_COUNT=$(aws dynamodb scan --table-name "${TABLE_NAME}" \
        --select "COUNT" --query 'Count' --output text 2>/dev/null || echo "0")

    if [[ "${TABLE_STATUS}" == "ACTIVE" ]]; then
        log_pass "Table status: ${TABLE_STATUS}"
        log_info "Item count: ${ITEM_COUNT}"

        if [[ "${ITEM_COUNT}" -eq 0 ]]; then
            log_warn "No items in table - run demo-setup.sh first"
        fi
    else
        log_fail "Table status: ${TABLE_STATUS}"
        ((FAILURES++))
    fi

    # Check GSIs
    for gsi in "by_sentiment" "by_tag" "by_status"; do
        GSI_STATUS=$(aws dynamodb describe-table --table-name "${TABLE_NAME}" \
            --query "Table.GlobalSecondaryIndexes[?IndexName=='${gsi}'].IndexStatus" \
            --output text 2>/dev/null || echo "NOT_FOUND")
        if [[ "${GSI_STATUS}" == "ACTIVE" ]]; then
            log_pass "GSI ${gsi}: Active"
        else
            log_fail "GSI ${gsi}: ${GSI_STATUS}"
            ((FAILURES++))
        fi
    done
else
    log_fail "Table not found: ${TABLE_NAME}"
    ((FAILURES++))
fi
echo ""

# Test 3: Dashboard URL
echo "=== Dashboard ==="
DASHBOARD_FUNCTION="${ENVIRONMENT}-sentiment-dashboard"
DASHBOARD_URL=$(aws lambda get-function-url-config \
    --function-name "${DASHBOARD_FUNCTION}" \
    --query 'FunctionUrl' --output text 2>/dev/null || echo "")

if [[ -n "${DASHBOARD_URL}" ]]; then
    log_pass "Function URL: ${DASHBOARD_URL}"

    # Health check
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 "${DASHBOARD_URL}health" 2>/dev/null || echo "000")
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log_pass "Health check: HTTP ${HTTP_CODE}"
    else
        log_fail "Health check: HTTP ${HTTP_CODE}"
        ((FAILURES++))
    fi

    # Main page
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        --max-time 10 "${DASHBOARD_URL}" 2>/dev/null || echo "000")
    if [[ "${HTTP_CODE}" == "200" ]]; then
        log_pass "Main page: HTTP ${HTTP_CODE}"
    else
        log_fail "Main page: HTTP ${HTTP_CODE}"
        ((FAILURES++))
    fi
else
    log_fail "Function URL not configured"
    ((FAILURES++))
fi
echo ""

# Test 4: Secrets
echo "=== Secrets Manager ==="
SECRETS=(
    "${ENVIRONMENT}/sentiment-analyzer/newsapi"
    "${ENVIRONMENT}/sentiment-analyzer/dashboard-api-key"
)
for secret in "${SECRETS[@]}"; do
    if aws secretsmanager describe-secret --secret-id "${secret}" > /dev/null 2>&1; then
        log_pass "Secret: ${secret}"
    else
        log_fail "Secret not found: ${secret}"
        ((FAILURES++))
    fi
done
echo ""

# Test 5: SNS Topic
echo "=== SNS Topic ==="
TOPIC_NAME="${ENVIRONMENT}-sentiment-analysis-requests"
TOPIC_ARN=$(aws sns list-topics --query "Topics[?contains(TopicArn, '${TOPIC_NAME}')].TopicArn" \
    --output text 2>/dev/null || echo "")
if [[ -n "${TOPIC_ARN}" ]]; then
    log_pass "SNS Topic: ${TOPIC_ARN}"

    # Check subscriptions
    SUB_COUNT=$(aws sns list-subscriptions-by-topic --topic-arn "${TOPIC_ARN}" \
        --query 'length(Subscriptions)' --output text 2>/dev/null || echo "0")
    log_info "Subscriptions: ${SUB_COUNT}"
else
    log_fail "SNS Topic not found: ${TOPIC_NAME}"
    ((FAILURES++))
fi
echo ""

# Test 6: CloudWatch Alarms
echo "=== CloudWatch Alarms ==="
ALARM_PREFIX="${ENVIRONMENT}-sentiment"
ALARMS=$(aws cloudwatch describe-alarms \
    --alarm-name-prefix "${ALARM_PREFIX}" \
    --query 'MetricAlarms[*].[AlarmName, StateValue]' \
    --output text 2>/dev/null || echo "")

if [[ -n "${ALARMS}" ]]; then
    while IFS=$'\t' read -r name state; do
        if [[ "${state}" == "OK" ]]; then
            log_pass "${name}: ${state}"
        elif [[ "${state}" == "ALARM" ]]; then
            log_fail "${name}: ${state}"
            ((FAILURES++))
        else
            log_warn "${name}: ${state}"
        fi
    done <<< "${ALARMS}"
else
    log_warn "No alarms found with prefix: ${ALARM_PREFIX}"
fi
echo ""

# Test 7: EventBridge Rule
echo "=== EventBridge ==="
RULE_NAME="${ENVIRONMENT}-sentiment-ingestion-schedule"
if aws events describe-rule --name "${RULE_NAME}" > /dev/null 2>&1; then
    STATE=$(aws events describe-rule --name "${RULE_NAME}" \
        --query 'State' --output text)
    if [[ "${STATE}" == "ENABLED" ]]; then
        log_pass "Schedule rule: ${STATE}"
    else
        log_warn "Schedule rule: ${STATE}"
    fi
else
    log_warn "EventBridge rule not found: ${RULE_NAME}"
fi
echo ""

# Summary
echo "=== Summary ==="
if [[ ${FAILURES} -eq 0 ]]; then
    log_pass "All validation checks passed!"
    exit 0
else
    log_fail "${FAILURES} validation check(s) failed"
    exit 1
fi
