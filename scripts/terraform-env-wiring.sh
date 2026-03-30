#!/usr/bin/env bash
# Feature 1290: Lambda Environment Variable Wiring Script
#
# Reads current Lambda env vars, merges a single key-value pair, writes back,
# and verifies the update succeeded. Used by terraform_data provisioners to
# populate cross-module env var values after all modules are created.
#
# Usage: terraform-env-wiring.sh <function-name> <env-var-key> <env-var-value>
#
# Exit codes:
#   0 — success, value verified
#   1 — AWS CLI error (read or write failed)
#   2 — verification failed (value mismatch after write)
#
# Security:
#   - No temp files created (uses pipes and process substitution)
#   - Command output suppressed (env vars contain secret ARN values)
#   - See docs/terraform-patterns.md for pattern documentation

set -euo pipefail

FUNCTION_NAME="${1:?Usage: terraform-env-wiring.sh <function-name> <env-var-key> <env-var-value>}"
ENV_VAR_KEY="${2:?Missing env var key}"
ENV_VAR_VALUE="${3:-}"  # Value can be empty (e.g., when chaos is disabled)

# Step 1: Read current environment variables
# Suppress output to prevent logging secret values
CURRENT_ENV=$(aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --query 'Environment.Variables' \
  --output json 2>/dev/null) || {
  echo "ERROR: Failed to read env vars for $FUNCTION_NAME" >&2
  exit 1
}

# Handle case where Lambda has no env vars yet
if [ "$CURRENT_ENV" = "null" ] || [ -z "$CURRENT_ENV" ]; then
  CURRENT_ENV="{}"
fi

# Step 2: Merge the key-value pair using jq
# This preserves ALL existing env vars and adds/updates the specified key
MERGED_ENV=$(echo "$CURRENT_ENV" | jq --arg key "$ENV_VAR_KEY" --arg val "$ENV_VAR_VALUE" \
  '. + {($key): $val}') || {
  echo "ERROR: Failed to merge env var $ENV_VAR_KEY for $FUNCTION_NAME" >&2
  exit 1
}

# Step 3: Write back the merged environment
# Output suppressed — contains all env vars including secrets
aws lambda update-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --environment "Variables=$MERGED_ENV" \
  --output json > /dev/null 2>&1 || {
  echo "ERROR: Failed to update env vars for $FUNCTION_NAME" >&2
  exit 1
}

# Step 4: Wait for update to complete (atomic but async)
aws lambda wait function-updated \
  --function-name "$FUNCTION_NAME" 2>/dev/null || {
  echo "WARNING: Timed out waiting for $FUNCTION_NAME update — verifying anyway" >&2
}

# Step 5: Read back and verify
ACTUAL_VALUE=$(aws lambda get-function-configuration \
  --function-name "$FUNCTION_NAME" \
  --query "Environment.Variables.\"$ENV_VAR_KEY\"" \
  --output text 2>/dev/null) || {
  echo "ERROR: Failed to verify env var $ENV_VAR_KEY for $FUNCTION_NAME" >&2
  exit 2
}

if [ "$ACTUAL_VALUE" != "$ENV_VAR_VALUE" ]; then
  echo "ERROR: Verification failed for $FUNCTION_NAME.$ENV_VAR_KEY — expected length ${#ENV_VAR_VALUE}, got length ${#ACTUAL_VALUE}" >&2
  exit 2
fi

echo "OK: $FUNCTION_NAME.$ENV_VAR_KEY wired successfully"
