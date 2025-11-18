variable "environment" {
  description = "Environment name"
  type        = string
}

variable "ingestion_lambda_arn" {
  description = "ARN of the Ingestion Lambda function"
  type        = string
}

variable "ingestion_lambda_function_name" {
  description = "Name of the Ingestion Lambda function"
  type        = string
}

variable "metrics_lambda_arn" {
  description = "ARN of the Metrics Lambda function"
  type        = string
}

variable "metrics_lambda_function_name" {
  description = "Name of the Metrics Lambda function"
  type        = string
}
