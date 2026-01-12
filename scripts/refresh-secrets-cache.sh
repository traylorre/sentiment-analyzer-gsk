#!/usr/bin/env bash
# refresh-secrets-cache.sh - Force-refresh secrets from AWS Secrets Manager
# Feature: 1194-workspace-bootstrap
#
# Usage:
#   ./scripts/refresh-secrets-cache.sh           # Refresh and regenerate .env.local
#   ./scripts/refresh-secrets-cache.sh --no-env  # Refresh cache only
#
# This script:
# 1. Validates AWS credentials
# 2. Fetches fresh secrets from AWS Secrets Manager
# 3. Atomically replaces the encrypted cache
# 4. Regenerates .env.local (unless --no-env)

set -euo pipefail

# Get script directory for sourcing libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source libraries
source "${SCRIPT_DIR}/lib/colors.sh"
source "${SCRIPT_DIR}/lib/prereqs.sh"
source "${SCRIPT_DIR}/lib/secrets.sh"

# Configuration
REGENERATE_ENV=true

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --no-env)
                REGENERATE_ENV=false
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Force-refresh secrets from AWS Secrets Manager.

Options:
    --no-env    Don't regenerate .env.local after refresh
    -h, --help  Show this help message

Examples:
    ./scripts/refresh-secrets-cache.sh
    ./scripts/refresh-secrets-cache.sh --no-env
EOF
}

# Show banner
show_banner() {
    echo ""
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║            Sentiment Analyzer - Secrets Refresh             ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Main
main() {
    parse_args "$@"

    show_banner

    # Show current cache status
    print_cache_info

    # Validate AWS credentials
    if ! check_aws_credentials; then
        print_error "Cannot refresh - AWS credentials invalid"
        exit 1
    fi

    # Ensure age identity exists
    if ! ensure_age_identity; then
        print_error "Cannot refresh - age identity setup failed"
        exit 1
    fi

    # Backup existing cache
    if [[ -f "${SECRETS_CACHE_FILE}" ]]; then
        cp "${SECRETS_CACHE_FILE}" "${SECRETS_CACHE_FILE}.bak"
        print_status "INFO" "Backed up existing cache"
    fi

    # Fetch all secrets
    local secrets_json
    if ! secrets_json=$(fetch_all_secrets); then
        print_error "Failed to fetch secrets"
        # Restore backup
        if [[ -f "${SECRETS_CACHE_FILE}.bak" ]]; then
            mv "${SECRETS_CACHE_FILE}.bak" "${SECRETS_CACHE_FILE}"
            print_status "INFO" "Restored previous cache"
        fi
        exit 1
    fi

    # Encrypt and cache (atomic operation)
    local temp_cache
    temp_cache="${SECRETS_CACHE_FILE}.new"

    # Write to temp file first
    if ! echo "${secrets_json}" | age -e -i "${SECRETS_IDENTITY_FILE}" -o "${temp_cache}"; then
        print_error "Failed to encrypt secrets"
        rm -f "${temp_cache}"
        exit 1
    fi

    # Atomic replacement
    mv "${temp_cache}" "${SECRETS_CACHE_FILE}"
    chmod 600 "${SECRETS_CACHE_FILE}"

    # Update metadata
    local now expires_at
    now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    expires_at=$(date -u -d "+${SECRETS_TTL_DAYS} days" +"%Y-%m-%dT%H:%M:%SZ")

    cat > "${SECRETS_METADATA_FILE}" <<EOF
{
  "fetched_at": "${now}",
  "ttl_days": ${SECRETS_TTL_DAYS},
  "expires_at": "${expires_at}",
  "secrets_version": "1.0",
  "environment": "dev"
}
EOF

    print_success "Secrets cache refreshed!"
    print_status "INFO" "Expires: ${expires_at}"

    # Remove backup
    rm -f "${SECRETS_CACHE_FILE}.bak"

    # Regenerate .env.local
    if [[ "${REGENERATE_ENV}" == true ]]; then
        cd "${REPO_ROOT}"
        if ! generate_env_local; then
            print_warning "Failed to regenerate .env.local - cache is updated but env file is stale"
            exit 1
        fi
    fi

    echo ""
    echo -e "  ${BOLD}Next steps:${NC}"
    echo -e "    ${CYAN}source .env.local${NC}"
    echo ""
}

main "$@"
