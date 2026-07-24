# Production Environment Variables
# =================================
#
# Production is the live environment serving real users.
# All resources use production-grade configuration.

environment = "prod"

# AWS Configuration
aws_region = "us-east-1"

# Tags for cost tracking and resource management
tags = {
  Environment = "prod"
  ManagedBy   = "Terraform"
  Purpose     = "Production sentiment analysis service"
  CostCenter  = "production"
}

# NewsAPI Configuration
watch_tags = "AI,climate,economy,health,sports"

# Model Configuration
model_version = "v1.0.0"

# Monitoring and Alerting
alarm_email = "" # Set to production email or PagerDuty endpoint

# Cost Monitoring
# Alert if monthly costs exceed $100 (adjust based on expected usage)
monthly_budget_limit = 100

# Lambda Layer ARNs (if using pre-built model layers)
model_layer_arns = []

# CORS: Production requires explicit origins - NO WILDCARDS
# Feature 1269: Populated with known production origins
cors_allowed_origins = [
  "https://traylorre.github.io", # GitHub Pages interview demo
  # TODO(1269): Add Amplify production URL after enable_amplify is set
  # Get it from: terraform output amplify_production_url
  # Format: "https://main.<app-id>.amplifyapp.com"
]

# TODO(1383): Set frontend_url + cognito_callback_urls[0] to the prod Amplify URL once
# enable_amplify is turned on for prod and the URL is finalized (see TODO(1269) above).
# The CI dashboard-deploy "Step 2.5" is empty-safe and will no-op FRONTEND_URL /
# COGNITO_REDIRECT_URI until these are set. Do NOT copy the preprod URL here — prod uses a
# different frontend URL. Left unset deliberately (owner question O1: prod canonical URL).

# Feature 1054: JWT Secret for auth middleware
# IMPORTANT: Use a strong, unique secret for production
# The value is passed via TF_VAR_jwt_secret in CI - never commit the actual secret

# Feature 1189: Environment-specific JWT audience (A16)
# Prevents cross-environment token replay attacks
jwt_audience = "sentiment-api-prod"
