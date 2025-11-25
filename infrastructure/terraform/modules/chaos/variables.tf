# Chaos Testing Module Variables
# ===============================

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "enable_chaos_testing" {
  description = "Enable chaos testing infrastructure (FIS templates, IAM roles)"
  type        = bool
  default     = false
}

variable "lambda_arns" {
  description = "List of Lambda ARNs to target for chaos experiments"
  type        = list(string)
}

variable "lambda_error_alarm_arn" {
  description = "ARN of the CloudWatch alarm for Lambda errors (kill switch for experiments)"
  type        = string
}

# ============================================================================
# Deprecated Variables (kept for backwards compatibility during migration)
# ============================================================================

variable "dynamodb_table_arn" {
  description = "DEPRECATED: DynamoDB ARN - FIS doesn't support DynamoDB API fault injection"
  type        = string
  default     = ""
}

variable "write_throttle_alarm_arn" {
  description = "DEPRECATED: Was used for DynamoDB throttle alarm"
  type        = string
  default     = ""
}
