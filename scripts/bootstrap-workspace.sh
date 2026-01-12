#!/usr/bin/env bash
# bootstrap-workspace.sh - Main workspace bootstrap script
# Feature: 1194-workspace-bootstrap
#
# Usage:
#   ./scripts/bootstrap-workspace.sh              # Full bootstrap
#   ./scripts/bootstrap-workspace.sh --skip-hooks # Skip git hooks
#   ./scripts/bootstrap-workspace.sh --force      # Overwrite existing cache
#   ./scripts/bootstrap-workspace.sh --env preprod # Use preprod secrets
#
# This script:
# 1. Checks all prerequisites (Python, AWS CLI, age, etc.)
# 2. Validates AWS credentials
# 3. Fetches secrets from AWS Secrets Manager
# 4. Encrypts and caches secrets locally using age
# 5. Generates .env.local for local development
# 6. Optionally installs git hooks

set -euo pipefail

# Get script directory for sourcing libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source libraries
source "${SCRIPT_DIR}/lib/colors.sh"
source "${SCRIPT_DIR}/lib/prereqs.sh"
source "${SCRIPT_DIR}/lib/secrets.sh"

# Configuration
SKIP_HOOKS=false
FORCE_REFRESH=false
ENVIRONMENT="dev"

# Track overall status
BOOTSTRAP_FAILED=false

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-hooks)
                SKIP_HOOKS=true
                shift
                ;;
            --force)
                FORCE_REFRESH=true
                shift
                ;;
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Bootstrap a new development workspace with secrets caching.

Options:
    --skip-hooks    Skip git hooks installation
    --force         Overwrite existing secrets cache
    --env ENV       Use specified environment (default: dev)
    -h, --help      Show this help message

Examples:
    ./scripts/bootstrap-workspace.sh
    ./scripts/bootstrap-workspace.sh --skip-hooks
    ./scripts/bootstrap-workspace.sh --force --env preprod
EOF
}

# Main banner
show_banner() {
    echo ""
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║           Sentiment Analyzer - Workspace Bootstrap          ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  ${DIM}Environment: ${ENVIRONMENT}${NC}"
    echo -e "  ${DIM}Repo root: ${REPO_ROOT}${NC}"
    echo ""
}

# Check prerequisites
check_prerequisites() {
    local failed=0

    if ! check_required_prereqs; then
        BOOTSTRAP_FAILED=true
        ((failed++))
    fi

    check_optional_prereqs

    return "${failed}"
}

# Check AWS credentials and access
check_aws() {
    if ! check_aws_credentials; then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    if ! check_secrets_access "${ENVIRONMENT}/sentiment-analyzer"; then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    return 0
}

# Check if we should skip secrets fetch
should_skip_secrets() {
    if [[ "${FORCE_REFRESH}" == true ]]; then
        print_status "INFO" "Force refresh requested - will fetch new secrets"
        return 1
    fi

    local status
    status=$(get_cache_status)

    case "${status}" in
        valid)
            print_status "INFO" "Secrets cache is valid"
            return 0
            ;;
        expired)
            print_status "WARN" "Secrets cache expired - will refresh"
            return 1
            ;;
        missing)
            print_status "INFO" "No secrets cache found - will fetch"
            return 1
            ;;
    esac
}

# Fetch and cache secrets
fetch_and_cache_secrets() {
    print_header "Secrets Management"

    if should_skip_secrets; then
        print_status "INFO" "Using existing secrets cache"
        return 0
    fi

    # Ensure age identity exists
    if ! ensure_age_identity; then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    # Fetch all secrets
    local secrets_json
    if ! secrets_json=$(fetch_all_secrets); then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    # Encrypt and cache
    if ! echo "${secrets_json}" | encrypt_secrets_cache; then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    return 0
}

# Generate environment file
generate_environment() {
    if ! generate_env_local; then
        BOOTSTRAP_FAILED=true
        return 1
    fi

    return 0
}

# Setup git hooks
setup_git_hooks() {
    if [[ "${SKIP_HOOKS}" == true ]]; then
        print_header "Git Hooks (skipped)"
        print_status "INFO" "Skipped git hooks installation (--skip-hooks)"
        return 0
    fi

    print_header "Git Hooks"

    # Check if pre-commit is installed
    if ! command_exists pre-commit; then
        print_status "WARN" "pre-commit not installed" "pip install pre-commit"
        return 0
    fi

    # Check if .pre-commit-config.yaml exists
    if [[ ! -f "${REPO_ROOT}/.pre-commit-config.yaml" ]]; then
        print_status "WARN" "No .pre-commit-config.yaml found"
        return 0
    fi

    # Install hooks
    cd "${REPO_ROOT}"
    if pre-commit install &>/dev/null; then
        print_status "PASS" "Installed pre-commit hooks"
    else
        print_status "WARN" "Failed to install pre-commit hooks"
    fi

    return 0
}

# Setup Python virtual environment
setup_python_venv() {
    print_header "Python Environment"

    cd "${REPO_ROOT}"

    # Check if venv exists
    if [[ -d ".venv" ]]; then
        print_status "PASS" "Virtual environment exists: .venv/"
    else
        print_status "INFO" "Creating virtual environment..."
        if python3 -m venv .venv; then
            print_status "PASS" "Created virtual environment: .venv/"
        else
            print_status "FAIL" "Failed to create virtual environment"
            BOOTSTRAP_FAILED=true
            return 1
        fi
    fi

    # Install dependencies
    print_status "INFO" "Installing dependencies..."
    if source .venv/bin/activate && pip install -q -r requirements-dev.txt 2>/dev/null; then
        print_status "PASS" "Dependencies installed"
    else
        # Try without -dev
        if pip install -q -r requirements.txt 2>/dev/null; then
            print_status "PASS" "Dependencies installed (requirements.txt)"
        else
            print_status "WARN" "Could not install dependencies" "Run: pip install -r requirements-dev.txt"
        fi
    fi

    return 0
}

# Final summary
show_summary() {
    if [[ "${BOOTSTRAP_FAILED}" == true ]]; then
        print_error "Bootstrap failed - see errors above"
        echo ""
        echo -e "${DIM}Fix the errors above and run bootstrap again.${NC}"
        echo ""
        return 1
    fi

    print_success "Bootstrap complete!"
    echo ""
    echo -e "  ${BOLD}Next steps:${NC}"
    echo -e "    1. Activate environment: ${CYAN}source .venv/bin/activate${NC}"
    echo -e "    2. Load secrets:         ${CYAN}source .env.local${NC}"
    echo -e "    3. Run tests:            ${CYAN}pytest${NC}"
    echo ""
    echo -e "  ${BOLD}Verify your setup:${NC}"
    echo -e "    ${CYAN}./scripts/verify-dev-environment.sh${NC}"
    echo ""
    echo -e "  ${DIM}Secrets cache: ~/.config/sentiment-analyzer/${NC}"
    echo -e "  ${DIM}Cache expires in ${SECRETS_TTL_DAYS} days${NC}"
    echo ""

    return 0
}

# Cleanup on failure (atomic operation handling)
cleanup_on_failure() {
    local exit_code=$?

    if [[ "${exit_code}" -ne 0 ]]; then
        print_error "Bootstrap interrupted - cleaning up partial state"

        # Remove partially created files
        if [[ -f "${SECRETS_CACHE_FILE}.tmp" ]]; then
            rm -f "${SECRETS_CACHE_FILE}.tmp"
        fi

        # Don't remove .env.local if it existed before
    fi

    exit "${exit_code}"
}

# Main execution
main() {
    parse_args "$@"

    # Setup cleanup trap for atomic operations
    trap cleanup_on_failure EXIT

    show_banner

    # Phase 1: Prerequisites
    check_prerequisites

    # Phase 2: AWS validation
    check_aws

    # Phase 3: Secrets management
    fetch_and_cache_secrets

    # Phase 4: Environment generation
    generate_environment

    # Phase 5: Git hooks
    setup_git_hooks

    # Phase 6: Python setup
    setup_python_venv

    # Summary
    show_summary
}

# Run main
main "$@"
