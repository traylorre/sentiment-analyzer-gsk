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
