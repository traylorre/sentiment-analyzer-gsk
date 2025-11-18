# Secrets Manager for API Keys

# NewsAPI Secret
resource "aws_secretsmanager_secret" "newsapi" {
  name        = "${var.environment}/sentiment-analyzer/newsapi"
  description = "NewsAPI key for sentiment analysis ingestion"

  recovery_window_in_days = 7 # Allow 7-day recovery if accidentally deleted

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Purpose     = "newsapi-key"
  }
}

# NewsAPI Secret Rotation (90-day policy)
resource "aws_secretsmanager_secret_rotation" "newsapi" {
  secret_id           = aws_secretsmanager_secret.newsapi.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  # Only enable rotation if rotation Lambda is provided
  count = var.rotation_lambda_arn != null ? 1 : 0
}

# Dashboard API Key Secret
resource "aws_secretsmanager_secret" "dashboard_api_key" {
  name        = "${var.environment}/sentiment-analyzer/dashboard-api-key"
  description = "API key for dashboard Lambda Function URL authentication"

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Purpose     = "dashboard-auth"
  }
}

# Dashboard API Key Rotation
resource "aws_secretsmanager_secret_rotation" "dashboard_api_key" {
  secret_id           = aws_secretsmanager_secret.dashboard_api_key.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  count = var.rotation_lambda_arn != null ? 1 : 0
}

# NOTE: Secret values are NOT stored in Terraform state
# Use AWS CLI or Console to set initial secret values:
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/newsapi \
#   --secret-string '{"api_key":"YOUR_NEWSAPI_KEY"}'
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/dashboard-api-key \
#   --secret-string '{"api_key":"GENERATED_API_KEY"}'
