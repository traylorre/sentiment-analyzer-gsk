variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "account_suffix" {
  description = "AWS account ID suffix for globally unique bucket naming"
  type        = string
}

variable "api_gateway_domain" {
  description = "API Gateway domain for /api/* routes (optional)"
  type        = string
  default     = ""
}

variable "custom_domain" {
  description = "Custom domain for CloudFront distribution (optional)"
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain (required if custom_domain is set)"
  type        = string
  default     = ""
}

variable "content_security_policy" {
  description = "Content-Security-Policy header value"
  type        = string
  default     = "default-src 'self'; script-src 'self' 'unsafe-inline' https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com; frame-src https://hcaptcha.com https://*.hcaptcha.com;"
}

variable "enable_logging" {
  description = "Enable CloudFront access logging"
  type        = bool
  default     = false
}

variable "logging_bucket" {
  description = "S3 bucket for CloudFront access logs (required if enable_logging is true)"
  type        = string
  default     = ""
}
