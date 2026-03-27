# WAF v2 Module Variables
# Feature 1254: Per-IP rate limiting, SQLi, XSS, bot detection
# FR-009: Reusable for API Gateway (REGIONAL) and CloudFront (CLOUDFRONT)

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "scope" {
  description = "WAF scope: REGIONAL (API Gateway) or CLOUDFRONT"
  type        = string
  default     = "REGIONAL"

  validation {
    condition     = contains(["REGIONAL", "CLOUDFRONT"], var.scope)
    error_message = "scope must be REGIONAL or CLOUDFRONT"
  }
}

variable "resource_arn" {
  description = "ARN of the resource to associate with (API Gateway stage ARN or CloudFront distribution ARN)"
  type        = string
}

variable "rate_limit" {
  description = "Per-IP request limit per 5-minute window (FR-002)"
  type        = number
  default     = 2000
}

variable "enable_bot_control" {
  description = "Enable AWS Bot Control managed rule group (FR-005)"
  type        = bool
  default     = true
}

variable "bot_control_action" {
  description = "Action for bot control: COUNT (monitoring) or BLOCK"
  type        = string
  default     = "COUNT"

  validation {
    condition     = contains(["COUNT", "BLOCK"], var.bot_control_action)
    error_message = "bot_control_action must be COUNT or BLOCK"
  }
}

variable "alarm_actions" {
  description = "SNS topic ARNs for WAF alarm notifications (FR-007)"
  type        = list(string)
  default     = []
}

variable "blocked_requests_threshold" {
  description = "Alarm threshold: blocked requests in 5 minutes (FR-007)"
  type        = number
  default     = 500
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = {}
}
