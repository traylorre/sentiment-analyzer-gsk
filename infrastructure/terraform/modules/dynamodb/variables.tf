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
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional tags to apply to all resources"
  type        = map(string)
  default     = {}
}
