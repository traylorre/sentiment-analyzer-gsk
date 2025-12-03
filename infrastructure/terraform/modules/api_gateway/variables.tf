# API Gateway Module Variables

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the Lambda function to integrate with"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "ARN for Lambda invocation (e.g., arn:aws:apigateway:region:lambda:path/2015-03-31/functions/arn:aws:lambda:region:account:function:name/invocations)"
  type        = string
}

variable "stage_name" {
  description = "API Gateway stage name"
  type        = string
  default     = "v1"
}

# Rate Limiting Configuration

variable "rate_limit" {
  description = "Steady-state request rate limit (requests per second)"
  type        = number
  default     = 100
}

variable "burst_limit" {
  description = "Burst request limit (concurrent requests)"
  type        = number
  default     = 200
}

variable "quota_limit" {
  description = "Optional quota limit (requests per period). Set to 0 to disable."
  type        = number
  default     = 0
}

variable "quota_period" {
  description = "Quota period (DAY, WEEK, or MONTH)"
  type        = string
  default     = "DAY"
}

# Monitoring Configuration

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "enable_xray_tracing" {
  description = "Enable AWS X-Ray tracing for API Gateway"
  type        = bool
  default     = true
}

variable "create_alarms" {
  description = "Create CloudWatch alarms for API Gateway metrics"
  type        = bool
  default     = true
}

variable "alarm_actions" {
  description = "SNS topic ARNs for alarm notifications"
  type        = list(string)
  default     = []
}

variable "error_4xx_threshold" {
  description = "Alarm threshold for 4XX errors (count per 5 minutes)"
  type        = number
  default     = 100
}

variable "error_5xx_threshold" {
  description = "Alarm threshold for 5XX errors (count per 5 minutes)"
  type        = number
  default     = 10
}

variable "latency_threshold" {
  description = "Alarm threshold for p90 latency (milliseconds)"
  type        = number
  default     = 5000
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# ===================================================================
# Authentication Configuration (FR-012 to FR-014)
# ===================================================================

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool for JWT authorization. If set, enables Cognito authorizer."
  type        = string
  default     = null
}

variable "enable_cognito_auth" {
  description = "Enable Cognito JWT authorization for API Gateway endpoints"
  type        = bool
  default     = false
}
