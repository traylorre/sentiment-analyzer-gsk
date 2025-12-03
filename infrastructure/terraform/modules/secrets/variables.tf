variable "environment" {
  description = "Environment name"
  type        = string
}

variable "rotation_lambda_arn" {
  description = "ARN of Lambda function for secret rotation (optional)"
  type        = string
  default     = null
}

variable "kms_key_arn" {
  description = "ARN of KMS key for secret encryption (FR-019). If null, uses AWS-managed key."
  type        = string
  default     = null
}
