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
  description = "ARN of the Metrics Lambda function (optional)"
  type        = string
  default     = null
}

variable "metrics_lambda_function_name" {
  description = "Name of the Metrics Lambda function (optional)"
  type        = string
  default     = null
}

variable "create_metrics_schedule" {
  description = "Whether to create the metrics schedule (requires metrics Lambda)"
  type        = bool
  default     = false
}

# Daily Digest Schedule (Feature 006)
variable "notification_lambda_arn" {
  description = "ARN of the Notification Lambda function (optional)"
  type        = string
  default     = null
}

variable "notification_lambda_function_name" {
  description = "Name of the Notification Lambda function (optional)"
  type        = string
  default     = null
}

variable "create_digest_schedule" {
  description = "Whether to create the daily digest schedule (requires notification Lambda)"
  type        = bool
  default     = false
}
