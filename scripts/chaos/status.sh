#!/usr/bin/env bash
# Chaos Status Script
# ===================
# Display the current chaos state for an environment.
#
# Usage:
#   scripts/chaos/status.sh <environment>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "${SCRIPT_DIR}/lib/common.sh"

# ============================================================================
# Argument parsing
# ============================================================================

[[ $# -lt 1 ]] && { echo "Usage: $0 <environment>"; exit 1; }
ENVIRONMENT="$1"

# ============================================================================
# Display status
# ============================================================================

echo "================================"
echo "Chaos Status: $ENVIRONMENT"
echo "================================"
echo ""

# Kill switch state
KILL_SWITCH=$(aws ssm get-parameter \
    --name "/chaos/${ENVIRONMENT}/kill-switch" \
    --query "Parameter.Value" \
    --output text 2>/dev/null || echo "disarmed (not configured)")

echo "Kill Switch: $KILL_SWITCH"
echo ""

# Active snapshots (indicates active chaos scenarios)
SNAPSHOTS=$(list_snapshots "$ENVIRONMENT")
SNAPSHOT_COUNT=$(echo "$SNAPSHOTS" | python3 -c "import json,sys; data=json.load(sys.stdin); print(len(data))")

if [[ "$SNAPSHOT_COUNT" == "0" ]]; then
    echo "Active Scenarios: none"
else
    echo "Active Scenarios:"
    echo "$SNAPSHOTS" | python3 -c "
import json, sys
snapshots = json.load(sys.stdin)
for s in snapshots:
    name = s['Name']
    parts = name.split('/')
    scenario = parts[4] if len(parts) >= 5 else 'unknown'
    # Parse snapshot to get timestamp
    try:
        value = json.loads(s['Value'])
        ts = value.get('SnapshotTimestamp', 'unknown')
    except (json.JSONDecodeError, KeyError):
        ts = 'unknown'
    print(f'  {scenario:<25} started: {ts}')
"
fi

echo ""

# Recent experiments from DynamoDB
echo "Recent Experiments (last 5):"
TABLE_NAME="${ENVIRONMENT}-chaos-experiments"
aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --limit 5 \
    --query "Items[].{ID:experiment_id.S,Scenario:scenario_type.S,Status:status.S,Created:created_at.S}" \
    --output table 2>/dev/null || echo "  (table not accessible or empty)"

echo ""
echo "================================"
