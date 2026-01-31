# Secrets Manager for API Keys

# Dashboard API Key Secret
resource "aws_secretsmanager_secret" "dashboard_api_key" {
  name        = "${var.environment}/sentiment-analyzer/dashboard-api-key"
  description = "API key for dashboard Lambda Function URL authentication"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Purpose     = "dashboard-auth"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
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

# ===================================================================
# Feature 006: Financial News Sentiment API Secrets
# ===================================================================

# Tiingo API Secret (Primary financial news source)
resource "aws_secretsmanager_secret" "tiingo" {
  name        = "${var.environment}/sentiment-analyzer/tiingo"
  description = "Tiingo API key for financial news and market data"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Purpose     = "tiingo-api-key"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_rotation" "tiingo" {
  secret_id           = aws_secretsmanager_secret.tiingo.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  count = var.rotation_lambda_arn != null ? 1 : 0
}

# Finnhub API Secret (Secondary financial news source)
resource "aws_secretsmanager_secret" "finnhub" {
  name        = "${var.environment}/sentiment-analyzer/finnhub"
  description = "Finnhub API key for financial news and sentiment data"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Purpose     = "finnhub-api-key"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_rotation" "finnhub" {
  secret_id           = aws_secretsmanager_secret.finnhub.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  count = var.rotation_lambda_arn != null ? 1 : 0
}

# SendGrid API Secret (Email notifications)
resource "aws_secretsmanager_secret" "sendgrid" {
  name        = "${var.environment}/sentiment-analyzer/sendgrid"
  description = "SendGrid API key for email notifications and magic links"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Purpose     = "sendgrid-api-key"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_rotation" "sendgrid" {
  secret_id           = aws_secretsmanager_secret.sendgrid.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  count = var.rotation_lambda_arn != null ? 1 : 0
}

# hCaptcha Secret (Bot protection for anonymous config creation)
resource "aws_secretsmanager_secret" "hcaptcha" {
  name        = "${var.environment}/sentiment-analyzer/hcaptcha"
  description = "hCaptcha secret key for bot protection"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Purpose     = "hcaptcha-secret"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_rotation" "hcaptcha" {
  secret_id           = aws_secretsmanager_secret.hcaptcha.id
  rotation_lambda_arn = var.rotation_lambda_arn

  rotation_rules {
    automatically_after_days = 90
  }

  count = var.rotation_lambda_arn != null ? 1 : 0
}

# Stripe Webhook Secret (Payment webhook signature verification)
# Blind spot fix: STRIPE_WEBHOOK_SECRET was missing from infrastructure
resource "aws_secretsmanager_secret" "stripe_webhook" {
  name        = "${var.environment}/sentiment-analyzer/stripe-webhook"
  description = "Stripe webhook secret for signature verification"
  kms_key_id  = var.kms_key_arn # Customer-managed encryption (FR-019)

  recovery_window_in_days = 7

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Purpose     = "stripe-webhook-verification"
  }

  # SECURITY: Prevent accidental deletion of credentials (FR-016)
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_secretsmanager_secret_rotation" "stripe_webhook" {
  secret_id           = aws_secretsmanager_secret.stripe_webhook.id
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
#   --secret-id ${var.environment}/sentiment-analyzer/dashboard-api-key \
#   --secret-string '{"api_key":"GENERATED_API_KEY"}'
#
# Financial News API secrets (Feature 006):
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/tiingo \
#   --secret-string '{"api_key":"YOUR_TIINGO_API_KEY"}'
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/finnhub \
#   --secret-string '{"api_key":"YOUR_FINNHUB_API_KEY"}'
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/sendgrid \
#   --secret-string '{"api_key":"YOUR_SENDGRID_API_KEY"}'
#
# aws secretsmanager put-secret-value \
#   --secret-id ${var.environment}/sentiment-analyzer/hcaptcha \
#   --secret-string '{"secret_key":"YOUR_HCAPTCHA_SECRET_KEY","site_key":"YOUR_HCAPTCHA_SITE_KEY"}'
