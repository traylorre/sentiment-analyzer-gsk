# Chaos Testing Module Outputs
# ============================
#
# NOTE: FIS Lambda templates are currently disabled due to Terraform provider bug.
# See: https://github.com/hashicorp/terraform-provider-aws/issues/41208
# These outputs return empty strings until the templates can be re-enabled.

output "fis_lambda_latency_template_id" {
  description = "ID of the FIS experiment template for Lambda latency injection (DISABLED)"
  value       = "" # Disabled until Terraform provider supports Lambda FIS targets
}

output "fis_lambda_error_template_id" {
  description = "ID of the FIS experiment template for Lambda error injection (DISABLED)"
  value       = "" # Disabled until Terraform provider supports Lambda FIS targets
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
