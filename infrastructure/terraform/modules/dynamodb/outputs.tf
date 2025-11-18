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
  description = "ARN of the backup vault"
  value       = aws_backup_vault.dynamodb.arn
}

output "backup_plan_id" {
  description = "ID of the backup plan"
  value       = aws_backup_plan.dynamodb_daily.id
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
