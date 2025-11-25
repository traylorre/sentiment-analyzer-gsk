# Chaos Testing Module Outputs
# ============================

output "fis_lambda_latency_template_id" {
  description = "ID of the FIS experiment template for Lambda latency injection"
  value       = var.enable_chaos_testing ? aws_fis_experiment_template.lambda_latency[0].id : ""
}

output "fis_lambda_error_template_id" {
  description = "ID of the FIS experiment template for Lambda error injection"
  value       = var.enable_chaos_testing ? aws_fis_experiment_template.lambda_error[0].id : ""
}

output "fis_execution_role_arn" {
  description = "ARN of the IAM role used by FIS to execute experiments"
  value       = var.enable_chaos_testing ? aws_iam_role.fis_execution[0].arn : ""
}

output "fis_log_group_name" {
  description = "Name of the CloudWatch Log Group for FIS experiment logs"
  value       = var.enable_chaos_testing ? aws_cloudwatch_log_group.fis_experiments[0].name : ""
}

# ============================================================================
# Deprecated Outputs (kept for backwards compatibility)
# ============================================================================

output "fis_dynamodb_throttle_template_id" {
  description = "DEPRECATED: Use fis_lambda_latency_template_id instead"
  value       = ""
}
