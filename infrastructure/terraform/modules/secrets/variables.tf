variable "environment" {
  description = "Environment name"
  type        = string
}

variable "rotation_lambda_arn" {
  description = "ARN of Lambda function for secret rotation (optional)"
  type        = string
  default     = null
}
