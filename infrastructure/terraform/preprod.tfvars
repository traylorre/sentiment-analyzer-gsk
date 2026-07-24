# Preprod Environment Variables
# ==============================
#
# Preprod is a production mirror for integration testing.
# Infrastructure is identical to prod but with lower scale/cost.

environment = "preprod"
aws_region  = "us-east-1"

# Tags for cost tracking and resource management
tags = {
  Environment = "preprod"
  ManagedBy   = "Terraform"
  Purpose     = "Integration testing and production validation"
  CostCenter  = "testing"
}

# Note: Lambda memory/timeout and EventBridge schedule are configured
# in the Terraform modules with environment-appropriate defaults.
# DynamoDB uses on-demand billing (no reserved capacity).

# CORS: Preprod allows Amplify frontend, GitHub Pages, and localhost for testing.
# No wildcard allowed per security policy.
# Feature 1204: CloudFront URL removed - Amplify serves frontend directly
cors_allowed_origins = [
  "https://main.d29tlmksqcx494.amplifyapp.com", # AWS Amplify frontend (Feature 1105)
  "https://traylorre.github.io",                # GitHub Pages interview demo
  "http://localhost:3000",                      # Local development
  "http://localhost:8080"                       # Alternative local dev
]

# Feature 1054: JWT Secret for auth middleware
# This must match PREPROD_TEST_JWT_SECRET used by E2E tests (Feature 1053)
# The value is passed via TF_VAR_jwt_secret in CI to avoid committing secrets
# Default for local dev: "test-jwt-secret-for-e2e-only-not-production"

# Feature 1105: AWS Amplify SSR Frontend
# Deploys Next.js frontend via Amplify Hosting (replaces vanilla JS dashboard)
# GitHub PAT stored in Secrets Manager: preprod/amplify/github-token
enable_amplify            = true
amplify_github_repository = "https://github.com/traylorre/sentiment-analyzer-gsk"

# Feature 1189: Environment-specific JWT audience (A16)
# Prevents cross-environment token replay attacks
jwt_audience = "sentiment-api-preprod"

# Alarm notifications — required for operational visibility
# SNS topic subscription sends alarm state changes to this email.
# You must confirm the subscription via email after first deploy.
alarm_email = "scotthazlett+sentiment-alarm@gmail.com"

# ===================================================================
# Cost controls (active development shelved — minimize spend)
# ===================================================================
# WAF v2 has no free tier (~$42/mo: $5/ACL × 2 + Bot Control managed rules).
# Disabled while shelved. Re-enable by flipping to true (single flag flip,
# no feature rebuild). Removes SQLi/XSS/bot/rate-limit filtering on the
# public API + CloudFront while off.
enable_waf = false

# Extended alarms (~26 from cloudwatch-alarms module + 3 API Gateway alarms)
# bill $0.10 each beyond the 10-alarm free tier. Disabled to stay near free
# tier. Core monitoring-module alarms and the SNS topic remain.
enable_extended_cloudwatch_alarms = false

# CloudFront WAF teardown — PHASE 1 (disassociate, keep the ACL).
# enable_waf=false already drops web_acl_id from the CloudFront distribution.
# Keep the ACL itself alive (true) for this apply so Terraform doesn't try to
# delete it while CloudFront is still propagating the disassociation, which
# fails with WAFAssociatedItemException. Once this deploy reaches
# Status=Deployed, PHASE 2 sets this to false to delete the orphaned ACL.
enable_cloudfront_waf = true

# M1 WI-6: enable Google as a Cognito social identity provider.
# Google-only per Q-M1-1 (GitHub's IdP points at the GitHub Actions OIDC issuer
# and is a known-broken follow-up — do NOT add "GitHub" here).
#
# SEQUENCING (critical): the Cognito Google IdP (modules/cognito/google.tf) and
# the Lambda's ENABLED_OAUTH_PROVIDERS (main.tf:138, derived from the secret's
# client_id being non-empty) both take effect at `terraform apply`. Populate
# preprod/sentiment-analyzer/google-oauth (client_id/client_secret) BEFORE the
# apply that includes this line, so the IdP and the enabled-providers env land
# together. Secret-without-IdP yields Cognito "Invalid state"; IdP-without-secret
# yields a broken provider.
cognito_identity_providers = ["Google"]

# Feature 1383: durable OAuth env (previously set manually during WI-6 go-live).
# These feed two Terraform outputs (frontend_url, cognito_redirect_uri) that the CI
# dashboard-deploy "Step 2.5" syncs onto the Lambda's FRONTEND_URL / COGNITO_REDIRECT_URI
# env vars (the Lambda env is Terraform-frozen via ignore_changes=[environment], Feature 1290).
#
# frontend_url drives the OAuth redirect_uri allowlist (_resolve_redirect_uri, auth.py).
frontend_url = "https://main.d29tlmksqcx494.amplifyapp.com"

# cognito_callback_urls[0] feeds COGNITO_REDIRECT_URI (the static token-exchange fallback).
# The Amplify callback MUST be index [0]. localhost is included to document the dev origin
# the allowlist already permits. NOTE: the Cognito app client's registered callback URLs are
# ignore_changes-frozen (modules/cognito/main.tf), so this list only affects the Lambda-env
# output, not live Cognito registration.
cognito_callback_urls = [
  "https://main.d29tlmksqcx494.amplifyapp.com/auth/callback",
  "http://localhost:3000/auth/callback",
]
