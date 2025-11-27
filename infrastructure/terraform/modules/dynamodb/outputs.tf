# DynamoDB Module Outputs

output "table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.sentiment_items.name
}

output "table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.sentiment_items.arn
}

output "table_stream_arn" {
  description = "ARN of the DynamoDB Stream"
  value       = aws_dynamodb_table.sentiment_items.stream_arn
}

output "gsi_by_sentiment_name" {
  description = "Name of the by_sentiment GSI"
  value       = "by_sentiment"
}

output "gsi_by_tag_name" {
  description = "Name of the by_tag GSI"
  value       = "by_tag"
}

output "gsi_by_status_name" {
  description = "Name of the by_status GSI"
  value       = "by_status"
}

output "backup_vault_arn" {
  description = "ARN of the backup vault (empty if backups disabled)"
  value       = var.enable_backup ? aws_backup_vault.dynamodb[0].arn : ""
}

output "backup_plan_id" {
  description = "ID of the backup plan (empty if backups disabled)"
  value       = var.enable_backup ? aws_backup_plan.dynamodb_daily[0].id : ""
}

output "cloudwatch_alarm_user_errors_arn" {
  description = "ARN of the user errors CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.user_errors.arn
}

output "cloudwatch_alarm_system_errors_arn" {
  description = "ARN of the system errors CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.system_errors.arn
}

output "cloudwatch_alarm_write_throttles_arn" {
  description = "ARN of the write throttles CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.write_throttles.arn
}

# Feature 006: User Data Table Outputs
output "feature_006_users_table_name" {
  description = "Name of the Feature 006 users DynamoDB table"
  value       = aws_dynamodb_table.feature_006_users.name
}

output "feature_006_users_table_arn" {
  description = "ARN of the Feature 006 users DynamoDB table"
  value       = aws_dynamodb_table.feature_006_users.arn
}

output "feature_006_gsi_by_email" {
  description = "Name of the by_email GSI (user lookup)"
  value       = "by_email"
}

output "feature_006_gsi_by_cognito_sub" {
  description = "Name of the by_cognito_sub GSI (OAuth lookup)"
  value       = "by_cognito_sub"
}

output "feature_006_gsi_by_entity_status" {
  description = "Name of the by_entity_status GSI (notification/alert filtering)"
  value       = "by_entity_status"
}

# Chaos Testing Outputs
output "chaos_experiments_table_name" {
  description = "Name of the Chaos Experiments DynamoDB table"
  value       = aws_dynamodb_table.chaos_experiments.name
}

output "chaos_experiments_table_arn" {
  description = "ARN of the Chaos Experiments DynamoDB table"
  value       = aws_dynamodb_table.chaos_experiments.arn
}
