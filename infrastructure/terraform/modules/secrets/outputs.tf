output "dashboard_api_key_secret_arn" {
  description = "ARN of the Dashboard API key secret"
  value       = aws_secretsmanager_secret.dashboard_api_key.arn
}

output "dashboard_api_key_secret_name" {
  description = "Name of the Dashboard API key secret"
  value       = aws_secretsmanager_secret.dashboard_api_key.name
}

# Feature 006: Financial News Sentiment Secrets

output "tiingo_secret_arn" {
  description = "ARN of the Tiingo API secret"
  value       = aws_secretsmanager_secret.tiingo.arn
}

output "tiingo_secret_name" {
  description = "Name of the Tiingo API secret"
  value       = aws_secretsmanager_secret.tiingo.name
}

output "finnhub_secret_arn" {
  description = "ARN of the Finnhub API secret"
  value       = aws_secretsmanager_secret.finnhub.arn
}

output "finnhub_secret_name" {
  description = "Name of the Finnhub API secret"
  value       = aws_secretsmanager_secret.finnhub.name
}

output "sendgrid_secret_arn" {
  description = "ARN of the SendGrid API secret"
  value       = aws_secretsmanager_secret.sendgrid.arn
}

output "sendgrid_secret_name" {
  description = "Name of the SendGrid API secret"
  value       = aws_secretsmanager_secret.sendgrid.name
}

output "hcaptcha_secret_arn" {
  description = "ARN of the hCaptcha secret"
  value       = aws_secretsmanager_secret.hcaptcha.arn
}

output "hcaptcha_secret_name" {
  description = "Name of the hCaptcha secret"
  value       = aws_secretsmanager_secret.hcaptcha.name
}

# Stripe Webhook Secret
output "stripe_webhook_secret_arn" {
  description = "ARN of the Stripe webhook secret for signature verification"
  value       = aws_secretsmanager_secret.stripe_webhook.arn
}

output "stripe_webhook_secret_name" {
  description = "Name of the Stripe webhook secret"
  value       = aws_secretsmanager_secret.stripe_webhook.name
}
