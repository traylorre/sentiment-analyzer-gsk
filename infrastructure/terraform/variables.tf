# Terraform Variables

variable "environment" {
  description = "Environment name (dev, preprod, or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "preprod", "prod"], var.environment)
    error_message = "Environment must be one of: dev, preprod, prod."
  }
}

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  # No default - region must be explicitly provided
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
  description = "Sentiment model version (semantic version like v1.0.0 or git SHA like a1b2c3d)"
  type        = string
  default     = "v1.0.0"
  validation {
    condition     = can(regex("^v\\d+\\.\\d+\\.\\d+$", var.model_version)) || can(regex("^[0-9a-fA-F]{7}$", var.model_version))
    error_message = "Model version must be semantic versioning (e.g., v1.0.0) or git SHA (e.g., a1b2c3d or A1B2C3D)."
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

variable "cors_allowed_origins" {
  description = "List of allowed CORS origins for the dashboard Lambda. Use specific domains in production."
  type        = list(string)
  default     = []
  validation {
    condition     = length(var.cors_allowed_origins) == 0 || !contains(var.cors_allowed_origins, "*")
    error_message = "Wildcard '*' is not allowed in cors_allowed_origins. Use specific domain names."
  }
}

variable "lambda_package_version" {
  description = "Version identifier for Lambda packages (git SHA). Used to force Lambda updates when packages change."
  type        = string
  default     = "initial"
}

# ===================================================================
# Feature 006: Cognito Variables
# ===================================================================

variable "cognito_domain_suffix" {
  description = "Unique suffix for Cognito domain (must be globally unique)"
  type        = string
  default     = "218795110243" # AWS account ID as default
}

variable "cognito_callback_urls" {
  description = "List of allowed callback URLs for OAuth redirects"
  type        = list(string)
  default     = ["http://localhost:3000/auth/callback"]
}

variable "cognito_logout_urls" {
  description = "List of allowed logout redirect URLs"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "cognito_identity_providers" {
  description = "List of enabled identity providers (Google, GitHub)"
  type        = list(string)
  default     = []
}

variable "google_oauth_client_id" {
  description = "Google OAuth client ID (from Google Cloud Console)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_oauth_client_secret" {
  description = "Google OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_oauth_client_id" {
  description = "GitHub OAuth client ID (from GitHub Developer Settings)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_oauth_client_secret" {
  description = "GitHub OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

# ===================================================================
# Feature 006: CloudFront Variables
# ===================================================================

variable "cloudfront_custom_domain" {
  description = "Custom domain for CloudFront distribution (optional)"
  type        = string
  default     = ""
}

variable "cloudfront_acm_certificate_arn" {
  description = "ACM certificate ARN for custom domain (required if custom_domain is set)"
  type        = string
  default     = ""
}

# ===================================================================
# Feature 006: Notification Variables
# ===================================================================

variable "notification_from_email" {
  description = "From email address for notifications (must be verified in SendGrid)"
  type        = string
  default     = "noreply@sentiment-analyzer.com"
}
