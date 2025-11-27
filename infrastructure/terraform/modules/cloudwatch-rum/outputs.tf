output "app_monitor_id" {
  description = "ID of the CloudWatch RUM App Monitor"
  value       = aws_rum_app_monitor.dashboard.id
}

output "app_monitor_arn" {
  description = "ARN of the CloudWatch RUM App Monitor"
  value       = aws_rum_app_monitor.dashboard.arn
}

output "app_monitor_cw_log_group" {
  description = "CloudWatch Log Group for RUM events (if enabled)"
  value       = aws_rum_app_monitor.dashboard.cw_log_group
}

output "identity_pool_id" {
  description = "Cognito Identity Pool ID for RUM"
  value       = aws_cognito_identity_pool.rum.id
}

output "guest_role_arn" {
  description = "IAM role ARN for unauthenticated RUM users"
  value       = aws_iam_role.rum_guest.arn
}

output "snippet_config" {
  description = "Configuration object for RUM JavaScript snippet"
  value = {
    app_monitor_id   = aws_rum_app_monitor.dashboard.id
    identity_pool_id = aws_cognito_identity_pool.rum.id
    guest_role_arn   = aws_iam_role.rum_guest.arn
    region           = data.aws_region.current.name
  }
}

data "aws_region" "current" {}
