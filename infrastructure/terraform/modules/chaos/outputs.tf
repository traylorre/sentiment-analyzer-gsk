# Chaos Testing Module Outputs

output "fis_dynamodb_throttle_template_id" {
  description = "ID of the FIS experiment template for DynamoDB throttling"
  value       = var.enable_chaos_testing ? aws_fis_experiment_template.dynamodb_throttle[0].id : ""
}

output "fis_execution_role_arn" {
  description = "ARN of the IAM role used by FIS to execute experiments"
  value       = var.enable_chaos_testing ? aws_iam_role.fis_execution[0].arn : ""
}

output "fis_log_group_name" {
  description = "Name of the CloudWatch Log Group for FIS experiment logs"
  value       = var.enable_chaos_testing ? aws_cloudwatch_log_group.fis_experiments[0].name : ""
}

# Phase 4 outputs (commented out for now)
# output "fis_lambda_delay_template_id" {
#   description = "ID of the FIS experiment template for Lambda delay injection"
#   value       = var.enable_chaos_testing ? aws_fis_experiment_template.lambda_delay[0].id : ""
# }
