output "ingestion_schedule_arn" {
  description = "ARN of the ingestion EventBridge rule"
  value       = aws_cloudwatch_event_rule.ingestion_schedule.arn
}

output "metrics_schedule_arn" {
  description = "ARN of the metrics EventBridge rule"
  value       = aws_cloudwatch_event_rule.metrics_schedule.arn
}
