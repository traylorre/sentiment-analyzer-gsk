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
# External Chaos Actor Variables (Feature 1237)
# ============================================================================

variable "chaos_engineer_principals" {
  description = "List of IAM ARNs allowed to assume the chaos-engineer role"
  type        = list(string)
  default     = []
}

variable "lambda_execution_role_arns" {
  description = "ARNs of Lambda execution roles (for IAM policy attach/detach scoping)"
  type        = list(string)
  default     = []
}

variable "eventbridge_rule_arns" {
  description = "ARNs of EventBridge rules that can be disabled for chaos testing"
  type        = list(string)
  default     = []
}

variable "chaos_experiments_table_arn" {
  description = "ARN of the chaos-experiments DynamoDB table for audit logging"
  type        = string
  default     = ""
}

# Feature 1250: Auto-restore scheduling
variable "dashboard_lambda_arn" {
  description = "ARN of the Dashboard Lambda for auto-restore scheduling target"
  type        = string
  default     = ""
}

variable "alerting_topic_arn" {
  description = "ARN of SNS topic for CloudWatch alarm notifications"
  type        = string
  default     = ""
}
