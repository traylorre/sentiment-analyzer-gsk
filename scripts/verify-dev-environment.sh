#!/usr/bin/env bash
# verify-dev-environment.sh - Environment verification script
# Feature: 1194-workspace-bootstrap
#
# Usage:
#   ./scripts/verify-dev-environment.sh        # Full verification
#   ./scripts/verify-dev-environment.sh --json # JSON output for automation
#
# Checks:
# - Prerequisites (Python, AWS CLI, age, etc.)
# - AWS credentials validity
# - Secrets cache status
# - Git hooks status
# - Python venv status
# - .env.local presence

set -euo pipefail

# Get script directory for sourcing libraries
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Source libraries
source "${SCRIPT_DIR}/lib/colors.sh"
source "${SCRIPT_DIR}/lib/prereqs.sh"
source "${SCRIPT_DIR}/lib/secrets.sh"

# Configuration
JSON_OUTPUT=false
OVERALL_STATUS="PASS"

# Results for JSON output
declare -a RESULTS=()

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                JSON_OUTPUT=true
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

Verify development environment status.

Options:
    --json      Output results as JSON (for automation)
    -h, --help  Show this help message

Exit codes:
    0   All checks passed
    1   One or more checks failed
EOF
}

# Add result for JSON output
add_result() {
    local category="$1"
    local check="$2"
    local status="$3"
    local message="$4"
    local remediation="${5:-}"

    if [[ "${status}" == "FAIL" ]]; then
        OVERALL_STATUS="FAIL"
    fi

    RESULTS+=("{\"category\":\"${category}\",\"check\":\"${check}\",\"status\":\"${status}\",\"message\":\"${message}\",\"remediation\":\"${remediation}\"}")
}

# Show banner
show_banner() {
    if [[ "${JSON_OUTPUT}" == true ]]; then
        return
    fi

    echo ""
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║          Sentiment Analyzer - Environment Verification      ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Check prerequisites
verify_prerequisites() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "Prerequisites"
    fi

    local tools=(
        "python3:3.12.0:pyenv install 3.13.0 && pyenv global 3.13.0"
        "aws:2.0.0:curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o awscliv2.zip && unzip awscliv2.zip && sudo ./aws/install"
        "git:2.30.0:sudo apt install git"
        "jq:1.6:sudo apt install jq"
        "age:1.0.0:sudo apt install age"
    )

    for tool_spec in "${tools[@]}"; do
        IFS=':' read -r tool min_version install_hint <<< "${tool_spec}"

        if ! command_exists "${tool}"; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "${tool} not installed" "${install_hint}"
            fi
            add_result "prerequisites" "${tool}" "FAIL" "Not installed" "${install_hint}"
            continue
        fi

        local version
        version=$(get_version "${tool}")

        if [[ -z "${version}" ]]; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "WARN" "${tool} version unknown"
            fi
            add_result "prerequisites" "${tool}" "WARN" "Version unknown" ""
            continue
        fi

        if version_gte "${version}" "${min_version}"; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "PASS" "${tool} ${version}"
            fi
            add_result "prerequisites" "${tool}" "PASS" "${version}" ""
        else
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "${tool} ${version} (need >= ${min_version})" "${install_hint}"
            fi
            add_result "prerequisites" "${tool}" "FAIL" "${version} (need >= ${min_version})" "${install_hint}"
        fi
    done
}

# Check AWS credentials
verify_aws() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "AWS Credentials"
    fi

    if ! command_exists aws; then
        add_result "aws" "cli" "FAIL" "AWS CLI not installed" "Install AWS CLI v2"
        return
    fi

    local caller_identity
    if ! caller_identity=$(aws sts get-caller-identity 2>&1); then
        if echo "${caller_identity}" | grep -q "expired"; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "AWS credentials expired" "Run: aws sso login"
            fi
            add_result "aws" "credentials" "FAIL" "Credentials expired" "aws sso login"
        elif echo "${caller_identity}" | grep -q "Unable to locate credentials"; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "AWS credentials not configured" "Run: aws configure"
            fi
            add_result "aws" "credentials" "FAIL" "Not configured" "aws configure"
        else
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "AWS credentials invalid"
            fi
            add_result "aws" "credentials" "FAIL" "Invalid" "Check AWS configuration"
        fi
        return
    fi

    local account_id
    account_id=$(echo "${caller_identity}" | jq -r '.Account')

    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_status "PASS" "AWS account: ${account_id}"
    fi
    add_result "aws" "credentials" "PASS" "Account ${account_id}" ""
}

# Check secrets cache
verify_secrets_cache() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "Secrets Cache"
    fi

    local status
    status=$(get_cache_status)

    case "${status}" in
        valid)
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "PASS" "Secrets cache valid"
            fi
            add_result "secrets" "cache" "PASS" "Valid" ""
            ;;
        expired)
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "WARN" "Secrets cache expired" "./scripts/refresh-secrets-cache.sh"
            fi
            add_result "secrets" "cache" "WARN" "Expired" "./scripts/refresh-secrets-cache.sh"
            ;;
        missing)
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "FAIL" "No secrets cache found" "./scripts/bootstrap-workspace.sh"
            fi
            add_result "secrets" "cache" "FAIL" "Missing" "./scripts/bootstrap-workspace.sh"
            ;;
    esac

    # Check age identity
    if [[ -f "${SECRETS_IDENTITY_FILE}" ]]; then
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "PASS" "Age identity exists"
        fi
        add_result "secrets" "age_identity" "PASS" "Exists" ""
    else
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "FAIL" "Age identity missing" "./scripts/bootstrap-workspace.sh"
        fi
        add_result "secrets" "age_identity" "FAIL" "Missing" "./scripts/bootstrap-workspace.sh"
    fi
}

# Check .env.local
verify_env_local() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "Environment Files"
    fi

    cd "${REPO_ROOT}"

    if [[ -f ".env.local" ]]; then
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "PASS" ".env.local exists"
        fi
        add_result "environment" "env_local" "PASS" "Exists" ""

        # Check if it has the required keys
        local missing_keys=()
        for key in DASHBOARD_API_KEY TIINGO_API_KEY FINNHUB_API_KEY MAGIC_LINK_SECRET; do
            if ! grep -q "^${key}=" .env.local; then
                missing_keys+=("${key}")
            fi
        done

        if [[ ${#missing_keys[@]} -gt 0 ]]; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "WARN" "Missing keys: ${missing_keys[*]}" "./scripts/bootstrap-workspace.sh --force"
            fi
            add_result "environment" "env_keys" "WARN" "Missing: ${missing_keys[*]}" "./scripts/bootstrap-workspace.sh --force"
        else
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "PASS" "All required keys present"
            fi
            add_result "environment" "env_keys" "PASS" "All keys present" ""
        fi
    else
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "FAIL" ".env.local missing" "./scripts/bootstrap-workspace.sh"
        fi
        add_result "environment" "env_local" "FAIL" "Missing" "./scripts/bootstrap-workspace.sh"
    fi
}

# Check Python venv
verify_python_venv() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "Python Environment"
    fi

    cd "${REPO_ROOT}"

    if [[ -d ".venv" ]]; then
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "PASS" "Virtual environment exists"
        fi
        add_result "python" "venv" "PASS" "Exists" ""

        # Check if activated
        if [[ -n "${VIRTUAL_ENV:-}" ]] && [[ "${VIRTUAL_ENV}" == "${REPO_ROOT}/.venv" ]]; then
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "PASS" "Virtual environment activated"
            fi
            add_result "python" "venv_active" "PASS" "Activated" ""
        else
            if [[ "${JSON_OUTPUT}" != true ]]; then
                print_status "INFO" "Virtual environment not activated" "source .venv/bin/activate"
            fi
            add_result "python" "venv_active" "INFO" "Not activated" "source .venv/bin/activate"
        fi
    else
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "FAIL" "No virtual environment" "python3 -m venv .venv"
        fi
        add_result "python" "venv" "FAIL" "Missing" "python3 -m venv .venv"
    fi
}

# Check git hooks
verify_git_hooks() {
    if [[ "${JSON_OUTPUT}" != true ]]; then
        print_header "Git Hooks"
    fi

    cd "${REPO_ROOT}"

    if [[ -f ".git/hooks/pre-commit" ]]; then
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "PASS" "Pre-commit hook installed"
        fi
        add_result "git" "pre_commit_hook" "PASS" "Installed" ""
    else
        if [[ "${JSON_OUTPUT}" != true ]]; then
            print_status "WARN" "Pre-commit hook not installed" "pre-commit install"
        fi
        add_result "git" "pre_commit_hook" "WARN" "Not installed" "pre-commit install"
    fi
}

# Show summary
show_summary() {
    if [[ "${JSON_OUTPUT}" == true ]]; then
        # Output as JSON
        echo "{"
        echo "  \"status\": \"${OVERALL_STATUS}\","
        echo "  \"results\": ["
        local first=true
        for result in "${RESULTS[@]}"; do
            if [[ "${first}" == true ]]; then
                first=false
            else
                echo ","
            fi
            echo -n "    ${result}"
        done
        echo ""
        echo "  ]"
        echo "}"
        return
    fi

    echo ""
    echo -e "${BOLD}════════════════════════════════════════════════════════════${NC}"

    if [[ "${OVERALL_STATUS}" == "PASS" ]]; then
        print_success "All checks passed!"
        echo -e "  ${DIM}Your development environment is ready.${NC}"
    else
        print_error "Some checks failed"
        echo -e "  ${DIM}Review the failures above and run the suggested commands.${NC}"
    fi

    echo ""
}

# Main
main() {
    parse_args "$@"

    show_banner

    verify_prerequisites
    verify_aws
    verify_secrets_cache
    verify_env_local
    verify_python_venv
    verify_git_hooks

    show_summary

    if [[ "${OVERALL_STATUS}" == "FAIL" ]]; then
        exit 1
    fi
}

main "$@"
