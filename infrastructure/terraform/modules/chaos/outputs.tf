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
# External Chaos Actor Outputs (Feature 1237)
# ============================================================================

output "chaos_engineer_role_arn" {
  description = "ARN of the chaos-engineer IAM role"
  value       = var.enable_chaos_testing && var.environment != "prod" ? aws_iam_role.chaos_engineer[0].arn : ""
}

output "kill_switch_parameter_name" {
  description = "Name of the SSM parameter for the chaos kill switch"
  value       = var.enable_chaos_testing && var.environment != "prod" ? aws_ssm_parameter.chaos_kill_switch[0].name : ""
}

output "deny_dynamodb_write_policy_arn" {
  description = "ARN of the pre-created deny-DynamoDB-write policy"
  value       = var.enable_chaos_testing && var.environment != "prod" ? aws_iam_policy.chaos_deny_dynamodb_write[0].arn : ""
}

# ============================================================================
# Deprecated Outputs (kept for backwards compatibility)
# ============================================================================

output "fis_dynamodb_throttle_template_id" {
  description = "DEPRECATED: Use fis_lambda_latency_template_id instead"
  value       = ""
}
