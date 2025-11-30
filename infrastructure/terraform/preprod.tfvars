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

# Lambda Configuration
# Note: Same settings as prod to ensure accurate testing
lambda_memory_mb       = 512
lambda_timeout_seconds = 60

# DynamoDB Configuration
# Note: On-demand billing, no reserved capacity (cost optimization)
# Prod will use provisioned capacity or on-demand based on traffic

# EventBridge Schedule
# Run ingestion every 2 hours (less frequent than prod)
# Prod runs every 15 minutes
ingestion_schedule = "rate(2 hours)"

# Monitoring and Alerting
# Preprod has same alarms as prod but with higher thresholds
# This prevents alert fatigue while still catching major issues

# CORS: Preprod allows the CloudFront dashboard domain and localhost for testing.
# No wildcard allowed per security policy.
cors_allowed_origins = [
  "https://d2z9uvoj5xlbd2.cloudfront.net", # CloudFront dashboard
  "http://localhost:3000",                 # Local development
  "http://localhost:8080"                  # Alternative local dev
]
