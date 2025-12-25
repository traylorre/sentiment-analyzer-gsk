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

# CORS: Preprod allows the CloudFront dashboard domain, GitHub Pages, and localhost for testing.
# No wildcard allowed per security policy.
cors_allowed_origins = [
  "https://d2z9uvoj5xlbd2.cloudfront.net", # CloudFront dashboard
  "https://traylorre.github.io",           # GitHub Pages interview demo
  "http://localhost:3000",                 # Local development
  "http://localhost:8080"                  # Alternative local dev
]

# Feature 1054: JWT Secret for auth middleware
# This must match PREPROD_TEST_JWT_SECRET used by E2E tests (Feature 1053)
# The value is passed via TF_VAR_jwt_secret in CI to avoid committing secrets
# Default for local dev: "test-jwt-secret-for-e2e-only-not-production"
