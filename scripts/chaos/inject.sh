#!/usr/bin/env bash
# Chaos Injection Script
# ======================
# Inject faults by degrading infrastructure externally via AWS API calls.
# No application code changes needed -- Lambda handlers are unaware.
#
# Usage:
#   scripts/chaos/inject.sh <scenario> <environment> [options]
#
# Scenarios:
#   ingestion-failure   Set reserved concurrency to 0 on ingestion Lambda
#   dynamodb-throttle   Attach deny-write IAM policy to Lambda execution roles
#   cold-start          Set memory to 128MB on target Lambda (force cold starts)
#   trigger-failure     Disable EventBridge ingestion schedule rule
#   api-timeout         Set timeout to 1s on target Lambda
#
# Options:
#   --target <service>  Target Lambda service name (default: ingestion)
#   --dry-run           Show commands without executing
#   --duration <sec>    Auto-restore after N seconds (default: 300)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ============================================================================
# Argument parsing
# ============================================================================

SCENARIO=""
ENVIRONMENT=""
TARGET="ingestion"
DRY_RUN=false
DURATION=300

usage() {
    echo "Usage: $0 <scenario> <environment> [options]"
    echo ""
    echo "Scenarios:"
    echo "  ingestion-failure   Set reserved concurrency to 0"
    echo "  dynamodb-throttle   Attach deny-write IAM policy"
    echo "  cold-start          Set memory to 128MB"
    echo "  trigger-failure     Disable EventBridge rule"
    echo "  api-timeout         Set timeout to 1s"
    echo ""
    echo "Options:"
    echo "  --target <service>  Lambda service (default: ingestion)"
    echo "  --dry-run           Show commands without executing"
    echo "  --duration <sec>    Auto-restore after N seconds (default: 300)"
    echo ""
    echo "NOTE: Production chaos is NOT supported via this script."
    echo "      Production chaos requires a separate approval workflow."
    exit 1
}

# Parse positional args
[[ $# -lt 2 ]] && usage
SCENARIO="$1"
ENVIRONMENT="$2"
shift 2

# Parse optional flags
while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --duration) DURATION="$2"; shift 2 ;;
        *) die "Unknown option: $1" ;;
    esac
done

# Validate
# Production chaos is NEVER allowed via this script (Issue #28).
# Production chaos requires a separate approval workflow.
validate_environment "$ENVIRONMENT" "false"

VALID_SCENARIOS="ingestion-failure dynamodb-throttle cold-start trigger-failure api-timeout"
if ! echo "$VALID_SCENARIOS" | grep -qw "$SCENARIO"; then
    die "Invalid scenario: $SCENARIO. Must be one of: $VALID_SCENARIOS"
fi

# ============================================================================
# Pre-flight checks
# ============================================================================

info "Chaos injection: scenario=$SCENARIO env=$ENVIRONMENT target=$TARGET"

# Check gate state (Feature 1238: dual-mode observability)
GATE=$(check_kill_switch "$ENVIRONMENT")
info "Gate state: $GATE"

# Override dry_run if gate is disarmed
if [[ "$GATE" != "armed" && "$DRY_RUN" != "true" ]]; then
    DRY_RUN=true
    warn "Gate is $GATE -- running in DRY-RUN mode (no infrastructure changes)"
fi

# ============================================================================
# Scenario implementations
# ============================================================================

inject_ingestion_failure() {
    # Ingestion Lambda is EventBridge-triggered (scheduled), NOT Function URL.
    # Setting concurrency=0 works correctly for EventBridge-triggered Lambdas:
    # EventBridge will receive throttle errors and route to DLQ.
    local func_name
    func_name=$(get_function_name "$ENVIRONMENT" "ingestion")

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] aws lambda put-function-concurrency --function-name $func_name --reserved-concurrent-executions 0"
        return
    fi

    snapshot_config "$ENVIRONMENT" "ingestion-failure" "$func_name"

    aws lambda put-function-concurrency \
        --function-name "$func_name" \
        --reserved-concurrent-executions 0 \
        --no-cli-pager >/dev/null

    info "Set concurrency to 0 on $func_name -- all invocations will be throttled"
}

inject_dynamodb_throttle() {
    local policy_arn
    policy_arn=$(get_deny_policy_arn "$ENVIRONMENT")
    local roles=("$(get_lambda_role_name "$ENVIRONMENT" "ingestion")" "$(get_lambda_role_name "$ENVIRONMENT" "analysis")")

    if [[ "$DRY_RUN" == "true" ]]; then
        for role in "${roles[@]}"; do
            info "[DRY-RUN] aws iam attach-role-policy --role-name $role --policy-arn $policy_arn"
        done
        return
    fi

    # Snapshot: record which roles we're attaching to
    local func_name
    func_name=$(get_function_name "$ENVIRONMENT" "ingestion")
    snapshot_config "$ENVIRONMENT" "dynamodb-throttle" "$func_name"

    for role in "${roles[@]}"; do
        aws iam attach-role-policy \
            --role-name "$role" \
            --policy-arn "$policy_arn" \
            --no-cli-pager 2>/dev/null || warn "Policy may already be attached to $role"
        info "Attached deny-write policy to $role"
    done

    # IAM policy propagation takes up to 60 seconds. Sleep briefly to
    # increase probability of consistent behavior on first invocation.
    info "Waiting 5s for IAM policy propagation..."
    sleep 5

    info "DynamoDB writes will fail with AccessDenied for ingestion and analysis Lambdas"
}

inject_cold_start() {
    local func_name
    func_name=$(get_function_name "$ENVIRONMENT" "$TARGET")

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] aws lambda update-function-configuration --function-name $func_name --memory-size 128"
        return
    fi

    snapshot_config "$ENVIRONMENT" "cold-start" "$func_name"

    aws lambda update-function-configuration \
        --function-name "$func_name" \
        --memory-size 128 \
        --no-cli-pager >/dev/null

    info "Set memory to 128MB on $func_name -- cold starts will be slower"
}

inject_trigger_failure() {
    local rule_name
    rule_name=$(get_rule_name "$ENVIRONMENT")

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] aws events disable-rule --name $rule_name"
        return
    fi

    # Snapshot the ingestion Lambda config (rule name is derived)
    local func_name
    func_name=$(get_function_name "$ENVIRONMENT" "ingestion")
    snapshot_config "$ENVIRONMENT" "trigger-failure" "$func_name"

    aws events disable-rule \
        --name "$rule_name" \
        --no-cli-pager >/dev/null

    info "Disabled EventBridge rule $rule_name -- ingestion will stop triggering"
}

inject_api_timeout() {
    # NOTE: Timeout reduction only affects NEW invocations. In-flight requests
    # continue until their original timeout. For immediate effect, combine with
    # ingestion_failure (concurrency=0) to stop new invocations.
    local func_name
    func_name=$(get_function_name "$ENVIRONMENT" "$TARGET")

    if [[ "$DRY_RUN" == "true" ]]; then
        info "[DRY-RUN] aws lambda update-function-configuration --function-name $func_name --timeout 1"
        return
    fi

    snapshot_config "$ENVIRONMENT" "api-timeout" "$func_name"

    aws lambda update-function-configuration \
        --function-name "$func_name" \
        --timeout 1 \
        --no-cli-pager >/dev/null

    info "Set timeout to 1s on $func_name -- NEW invocations will timeout (in-flight unaffected)"
}

# ============================================================================
# Execute
# ============================================================================

# Set kill switch to armed (only if not dry-run)
if [[ "$DRY_RUN" != "true" ]]; then
    set_kill_switch "$ENVIRONMENT" "armed"
fi

# Route to scenario implementation
case "$SCENARIO" in
    ingestion-failure) inject_ingestion_failure ;;
    dynamodb-throttle) inject_dynamodb_throttle ;;
    cold-start)        inject_cold_start ;;
    trigger-failure)   inject_trigger_failure ;;
    api-timeout)       inject_api_timeout ;;
esac

# Log experiment to DynamoDB audit table
if [[ "$DRY_RUN" != "true" ]]; then
    EXPERIMENT_ID=$(log_experiment "$ENVIRONMENT" "$SCENARIO" "running" "target=$TARGET,duration=$DURATION,dry_run=false,gate=$GATE")
    info "Experiment logged: $EXPERIMENT_ID"
    info "Auto-restore in ${DURATION}s. Run 'scripts/chaos/restore.sh $ENVIRONMENT' to restore manually."
else
    EXPERIMENT_ID=$(log_experiment "$ENVIRONMENT" "$SCENARIO" "running" "target=$TARGET,duration=$DURATION,dry_run=true,gate=$GATE" 2>/dev/null || echo "dry-run-no-id")
    info "[DRY-RUN] Experiment logged (dry_run=true): $EXPERIMENT_ID"
fi

info "Chaos injection complete: $SCENARIO on $ENVIRONMENT (gate=$GATE, dry_run=$DRY_RUN)"
