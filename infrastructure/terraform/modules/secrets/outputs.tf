output "newsapi_secret_arn" {
  description = "ARN of the NewsAPI secret"
  value       = aws_secretsmanager_secret.newsapi.arn
}

output "newsapi_secret_name" {
  description = "Name of the NewsAPI secret"
  value       = aws_secretsmanager_secret.newsapi.name
}

output "dashboard_api_key_secret_arn" {
  description = "ARN of the Dashboard API key secret"
  value       = aws_secretsmanager_secret.dashboard_api_key.arn
}

output "dashboard_api_key_secret_name" {
  description = "Name of the Dashboard API key secret"
  value       = aws_secretsmanager_secret.dashboard_api_key.name
}
