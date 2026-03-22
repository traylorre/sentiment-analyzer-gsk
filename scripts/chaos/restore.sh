#!/usr/bin/env bash
# Chaos Restore Script
# ====================
# Restore all chaos-injected configurations from SSM snapshots.
#
# Usage:
#   scripts/chaos/restore.sh <environment> [--scenario <name>]
#
# Without --scenario: restores ALL active chaos scenarios.
# With --scenario: restores only the specified scenario.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ============================================================================
# Argument parsing
# ============================================================================

ENVIRONMENT=""
SCENARIO=""

usage() {
    echo "Usage: $0 <environment> [--scenario <name>]"
    echo ""
    echo "Options:"
    echo "  --scenario <name>  Restore only the specified scenario"
    exit 1
}

[[ $# -lt 1 ]] && usage
ENVIRONMENT="$1"
shift

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scenario) SCENARIO="$2"; shift 2 ;;
        *) die "Unknown option: $1" ;;
    esac
done

# ============================================================================
# Restore functions (one per scenario type)
# ============================================================================

restore_ingestion_failure() {
    local snapshot_json="$1"
    local func_name
    func_name=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['FunctionName'])")
    local concurrency
    concurrency=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin).get('ReservedConcurrency','NONE'))")

    if [[ "$concurrency" == "NONE" ]]; then
        # No reserved concurrency was set before -- delete the concurrency setting
        aws lambda delete-function-concurrency \
            --function-name "$func_name" \
            --no-cli-pager 2>/dev/null || true
        info "Removed reserved concurrency from $func_name (restored to unreserved)"
    else
        aws lambda put-function-concurrency \
            --function-name "$func_name" \
            --reserved-concurrent-executions "$concurrency" \
            --no-cli-pager >/dev/null
        info "Restored concurrency to $concurrency on $func_name"
    fi
}

restore_dynamodb_throttle() {
    local policy_arn
    policy_arn=$(get_deny_policy_arn "$ENVIRONMENT")
    local roles=("$(get_lambda_role_name "$ENVIRONMENT" "ingestion")" "$(get_lambda_role_name "$ENVIRONMENT" "analysis")")

    for role in "${roles[@]}"; do
        aws iam detach-role-policy \
            --role-name "$role" \
            --policy-arn "$policy_arn" \
            --no-cli-pager 2>/dev/null || warn "Policy may not be attached to $role"
        info "Detached deny-write policy from $role"
    done
}

restore_cold_start() {
    local snapshot_json="$1"
    local func_name
    func_name=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['FunctionName'])")
    local memory
    memory=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['MemorySize'])")

    aws lambda update-function-configuration \
        --function-name "$func_name" \
        --memory-size "$memory" \
        --no-cli-pager >/dev/null

    info "Restored memory to ${memory}MB on $func_name"
}

restore_trigger_failure() {
    local rule_name
    rule_name=$(get_rule_name "$ENVIRONMENT")

    aws events enable-rule \
        --name "$rule_name" \
        --no-cli-pager >/dev/null

    info "Re-enabled EventBridge rule $rule_name"
}

restore_api_timeout() {
    local snapshot_json="$1"
    local func_name
    func_name=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['FunctionName'])")
    local timeout
    timeout=$(echo "$snapshot_json" | python3 -c "import json,sys; print(json.load(sys.stdin)['Timeout'])")

    aws lambda update-function-configuration \
        --function-name "$func_name" \
        --timeout "$timeout" \
        --no-cli-pager >/dev/null

    info "Restored timeout to ${timeout}s on $func_name"
}

# ============================================================================
# Main restore logic
# ============================================================================

restore_scenario() {
    local scenario_name="$1"
    local snapshot_json

    snapshot_json=$(get_snapshot "$ENVIRONMENT" "$scenario_name")
    if [[ -z "$snapshot_json" ]]; then
        warn "No snapshot found for $scenario_name -- skipping"
        return
    fi

    info "Restoring scenario: $scenario_name"

    case "$scenario_name" in
        ingestion-failure) restore_ingestion_failure "$snapshot_json" ;;
        dynamodb-throttle) restore_dynamodb_throttle "$snapshot_json" ;;
        cold-start)        restore_cold_start "$snapshot_json" ;;
        trigger-failure)   restore_trigger_failure "$snapshot_json" ;;
        api-timeout)       restore_api_timeout "$snapshot_json" ;;
        *) warn "Unknown scenario: $scenario_name -- skipping" ;;
    esac

    # Delete snapshot after successful restore
    delete_snapshot "$ENVIRONMENT" "$scenario_name"
    info "Snapshot deleted for $scenario_name"

    # Log restore to audit table
    log_experiment "$ENVIRONMENT" "$scenario_name" "stopped" "restored_from_snapshot" >/dev/null
}

info "Restoring chaos configurations for environment: $ENVIRONMENT"

if [[ -n "$SCENARIO" ]]; then
    # Restore specific scenario
    restore_scenario "$SCENARIO"
else
    # Restore all scenarios by listing SSM snapshots
    SNAPSHOTS=$(list_snapshots "$ENVIRONMENT")
    SNAPSHOT_COUNT=$(echo "$SNAPSHOTS" | python3 -c "import json,sys; data=json.load(sys.stdin); print(len(data))")

    if [[ "$SNAPSHOT_COUNT" == "0" ]]; then
        info "No active chaos scenarios found -- nothing to restore"
    else
        info "Found $SNAPSHOT_COUNT active scenario(s) to restore"

        # Extract scenario names from snapshot parameter names
        echo "$SNAPSHOTS" | python3 -c "
import json, sys
snapshots = json.load(sys.stdin)
for s in snapshots:
    name = s['Name']
    # /chaos/{env}/snapshot/{scenario} -> scenario
    parts = name.split('/')
    if len(parts) >= 5:
        print(parts[4])
" | while read -r scenario_name; do
            restore_scenario "$scenario_name"
        done
    fi
fi

# Set kill switch to disarmed
set_kill_switch "$ENVIRONMENT" "disarmed"
info "Kill switch set to disarmed"

info "Restore complete for environment: $ENVIRONMENT"
