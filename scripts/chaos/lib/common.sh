#!/usr/bin/env bash
# Chaos Testing Common Library
# ============================
# Shared functions for chaos injection, restore, and status scripts.
#
# Usage: source scripts/chaos/lib/common.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Output helpers
# ============================================================================

die() {
    echo -e "${RED}ERROR: $*${NC}" >&2
    exit 1
}

info() {
    echo -e "${GREEN}INFO: $*${NC}"
}

warn() {
    echo -e "${YELLOW}WARN: $*${NC}"
}

debug() {
    if [[ "${CHAOS_DEBUG:-}" == "true" ]]; then
        echo -e "${BLUE}DEBUG: $*${NC}" >&2
    fi
}

# ============================================================================
# Environment validation
# ============================================================================

validate_environment() {
    local env="$1"
    # force_prod parameter kept for backward compatibility but always blocked
    # Production chaos requires a separate approval workflow (Issue #28)
    local force_prod="${2:-false}"

    if [[ "$env" == "prod" ]]; then
        die "Chaos experiments CANNOT run in production via this script. Production chaos requires a separate approval workflow."
    fi

    if [[ ! "$env" =~ ^(dev|preprod|test)$ ]]; then
        die "Invalid environment: $env. Must be one of: dev, preprod, test"
    fi
}

# ============================================================================
# SSM Kill Switch
# ============================================================================

check_kill_switch() {
    local env="$1"
    local param_name="/chaos/${env}/kill-switch"

    local value
    local exit_code=0
    value=$(aws ssm get-parameter \
        --name "$param_name" \
        --query "Parameter.Value" \
        --output text 2>/dev/null) || exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        # Check if this is a ParameterNotFound (first-time setup) vs SSM outage
        if aws ssm get-parameter --name "$param_name" 2>&1 | grep -q "ParameterNotFound"; then
            # No kill switch parameter = first-time setup, proceed
            echo "disarmed"
            return
        fi
        # FAIL-CLOSED: SSM is unreachable, block injection for safety
        die "Cannot verify kill switch (SSM unavailable) -- blocking injection for safety"
    fi

    if [[ "$value" == "triggered" ]]; then
        die "Kill switch is triggered -- resolve before injecting new chaos. Run: scripts/chaos/restore.sh $env"
    fi

    echo "$value"
}

set_kill_switch() {
    local env="$1"
    local value="$2"
    local param_name="/chaos/${env}/kill-switch"

    aws ssm put-parameter \
        --name "$param_name" \
        --value "$value" \
        --type "String" \
        --overwrite \
        --no-cli-pager >/dev/null

    debug "Kill switch set to: $value"
}

# ============================================================================
# SSM Snapshot (save/restore Lambda configuration)
# ============================================================================

snapshot_config() {
    local env="$1"
    local scenario="$2"
    local function_name="$3"
    local param_name="/chaos/${env}/snapshot/${scenario}"

    # Get current Lambda configuration
    local config
    config=$(aws lambda get-function-configuration \
        --function-name "$function_name" \
        --query '{MemorySize: MemorySize, Timeout: Timeout, FunctionName: FunctionName, FunctionArn: FunctionArn}' \
        --output json 2>/dev/null) || die "Failed to get config for $function_name"

    # Get current reserved concurrency (may not be set)
    local concurrency
    concurrency=$(aws lambda get-function-concurrency \
        --function-name "$function_name" \
        --query 'ReservedConcurrentExecutions' \
        --output text 2>/dev/null || echo "NONE")

    # Build snapshot JSON
    local snapshot
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    snapshot=$(echo "$config" | python3 -c "
import json, sys
config = json.load(sys.stdin)
config['ReservedConcurrency'] = '$concurrency'
config['SnapshotTimestamp'] = '$timestamp'
config['Scenario'] = '$scenario'
print(json.dumps(config))
")

    # Save to SSM
    aws ssm put-parameter \
        --name "$param_name" \
        --value "$snapshot" \
        --type "String" \
        --overwrite \
        --no-cli-pager >/dev/null

    info "Snapshot saved: $param_name"
    debug "Snapshot: $snapshot"
}

get_snapshot() {
    local env="$1"
    local scenario="$2"
    local param_name="/chaos/${env}/snapshot/${scenario}"

    aws ssm get-parameter \
        --name "$param_name" \
        --query "Parameter.Value" \
        --output text 2>/dev/null || echo ""
}

delete_snapshot() {
    local env="$1"
    local scenario="$2"
    local param_name="/chaos/${env}/snapshot/${scenario}"

    aws ssm delete-parameter \
        --name "$param_name" \
        --no-cli-pager 2>/dev/null || true
}

list_snapshots() {
    local env="$1"
    local prefix="/chaos/${env}/snapshot/"

    aws ssm get-parameters-by-path \
        --path "$prefix" \
        --query "Parameters[].{Name:Name,Value:Value}" \
        --output json 2>/dev/null || echo "[]"
}

# ============================================================================
# DynamoDB Audit Log
# ============================================================================

log_experiment() {
    local env="$1"
    local scenario="$2"
    local action="$3"  # "started" or "stopped" or "andon_cord"
    local details="${4:-}"

    local table_name="${env}-chaos-experiments"
    local experiment_id
    experiment_id=$(python3 -c "import uuid; print(str(uuid.uuid4()))")
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local ttl
    ttl=$(python3 -c "import time; print(int(time.time() + 7*86400))")

    aws dynamodb put-item \
        --table-name "$table_name" \
        --item "{
            \"experiment_id\": {\"S\": \"$experiment_id\"},
            \"scenario_type\": {\"S\": \"$scenario\"},
            \"status\": {\"S\": \"$action\"},
            \"environment\": {\"S\": \"$env\"},
            \"created_at\": {\"S\": \"$timestamp\"},
            \"updated_at\": {\"S\": \"$timestamp\"},
            \"results\": {\"M\": {
                \"injection_method\": {\"S\": \"external_api\"},
                \"${action}_at\": {\"S\": \"$timestamp\"},
                \"details\": {\"S\": \"${details:-none}\"}
            }},
            \"ttl_timestamp\": {\"N\": \"$ttl\"}
        }" \
        --no-cli-pager 2>/dev/null || warn "Failed to log experiment to DynamoDB (non-fatal)"

    echo "$experiment_id"
}

# ============================================================================
# Lambda naming helpers
# ============================================================================

get_function_name() {
    local env="$1"
    local service="$2"
    echo "${env}-sentiment-${service}"
}

get_rule_name() {
    local env="$1"
    echo "${env}-sentiment-ingestion-schedule"
}

# ============================================================================
# IAM Policy helpers
# ============================================================================

get_deny_policy_arn() {
    local env="$1"
    local account_id
    account_id=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || die "Failed to get AWS account ID"
    echo "arn:aws:iam::${account_id}:policy/${env}-chaos-deny-dynamodb-write"
}

get_lambda_role_name() {
    local env="$1"
    local service="$2"
    echo "${env}-${service}-lambda-role"
}
