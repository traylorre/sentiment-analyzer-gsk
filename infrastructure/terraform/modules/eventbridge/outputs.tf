output "ingestion_schedule_arn" {
  description = "ARN of the ingestion EventBridge rule"
  value       = aws_cloudwatch_event_rule.ingestion_schedule.arn
}

output "metrics_schedule_arn" {
  description = "ARN of the metrics EventBridge rule (null if not created)"
  value       = var.create_metrics_schedule ? aws_cloudwatch_event_rule.metrics_schedule[0].arn : null
}

output "daily_digest_schedule_arn" {
  description = "ARN of the daily digest EventBridge rule (null if not created)"
  value       = var.create_digest_schedule ? aws_cloudwatch_event_rule.daily_digest_schedule[0].arn : null
}
