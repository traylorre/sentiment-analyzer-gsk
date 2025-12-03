# KMS Module Variables

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
