variable "environment" {
  description = "Environment name"
  type        = string
}

variable "analysis_lambda_arn" {
  description = "ARN of the Analysis Lambda function (optional, set to create subscription)"
  type        = string
  default     = null
}

variable "analysis_lambda_function_name" {
  description = "Name of the Analysis Lambda function (optional, set to create subscription)"
  type        = string
  default     = null
}

variable "create_subscription" {
  description = "Whether to create the SNS subscription to Analysis Lambda"
  type        = bool
  default     = false
}
