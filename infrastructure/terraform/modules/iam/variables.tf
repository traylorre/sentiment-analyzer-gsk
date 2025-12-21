# IAM Module Variables

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB sentiment-items table"
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

variable "tiingo_secret_arn" {
  description = "ARN of the Tiingo API key secret in Secrets Manager (Feature 006)"
  type        = string
  default     = ""
}

variable "finnhub_secret_arn" {
  description = "ARN of the Finnhub API key secret in Secrets Manager (Feature 006)"
  type        = string
  default     = ""
}

variable "feature_006_users_table_arn" {
  description = "ARN of the Feature 006 sentiment-users DynamoDB table"
  type        = string
  default     = ""
}

variable "enable_feature_006" {
  description = "Whether Feature 006 resources should be created (ticker cache, users table policies)"
  type        = bool
  default     = true
}

variable "secrets_kms_key_arn" {
  description = "ARN of the KMS key used to encrypt secrets (required for secretsmanager:GetSecretValue)"
  type        = string
  default     = ""
}

variable "timeseries_table_arn" {
  description = "ARN of the Feature 1009 sentiment-timeseries DynamoDB table"
  type        = string
  default     = ""
}

variable "enable_timeseries" {
  description = "Enable Feature 1009 timeseries IAM policies (set explicitly to avoid count depends on unknown)"
  type        = bool
  default     = false
}
