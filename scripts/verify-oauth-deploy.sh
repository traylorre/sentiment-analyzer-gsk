#!/usr/bin/env bash
# Feature 1371: Verify OAuth deploy state for a given environment.
# Feature 1372: Adds --pre-apply mode for prod safety.
#
# Usage:
#   ./scripts/verify-oauth-deploy.sh <preprod|prod>             # post-apply
#   ./scripts/verify-oauth-deploy.sh <preprod|prod> --pre-apply # pre-apply
#
# Pre-apply: only checks AWS account ID matches the env (catches wrong-profile applies).
# Post-apply: checks Lambda env, Cognito IdPs, and /api/v2/auth/oauth/urls response.
#
# Exit 0 on all-pass, non-zero on any failure.

set -euo pipefail

# -------------------------------------------------------------------
# Args
# -------------------------------------------------------------------
ENV="${1:?usage: $0 <preprod|prod> [--pre-apply]}"
MODE="${2:-post-apply}"

case "$ENV" in
  preprod) EXPECTED_ACCOUNT="${EXPECTED_PREPROD_ACCOUNT:-218795110243}" ;;
  prod)    EXPECTED_ACCOUNT="${EXPECTED_PROD_ACCOUNT:-}" ;;
  *)       echo "ERROR: env must be 'preprod' or 'prod' (got '$ENV')"; exit 2 ;;
esac

if [[ -z "$EXPECTED_ACCOUNT" ]]; then
  echo "ERROR: expected account ID for '$ENV' is unset."
  echo "       Set EXPECTED_${ENV^^}_ACCOUNT in your env, or hardcode in this script."
  exit 2
fi

# -------------------------------------------------------------------
# AWS account guard (always runs)
# -------------------------------------------------------------------
ACTUAL_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
if [[ "$ACTUAL_ACCOUNT" != "$EXPECTED_ACCOUNT" ]]; then
  echo "FAIL: AWS account mismatch."
  echo "      Expected: $EXPECTED_ACCOUNT ($ENV)"
  echo "      Actual:   $ACTUAL_ACCOUNT"
  echo "      Run with the correct AWS_PROFILE for $ENV."
  exit 1
fi
echo "PASS: AWS account $ACTUAL_ACCOUNT matches expected $ENV account."

if [[ "$MODE" == "--pre-apply" ]]; then
  echo "PASS (pre-apply): account check only. Run again without --pre-apply after terraform apply."
  exit 0
fi

# -------------------------------------------------------------------
# Post-apply checks
# -------------------------------------------------------------------

# 1. Lambda env var
LAMBDA_NAME="${ENV}-dashboard"
ENABLED="$(aws lambda get-function-configuration \
  --function-name "$LAMBDA_NAME" \
  --query 'Environment.Variables.ENABLED_OAUTH_PROVIDERS' \
  --output text 2>/dev/null || echo "")"

if [[ -z "$ENABLED" || "$ENABLED" == "None" ]]; then
  echo "FAIL: Lambda $LAMBDA_NAME has empty ENABLED_OAUTH_PROVIDERS."
  echo "      Confirm Secrets Manager values are set, then re-run terraform apply."
  exit 1
fi
echo "PASS: Lambda env ENABLED_OAUTH_PROVIDERS=$ENABLED"

# 2. Cognito identity providers
USER_POOL_ID="$(aws cognito-idp list-user-pools --max-results 60 \
  --query "UserPools[?starts_with(Name, '${ENV}')].Id | [0]" \
  --output text)"

if [[ -z "$USER_POOL_ID" || "$USER_POOL_ID" == "None" ]]; then
  echo "FAIL: Could not find Cognito user pool starting with '$ENV'."
  exit 1
fi

IDPS="$(aws cognito-idp list-identity-providers \
  --user-pool-id "$USER_POOL_ID" \
  --query 'Providers[].ProviderName' \
  --output text)"

if [[ -z "$IDPS" ]]; then
  echo "FAIL: Cognito user pool $USER_POOL_ID has no identity providers."
  exit 1
fi
echo "PASS: Cognito IdPs configured: $IDPS"

# 3. Cross-check: every provider in the Lambda env should have a matching Cognito IdP
IFS=',' read -ra ENABLED_LIST <<< "$ENABLED"
for provider in "${ENABLED_LIST[@]}"; do
  case "$provider" in
    google) expected_idp="Google" ;;
    github) expected_idp="GitHub" ;;
    *) echo "WARN: unknown provider '$provider' in ENABLED_OAUTH_PROVIDERS"; continue ;;
  esac
  if ! grep -qw "$expected_idp" <<< "$IDPS"; then
    echo "FAIL: Lambda env says '$provider' enabled, but Cognito has no $expected_idp IdP."
    echo "      State drift between Lambda env and Cognito. Re-run terraform apply."
    exit 1
  fi
done
echo "PASS: Lambda env <-> Cognito IdP consistency verified."

# 4. /api/v2/auth/oauth/urls smoke test (requires API Gateway URL — discovered from Terraform output)
API_URL="${API_GATEWAY_URL:-}"
if [[ -z "$API_URL" ]]; then
  pushd "$(dirname "$0")/../infrastructure/terraform" > /dev/null
  API_URL="$(terraform output -raw api_gateway_url 2>/dev/null || true)"
  popd > /dev/null
fi

if [[ -z "$API_URL" ]]; then
  echo "WARN: API_GATEWAY_URL unset and terraform output unavailable. Skipping HTTP smoke test."
  echo "PASS (partial): infra-level checks complete. Set API_GATEWAY_URL to run HTTP smoke."
  exit 0
fi

URLS_ENDPOINT="${API_URL%/}/api/v2/auth/oauth/urls"
HTTP_RESPONSE="$(curl -sS -o /tmp/oauth-urls.$$.json -w '%{http_code}' "$URLS_ENDPOINT" || echo "000")"

if [[ "$HTTP_RESPONSE" != "200" ]]; then
  echo "FAIL: $URLS_ENDPOINT returned HTTP $HTTP_RESPONSE"
  cat /tmp/oauth-urls.$$.json 2>/dev/null || true
  rm -f /tmp/oauth-urls.$$.json
  exit 1
fi

PROVIDER_COUNT="$(jq '.providers | length' < /tmp/oauth-urls.$$.json 2>/dev/null || echo 0)"
rm -f /tmp/oauth-urls.$$.json

if [[ "$PROVIDER_COUNT" -lt 1 ]]; then
  echo "FAIL: $URLS_ENDPOINT returned 200 but providers object is empty."
  exit 1
fi
echo "PASS: $URLS_ENDPOINT returned 200 with $PROVIDER_COUNT provider(s)."

echo ""
echo "================================================================"
echo "  All OAuth deploy checks PASSED for env: $ENV"
echo "================================================================"
