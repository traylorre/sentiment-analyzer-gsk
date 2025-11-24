# Chaos Testing Module Variables

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "enable_chaos_testing" {
  description = "Enable chaos testing infrastructure (FIS templates, IAM roles)"
  type        = bool
  default     = false
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table to target for chaos experiments"
  type        = string
}

variable "write_throttle_alarm_arn" {
  description = "ARN of the CloudWatch alarm for write throttles (kill switch)"
  type        = string
}

# Phase 4 variables (commented out for now)
# variable "analysis_lambda_arn" {
#   description = "ARN of the Analysis Lambda to target for latency injection"
#   type        = string
#   default     = ""
# }
#
# variable "lambda_error_alarm_arn" {
#   description = "ARN of the CloudWatch alarm for Lambda errors (kill switch)"
#   type        = string
#   default     = ""
# }
