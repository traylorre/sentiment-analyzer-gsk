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
