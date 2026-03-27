# CloudFront SSE Module Variables
# Feature 1255: CloudFront distribution for SSE streaming with WAF protection

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "origin_url" {
  description = "SSE Lambda Function URL (origin for CloudFront)"
  type        = string
}

variable "waf_web_acl_arn" {
  description = "WAF v2 WebACL ARN to associate with CloudFront (CLOUDFRONT scope)"
  type        = string
  default     = ""
}

variable "price_class" {
  description = "CloudFront price class (FR-009)"
  type        = string
  default     = "PriceClass_100" # US, Canada, Europe only
}

variable "origin_read_timeout" {
  description = "Origin read timeout in seconds (FR-003: 60s default, 180s requires quota increase)"
  type        = number
  default     = 60
}

variable "origin_keepalive_timeout" {
  description = "Origin keepalive timeout in seconds"
  type        = number
  default     = 60
}

variable "lambda_function_arn" {
  description = "SSE Lambda function ARN (for OAC permission — Feature 1256)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
