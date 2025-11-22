# DynamoDB Module Variables

variable "environment" {
  description = "Environment name (dev, preprod, or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "preprod", "prod"], var.environment)
    error_message = "Environment must be one of: dev, preprod, prod."
  }
}

variable "aws_region" {
  description = "AWS region for DynamoDB table"
  type        = string
  # No default - region must be explicitly provided
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}

variable "enable_backup" {
  description = "Enable AWS Backup for DynamoDB table (disable for environments with IAM limitations)"
  type        = bool
  default     = true
}
