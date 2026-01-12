#!/usr/bin/env bash
# prereqs.sh - Prerequisite checking functions for bootstrap scripts
# Feature: 1194-workspace-bootstrap
#
# Usage: source scripts/lib/prereqs.sh
#
# Dependencies: scripts/lib/colors.sh must be sourced first

# Semantic version comparison
# Returns 0 if version >= required, 1 otherwise
# Usage: version_gte "3.12.0" "3.11.0"  # returns 0 (3.12.0 >= 3.11.0)
version_gte() {
    local version="$1"
    local required="$2"

    # Remove leading 'v' if present
    version="${version#v}"
    required="${required#v}"

    # Compare using sort -V
    local lowest
    lowest=$(printf '%s\n%s' "${version}" "${required}" | sort -V | head -n1)

    [[ "${lowest}" == "${required}" ]]
}

# Check if a command exists
# Usage: command_exists python
command_exists() {
    command -v "$1" &>/dev/null
}

# Get version of a tool
# Usage: get_version python  # returns "3.13.0"
get_version() {
    local tool="$1"

    case "${tool}" in
        python|python3)
            python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
            ;;
        aws)
            aws --version 2>/dev/null | grep -oE 'aws-cli/[0-9]+\.[0-9]+\.[0-9]+' | cut -d/ -f2
            ;;
        terraform)
            terraform --version 2>/dev/null | head -n1 | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d 'v'
            ;;
        node|nodejs)
            node --version 2>/dev/null | tr -d 'v'
            ;;
        git)
            git --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
            ;;
        jq)
            jq --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+'
            ;;
        age)
            age --version 2>/dev/null | grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' | tr -d 'v'
            ;;
        docker)
            docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
            ;;
        pre-commit)
            pre-commit --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Check a prerequisite tool
# Usage: check_prereq "python" "3.12.0" "pyenv install 3.13.0"
# Returns: 0 if OK, 1 if missing/old version
check_prereq() {
    local tool="$1"
    local min_version="$2"
    local install_hint="${3:-}"

    if ! command_exists "${tool}"; then
        print_status "FAIL" "${tool} not installed" "${install_hint}"
        return 1
    fi

    local current_version
    current_version=$(get_version "${tool}")

    if [[ -z "${current_version}" ]]; then
        print_status "WARN" "${tool} installed but version unknown"
        return 0
    fi

    if version_gte "${current_version}" "${min_version}"; then
        print_status "PASS" "${tool} ${current_version} (>= ${min_version})"
        return 0
    else
        print_status "FAIL" "${tool} ${current_version} (need >= ${min_version})" "${install_hint}"
        return 1
    fi
}

# Check optional tool (warn but don't fail)
# Usage: check_optional "docker" "Install with: sudo apt install docker.io"
check_optional() {
    local tool="$1"
    local install_hint="${2:-}"

    if ! command_exists "${tool}"; then
        print_status "WARN" "${tool} not installed (optional)" "${install_hint}"
        return 1
    fi

    local current_version
    current_version=$(get_version "${tool}")
    print_status "PASS" "${tool} ${current_version:-installed}"
    return 0
}

# Check all required prerequisites
# Returns: 0 if all pass, 1 if any fail
check_required_prereqs() {
    local failed=0

    print_header "Required Prerequisites"

    check_prereq "python3" "3.12.0" "pyenv install 3.13.0 && pyenv global 3.13.0" || ((failed++))
    check_prereq "aws" "2.0.0" "curl 'https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip' -o awscliv2.zip && unzip awscliv2.zip && sudo ./aws/install" || ((failed++))
    check_prereq "git" "2.30.0" "sudo apt install git" || ((failed++))
    check_prereq "jq" "1.6" "sudo apt install jq" || ((failed++))
    check_prereq "age" "1.0.0" "sudo apt install age" || ((failed++))

    return "${failed}"
}

# Check optional prerequisites
check_optional_prereqs() {
    print_header "Optional Tools"

    check_optional "terraform" "curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add - && sudo apt install terraform"
    check_optional "node" "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs"
    check_optional "docker" "sudo apt install docker.io && sudo usermod -aG docker \$USER"
    check_optional "pre-commit" "pip install pre-commit"
}

# Check AWS credentials
# Returns: 0 if valid, 1 if invalid/missing
check_aws_credentials() {
    print_header "AWS Credentials"

    if ! command_exists aws; then
        print_status "FAIL" "AWS CLI not installed" "Install AWS CLI v2 first"
        return 1
    fi

    # Try to get caller identity
    local caller_identity
    if ! caller_identity=$(aws sts get-caller-identity 2>&1); then
        if echo "${caller_identity}" | grep -q "expired"; then
            print_status "FAIL" "AWS credentials expired" "Run: aws sso login"
        elif echo "${caller_identity}" | grep -q "Unable to locate credentials"; then
            print_status "FAIL" "AWS credentials not configured" "Run: aws configure"
        else
            print_status "FAIL" "AWS credentials invalid" "Check your AWS configuration"
        fi
        return 1
    fi

    local account_id arn
    account_id=$(echo "${caller_identity}" | jq -r '.Account')
    arn=$(echo "${caller_identity}" | jq -r '.Arn')

    print_status "PASS" "AWS account: ${account_id}"
    print_status "INFO" "Identity: ${arn}"

    return 0
}

# Check Secrets Manager access
# Returns: 0 if can list secrets, 1 otherwise
check_secrets_access() {
    local secret_prefix="${1:-dev/sentiment-analyzer}"

    if ! aws secretsmanager list-secrets --filters Key=name,Values="${secret_prefix}" --max-results 1 &>/dev/null; then
        print_status "FAIL" "Cannot access Secrets Manager" "Check IAM permissions for secretsmanager:ListSecrets"
        return 1
    fi

    print_status "PASS" "Secrets Manager access verified"
    return 0
}
