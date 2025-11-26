# IAM Module Variables

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB sentiment-items table"
  type        = string
}

variable "newsapi_secret_arn" {
  description = "ARN of the NewsAPI secret in Secrets Manager"
  type        = string
}

variable "dashboard_api_key_secret_arn" {
  description = "ARN of the Dashboard API key secret in Secrets Manager"
  type        = string
}

variable "analysis_topic_arn" {
  description = "ARN of the SNS topic for analysis triggers"
  type        = string
}

variable "dlq_arn" {
  description = "ARN of the SQS dead letter queue for analysis Lambda"
  type        = string
}

variable "model_s3_bucket_arn" {
  description = "ARN of the S3 bucket containing ML model files"
  type        = string
}

variable "chaos_experiments_table_arn" {
  description = "ARN of the chaos experiments DynamoDB table"
  type        = string
  default     = ""
}

variable "ticker_cache_bucket_arn" {
  description = "ARN of the S3 bucket containing ticker cache data (Feature 006)"
  type        = string
  default     = ""
}

variable "sendgrid_secret_arn" {
  description = "ARN of the SendGrid API key secret in Secrets Manager (Feature 006)"
  type        = string
  default     = ""
}
