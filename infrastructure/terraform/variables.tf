# Terraform Variables

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "watch_tags" {
  description = "Comma-separated list of tags to watch (max 5)"
  type        = string
  default     = "AI,climate,economy,health,sports"
  validation {
    condition     = length(split(",", var.watch_tags)) <= 5
    error_message = "Maximum 5 watch tags allowed."
  }
}

variable "model_version" {
  description = "Sentiment model version"
  type        = string
  default     = "v1.0.0"
  validation {
    condition     = can(regex("^v\\d+\\.\\d+\\.\\d+$", var.model_version))
    error_message = "Model version must follow semantic versioning (e.g., v1.0.0)."
  }
}

variable "alarm_email" {
  description = "Email address for alarm notifications (leave empty to skip)"
  type        = string
  default     = ""
}

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD for cost alerts"
  type        = number
  default     = 50
}

variable "model_layer_arns" {
  description = "List of Lambda layer ARNs for the sentiment model"
  type        = list(string)
  default     = []
}
