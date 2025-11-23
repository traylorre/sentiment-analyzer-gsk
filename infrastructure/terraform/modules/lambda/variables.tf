# Lambda Module Variables
# =======================

# Required Variables
# ------------------

variable "function_name" {
  description = "Name of the Lambda function"
  type        = string
}

variable "description" {
  description = "Description of the Lambda function"
  type        = string
}

variable "iam_role_arn" {
  description = "ARN of the IAM role for Lambda execution"
  type        = string
}

variable "handler" {
  description = "Lambda function handler (e.g., handler.lambda_handler)"
  type        = string
}

variable "s3_bucket" {
  description = "S3 bucket containing the deployment package"
  type        = string
}

variable "s3_key" {
  description = "S3 key (path) to the deployment package"
  type        = string
}

# Optional Variables with Defaults
# ---------------------------------

variable "runtime" {
  description = "Lambda runtime"
  type        = string
  default     = "python3.13"
}

variable "timeout" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 30
}

variable "memory_size" {
  description = "Lambda memory in MB"
  type        = number
  default     = 512
}

variable "ephemeral_storage_size" {
  description = "Ephemeral storage (/tmp) size in MB (512-10240)"
  type        = number
  default     = 512

  validation {
    condition     = var.ephemeral_storage_size >= 512 && var.ephemeral_storage_size <= 10240
    error_message = "Ephemeral storage must be between 512 MB and 10240 MB."
  }
}

variable "environment_variables" {
  description = "Environment variables for the Lambda function"
  type        = map(string)
  default     = {}
}

variable "layers" {
  description = "List of Lambda layer ARNs to attach"
  type        = list(string)
  default     = []
}

variable "reserved_concurrency" {
  description = "Reserved concurrent executions (null = no limit)"
  type        = number
  default     = null
}

variable "source_code_hash" {
  description = "Base64-encoded SHA256 hash of the deployment package"
  type        = string
  default     = null
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention must be a valid CloudWatch Logs retention period."
  }
}

variable "tracing_mode" {
  description = "X-Ray tracing mode (Active or PassThrough)"
  type        = string
  default     = "PassThrough"

  validation {
    condition     = contains(["Active", "PassThrough"], var.tracing_mode)
    error_message = "Tracing mode must be Active or PassThrough."
  }
}

variable "vpc_config" {
  description = "VPC configuration for Lambda"
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "dlq_arn" {
  description = "ARN of SQS queue or SNS topic for dead letter queue"
  type        = string
  default     = null
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "ignore_source_code_changes" {
  description = "Ignore changes to s3_key and source_code_hash (for alias deployments)"
  type        = bool
  default     = false
}

# Function URL Configuration
# --------------------------

variable "create_function_url" {
  description = "Create a Lambda Function URL"
  type        = bool
  default     = false
}

variable "function_url_auth_type" {
  description = "Authorization type for Function URL (NONE or AWS_IAM)"
  type        = string
  default     = "NONE"

  validation {
    condition     = contains(["NONE", "AWS_IAM"], var.function_url_auth_type)
    error_message = "Function URL auth type must be NONE or AWS_IAM."
  }
}

variable "function_url_cors" {
  description = "CORS configuration for Function URL"
  type = object({
    allow_credentials = bool
    allow_headers     = list(string)
    allow_methods     = list(string)
    allow_origins     = list(string)
    expose_headers    = list(string)
    max_age           = number
  })
  default = {
    allow_credentials = false
    allow_headers     = ["content-type", "authorization"]
    allow_methods     = ["GET", "POST", "OPTIONS"]
    allow_origins     = ["*"]
    expose_headers    = []
    max_age           = 86400
  }
}

# Alarm Configuration
# -------------------

variable "create_error_alarm" {
  description = "Create CloudWatch alarm for Lambda errors"
  type        = bool
  default     = false
}

variable "error_alarm_threshold" {
  description = "Number of errors to trigger alarm"
  type        = number
  default     = 5
}

variable "create_duration_alarm" {
  description = "Create CloudWatch alarm for Lambda duration"
  type        = bool
  default     = false
}

variable "duration_alarm_threshold" {
  description = "Duration threshold in milliseconds to trigger alarm"
  type        = number
  default     = 5000
}

variable "alarm_actions" {
  description = "List of ARNs to notify when alarm triggers"
  type        = list(string)
  default     = []
}
