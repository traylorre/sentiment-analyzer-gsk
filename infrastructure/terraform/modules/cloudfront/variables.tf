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
  # Updated per 090-security-first-burndown to include CDN domains for Chart.js, DaisyUI, and Tailwind
  default = "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdn.tailwindcss.com https://hcaptcha.com https://*.hcaptcha.com; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self' https://*.amazonaws.com https://*.amazoncognito.com; frame-src https://hcaptcha.com https://*.hcaptcha.com; frame-ancestors 'none';"
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

# ===================================================================
# Cost Controls (FR-023)
# ===================================================================

variable "price_class_override" {
  description = "Override the default price class. Empty uses default (PriceClass_100 for non-prod, PriceClass_All for prod)"
  type        = string
  default     = ""

  validation {
    condition = var.price_class_override == "" || contains([
      "PriceClass_100", # US, Canada, Europe
      "PriceClass_200", # + Asia, Middle East, Africa
      "PriceClass_All"  # All edge locations
    ], var.price_class_override)
    error_message = "price_class_override must be empty or one of: PriceClass_100, PriceClass_200, PriceClass_All"
  }
}
