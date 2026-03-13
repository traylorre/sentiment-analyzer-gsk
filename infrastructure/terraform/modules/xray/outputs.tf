# X-Ray Module Outputs
# ====================

# ===================================================================
# Group ARNs (for alarm references)
# ===================================================================

output "errors_group_arn" {
  description = "ARN of the sentiment-errors X-Ray group"
  value       = aws_xray_group.errors.arn
}

output "production_traces_group_arn" {
  description = "ARN of the production-traces X-Ray group"
  value       = aws_xray_group.production_traces.arn
}

output "canary_traces_group_arn" {
  description = "ARN of the canary-traces X-Ray group"
  value       = aws_xray_group.canary_traces.arn
}

output "sse_group_arn" {
  description = "ARN of the sentiment-sse X-Ray group"
  value       = aws_xray_group.sse.arn
}

output "sse_reconnections_group_arn" {
  description = "ARN of the sse-reconnections X-Ray group"
  value       = aws_xray_group.sse_reconnections.arn
}

# ===================================================================
# Group Names (for CloudWatch metric filters)
# ===================================================================

output "errors_group_name" {
  description = "Name of the sentiment-errors X-Ray group"
  value       = aws_xray_group.errors.group_name
}

output "canary_traces_group_name" {
  description = "Name of the canary-traces X-Ray group"
  value       = aws_xray_group.canary_traces.group_name
}

output "sse_group_name" {
  description = "Name of the sentiment-sse X-Ray group"
  value       = aws_xray_group.sse.group_name
}

# ===================================================================
# Sampling Rule Names
# ===================================================================

output "sampling_rule_names" {
  description = "Names of all active sampling rules"
  value = var.environment == "prod" ? [
    aws_xray_sampling_rule.prod_apigw[0].rule_name,
    aws_xray_sampling_rule.prod_fnurl[0].rule_name,
    aws_xray_sampling_rule.prod_default[0].rule_name,
    ] : [
    aws_xray_sampling_rule.non_prod[0].rule_name,
  ]
}
