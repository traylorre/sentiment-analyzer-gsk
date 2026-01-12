#!/usr/bin/env bash
# secrets.sh - AWS Secrets Manager fetch and age encryption functions
# Feature: 1194-workspace-bootstrap
#
# Usage: source scripts/lib/secrets.sh
#
# Dependencies: scripts/lib/colors.sh must be sourced first

# Configuration
readonly SECRETS_CONFIG_DIR="${HOME}/.config/sentiment-analyzer"
readonly SECRETS_CACHE_FILE="${SECRETS_CONFIG_DIR}/secrets.cache.age"
readonly SECRETS_IDENTITY_FILE="${SECRETS_CONFIG_DIR}/age-identity.txt"
readonly SECRETS_METADATA_FILE="${SECRETS_CONFIG_DIR}/cache-metadata.json"
readonly SECRETS_TTL_DAYS=30

# Secret names to fetch from AWS Secrets Manager
readonly SECRETS_TO_FETCH=(
    "dev/sentiment-analyzer/dashboard-api-key"
    "dev/sentiment-analyzer/tiingo"
    "dev/sentiment-analyzer/finnhub"
    "dev/sentiment-analyzer/sendgrid"
    "dev/sentiment-analyzer/hcaptcha"
)

# Initialize secrets config directory
# Usage: init_secrets_dir
init_secrets_dir() {
    if [[ ! -d "${SECRETS_CONFIG_DIR}" ]]; then
        mkdir -p "${SECRETS_CONFIG_DIR}"
        chmod 700 "${SECRETS_CONFIG_DIR}"
        print_status "INFO" "Created secrets directory: ${SECRETS_CONFIG_DIR}"
    fi
}

# Generate age identity if not exists
# Usage: ensure_age_identity
ensure_age_identity() {
    init_secrets_dir

    if [[ -f "${SECRETS_IDENTITY_FILE}" ]]; then
        print_status "INFO" "Using existing age identity"
        return 0
    fi

    print_status "INFO" "Generating new age identity..."

    if ! age-keygen -o "${SECRETS_IDENTITY_FILE}" 2>/dev/null; then
        print_status "FAIL" "Failed to generate age identity" "Check age installation"
        return 1
    fi

    chmod 600 "${SECRETS_IDENTITY_FILE}"
    print_status "PASS" "Generated age identity: ${SECRETS_IDENTITY_FILE}"

    # Extract public key for display
    local public_key
    public_key=$(grep "^# public key:" "${SECRETS_IDENTITY_FILE}" | cut -d: -f2 | tr -d ' ')
    print_status "INFO" "Public key: ${public_key}"

    return 0
}

# Fetch a single secret from AWS Secrets Manager
# Usage: fetch_secret "dev/sentiment-analyzer/tiingo"
# Returns: JSON secret value on stdout
fetch_secret() {
    local secret_name="$1"

    # Disable trace to prevent secret leakage
    { set +x; } 2>/dev/null

    local secret_value
    if ! secret_value=$(aws secretsmanager get-secret-value \
        --secret-id "${secret_name}" \
        --query 'SecretString' \
        --output text 2>&1); then

        if echo "${secret_value}" | grep -q "ResourceNotFoundException"; then
            echo "ERROR: Secret not found: ${secret_name}" >&2
        elif echo "${secret_value}" | grep -q "AccessDeniedException"; then
            echo "ERROR: Access denied for secret: ${secret_name}" >&2
        else
            echo "ERROR: Failed to fetch secret: ${secret_name}" >&2
        fi
        return 1
    fi

    echo "${secret_value}"
}

# Fetch all secrets and return as JSON object
# Usage: fetch_all_secrets
# Returns: JSON object with all secrets
fetch_all_secrets() {
    local secrets_json="{}"
    local failed=0

    print_header "Fetching Secrets"

    for secret_name in "${SECRETS_TO_FETCH[@]}"; do
        local short_name
        short_name=$(basename "${secret_name}")

        print_status "INFO" "Fetching: ${secret_name}..."

        local secret_value
        if ! secret_value=$(fetch_secret "${secret_name}"); then
            print_status "FAIL" "Failed to fetch: ${short_name}"
            ((failed++))
            continue
        fi

        # Add to JSON object (handle both simple strings and JSON objects)
        if echo "${secret_value}" | jq -e . &>/dev/null; then
            # It's valid JSON - merge it
            secrets_json=$(echo "${secrets_json}" | jq --argjson val "${secret_value}" ". + {\"${short_name}\": \$val}")
        else
            # It's a plain string
            secrets_json=$(echo "${secrets_json}" | jq --arg val "${secret_value}" ". + {\"${short_name}\": \$val}")
        fi

        print_status "PASS" "Fetched: ${short_name}"
    done

    if [[ "${failed}" -gt 0 ]]; then
        print_status "WARN" "Failed to fetch ${failed} secret(s)"
        return 1
    fi

    echo "${secrets_json}"
}

# Encrypt secrets to cache file
# Usage: echo '{"key": "value"}' | encrypt_secrets_cache
encrypt_secrets_cache() {
    init_secrets_dir
    ensure_age_identity || return 1

    local temp_file
    temp_file=$(mktemp)
    trap "rm -f '${temp_file}'" RETURN

    # Read from stdin to temp file
    cat > "${temp_file}"

    # Encrypt with age
    if ! age -e -i "${SECRETS_IDENTITY_FILE}" -o "${SECRETS_CACHE_FILE}" "${temp_file}"; then
        print_status "FAIL" "Failed to encrypt secrets cache"
        return 1
    fi

    chmod 600 "${SECRETS_CACHE_FILE}"

    # Write metadata
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

    print_status "PASS" "Encrypted secrets cache: ${SECRETS_CACHE_FILE}"
    print_status "INFO" "Cache expires: ${expires_at}"

    return 0
}

# Decrypt secrets from cache file
# Usage: decrypt_secrets_cache
# Returns: Decrypted JSON on stdout
decrypt_secrets_cache() {
    if [[ ! -f "${SECRETS_CACHE_FILE}" ]]; then
        print_status "FAIL" "Secrets cache not found" "Run: ./scripts/bootstrap-workspace.sh"
        return 1
    fi

    if [[ ! -f "${SECRETS_IDENTITY_FILE}" ]]; then
        print_status "FAIL" "Age identity not found" "Run: ./scripts/bootstrap-workspace.sh"
        return 1
    fi

    # Disable trace to prevent secret leakage
    { set +x; } 2>/dev/null

    if ! age -d -i "${SECRETS_IDENTITY_FILE}" "${SECRETS_CACHE_FILE}"; then
        print_status "FAIL" "Failed to decrypt secrets cache" "Cache may be corrupted - run: ./scripts/refresh-secrets-cache.sh"
        return 1
    fi
}

# Check if cache is expired
# Returns: 0 if valid, 1 if expired or missing
is_cache_valid() {
    if [[ ! -f "${SECRETS_METADATA_FILE}" ]]; then
        return 1
    fi

    local expires_at now_epoch expires_epoch
    expires_at=$(jq -r '.expires_at' "${SECRETS_METADATA_FILE}" 2>/dev/null)

    if [[ -z "${expires_at}" || "${expires_at}" == "null" ]]; then
        return 1
    fi

    now_epoch=$(date +%s)
    expires_epoch=$(date -d "${expires_at}" +%s 2>/dev/null) || return 1

    if [[ "${now_epoch}" -ge "${expires_epoch}" ]]; then
        return 1
    fi

    return 0
}

# Get cache status
# Usage: get_cache_status
# Returns: "valid", "expired", or "missing"
get_cache_status() {
    if [[ ! -f "${SECRETS_CACHE_FILE}" ]]; then
        echo "missing"
        return
    fi

    if is_cache_valid; then
        echo "valid"
    else
        echo "expired"
    fi
}

# Get cache info for display
# Usage: print_cache_info
print_cache_info() {
    print_header "Secrets Cache Status"

    if [[ ! -f "${SECRETS_METADATA_FILE}" ]]; then
        print_status "WARN" "No cache metadata found"
        return 1
    fi

    local fetched_at expires_at status
    fetched_at=$(jq -r '.fetched_at' "${SECRETS_METADATA_FILE}")
    expires_at=$(jq -r '.expires_at' "${SECRETS_METADATA_FILE}")
    status=$(get_cache_status)

    case "${status}" in
        valid)
            print_status "PASS" "Cache status: valid"
            ;;
        expired)
            print_status "WARN" "Cache status: expired" "Run: ./scripts/refresh-secrets-cache.sh"
            ;;
        missing)
            print_status "FAIL" "Cache status: missing" "Run: ./scripts/bootstrap-workspace.sh"
            ;;
    esac

    print_status "INFO" "Fetched: ${fetched_at}"
    print_status "INFO" "Expires: ${expires_at}"
}

# Generate .env.local from cached secrets
# Usage: generate_env_local [output_file]
generate_env_local() {
    local output_file="${1:-.env.local}"
    local repo_root
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    output_file="${repo_root}/${output_file}"

    # Verify .env.local is gitignored
    if ! grep -q "^\.env\.local$" "${repo_root}/.gitignore" 2>/dev/null; then
        print_status "FAIL" ".env.local is not in .gitignore" "Add '.env.local' to .gitignore first"
        return 1
    fi

    print_header "Generating .env.local"

    # Get decrypted secrets
    local secrets_json
    if ! secrets_json=$(decrypt_secrets_cache); then
        return 1
    fi

    # Extract values with key normalization
    local dashboard_api_key tiingo_api_key finnhub_api_key sendgrid_api_key hcaptcha_secret hcaptcha_site

    # Dashboard API key (simple string)
    dashboard_api_key=$(echo "${secrets_json}" | jq -r '."dashboard-api-key" // empty')

    # Tiingo (may be JSON object or string)
    tiingo_api_key=$(echo "${secrets_json}" | jq -r '.tiingo | if type == "object" then .api_key else . end // empty')

    # Finnhub (may be JSON object or string)
    finnhub_api_key=$(echo "${secrets_json}" | jq -r '.finnhub | if type == "object" then .api_key else . end // empty')

    # SendGrid (may be JSON object or string)
    sendgrid_api_key=$(echo "${secrets_json}" | jq -r '.sendgrid | if type == "object" then .api_key else . end // empty')

    # hCaptcha (JSON object with secret_key and site_key)
    hcaptcha_secret=$(echo "${secrets_json}" | jq -r '.hcaptcha.secret_key // empty')
    hcaptcha_site=$(echo "${secrets_json}" | jq -r '.hcaptcha.site_key // empty')

    # Get metadata
    local fetched_at
    fetched_at=$(jq -r '.fetched_at' "${SECRETS_METADATA_FILE}" 2>/dev/null || echo "unknown")

    # Write .env.local
    cat > "${output_file}" <<EOF
# .env.local - Generated by bootstrap-workspace.sh
# DO NOT COMMIT - This file is gitignored
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Secrets fetched: ${fetched_at}

# AWS Configuration
AWS_REGION=us-east-1

# API Keys from AWS Secrets Manager (dev/sentiment-analyzer/*)
DASHBOARD_API_KEY=${dashboard_api_key}
TIINGO_API_KEY=${tiingo_api_key}
FINNHUB_API_KEY=${finnhub_api_key}
SENDGRID_API_KEY=${sendgrid_api_key}
HCAPTCHA_SECRET_KEY=${hcaptcha_secret}
HCAPTCHA_SITE_KEY=${hcaptcha_site}

# Test Configuration
MAGIC_LINK_SECRET=local-dev-secret-at-least-32-characters-long

# Cache metadata
SECRETS_CACHE_PATH=${SECRETS_CACHE_FILE}
SECRETS_FETCHED_AT=${fetched_at}
EOF

    chmod 600 "${output_file}"
    print_status "PASS" "Generated: ${output_file}"

    return 0
}
