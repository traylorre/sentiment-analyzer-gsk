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

# EventBridge Schedule
# Run ingestion every 15 minutes for near-real-time analysis
ingestion_schedule = "rate(15 minutes)"

# Monitoring and Alerting
alarm_email = "" # Set to production email or PagerDuty endpoint

# Cost Monitoring
# Alert if monthly costs exceed $100 (adjust based on expected usage)
monthly_budget_limit = 100

# Lambda Layer ARNs (if using pre-built model layers)
model_layer_arns = []

# CORS: Production requires explicit origins - NO WILDCARDS
# IMPORTANT: Set this to your CloudFront domain before deploying to production
# The CloudFront domain is output after first deployment as cloudfront_domain_name
# Example: ["https://d1234567890.cloudfront.net"]
# You can also add custom domains: ["https://dashboard.example.com", "https://d1234567890.cloudfront.net"]
cors_allowed_origins = []
