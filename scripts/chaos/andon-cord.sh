#!/usr/bin/env bash
# Andon Cord -- Emergency Chaos Stop
# ====================================
# Immediately restores ALL chaos-injected configurations.
# Sets kill switch to "triggered" then restores everything.
#
# Usage:
#   scripts/chaos/andon-cord.sh <environment>
#
# This is the panic button. Pull it when things go wrong.

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
# Execute andon cord
# ============================================================================

warn "ANDON CORD PULLED for environment: $ENVIRONMENT"
warn "Setting kill switch to 'triggered' and restoring all configurations..."

# Set kill switch to triggered (prevents new injections)
set_kill_switch "$ENVIRONMENT" "triggered"

# Log the andon cord activation
log_experiment "$ENVIRONMENT" "andon_cord" "triggered" "manual_andon_cord_activation" >/dev/null

# Restore all scenarios
"${SCRIPT_DIR}/restore.sh" "$ENVIRONMENT"

info "Andon cord complete. All chaos configurations restored."
info "Kill switch is now 'disarmed'."
