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
    aws_cloudwatch_metric_alarm.no_new_items.alarm_name,
    aws_cloudwatch_metric_alarm.dlq_depth.alarm_name,
    # Feature 006: Tiingo/Finnhub API alarms (replaced NewsAPI)
    aws_cloudwatch_metric_alarm.tiingo_error_rate.alarm_name,
    aws_cloudwatch_metric_alarm.finnhub_error_rate.alarm_name,
    aws_cloudwatch_metric_alarm.circuit_breaker_open.alarm_name,
    # Feature 006: SendGrid quota alarms
    aws_cloudwatch_metric_alarm.sendgrid_quota_warning.alarm_name,
    aws_cloudwatch_metric_alarm.sendgrid_quota_critical.alarm_name,
  ]
}

output "budget_name" {
  description = "Name of the monthly budget"
  value       = aws_budgets_budget.monthly.name
}

output "analysis_errors_alarm_arn" {
  description = "ARN of the Analysis Lambda errors alarm (used as FIS kill switch)"
  value       = aws_cloudwatch_metric_alarm.analysis_errors.arn
}
