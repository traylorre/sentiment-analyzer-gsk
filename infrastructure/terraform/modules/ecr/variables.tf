# ECR Module Variables

variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
}

variable "environment" {
  description = "Environment name (preprod, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region where ECR repository will be created"
  type        = string
}

variable "aws_account_id" {
  description = "AWS account ID for repository policy"
  type        = string
}

variable "tags" {
  description = "Additional tags for the ECR repository"
  type        = map(string)
  default     = {}
}
