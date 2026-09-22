# Monitoring Module Outputs

output "alarm_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = aws_sns_topic.alarms.arn
}

output "budget_name" {
  description = "Name of the monthly budget"
  value       = aws_budgets_budget.monthly.name
}
