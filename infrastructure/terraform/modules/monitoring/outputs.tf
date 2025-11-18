# Monitoring Module Outputs

output "alarm_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "alarm_names" {
  description = "List of all alarm names created"
  value = [
    aws_cloudwatch_metric_alarm.ingestion_errors.alarm_name,
    aws_cloudwatch_metric_alarm.analysis_errors.alarm_name,
    aws_cloudwatch_metric_alarm.dashboard_errors.alarm_name,
    aws_cloudwatch_metric_alarm.analysis_latency.alarm_name,
    aws_cloudwatch_metric_alarm.dashboard_latency.alarm_name,
    aws_cloudwatch_metric_alarm.sns_delivery_failures.alarm_name,
    aws_cloudwatch_metric_alarm.newsapi_rate_limit.alarm_name,
    aws_cloudwatch_metric_alarm.no_new_items.alarm_name,
    aws_cloudwatch_metric_alarm.dlq_depth.alarm_name
  ]
}

output "budget_name" {
  description = "Name of the monthly budget"
  value       = aws_budgets_budget.monthly.name
}
