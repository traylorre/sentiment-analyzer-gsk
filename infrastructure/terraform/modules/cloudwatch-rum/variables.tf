variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "domain" {
  description = "Domain to monitor (e.g., dashboard.example.com or *.cloudfront.net)"
  type        = string
}

variable "allow_cookies" {
  description = "Allow RUM web client to set cookies for user sessions"
  type        = bool
  default     = true
}

variable "enable_xray" {
  description = "Enable X-Ray tracing from browser to backend"
  type        = bool
  default     = true
}

variable "session_sample_rate" {
  description = "Percentage of user sessions to collect (0.0 to 1.0)"
  type        = number
  default     = 1.0

  validation {
    condition     = var.session_sample_rate >= 0 && var.session_sample_rate <= 1
    error_message = "Session sample rate must be between 0.0 and 1.0."
  }
}

variable "telemetries" {
  description = "Types of telemetry to collect"
  type        = list(string)
  default     = ["errors", "performance", "http"]

  validation {
    condition     = alltrue([for t in var.telemetries : contains(["errors", "performance", "http"], t)])
    error_message = "Telemetries must be a subset of: errors, performance, http."
  }
}

variable "included_pages" {
  description = "Pages to include in monitoring (empty = all pages)"
  type        = list(string)
  default     = []
}

variable "excluded_pages" {
  description = "Pages to exclude from monitoring"
  type        = list(string)
  default     = []
}

variable "enable_cw_logs" {
  description = "Store RUM events in CloudWatch Logs for custom analysis"
  type        = bool
  default     = false
}

variable "enable_custom_events" {
  description = "Enable custom events for tracking specific user actions"
  type        = bool
  default     = true
}
