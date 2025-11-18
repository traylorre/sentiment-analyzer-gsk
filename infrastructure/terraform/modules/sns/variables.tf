variable "environment" {
  description = "Environment name"
  type        = string
}

variable "analysis_lambda_arn" {
  description = "ARN of the Analysis Lambda function"
  type        = string
}

variable "analysis_lambda_function_name" {
  description = "Name of the Analysis Lambda function"
  type        = string
}
