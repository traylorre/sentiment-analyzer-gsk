variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "domain_suffix" {
  description = "Unique suffix for Cognito domain (must be globally unique)"
  type        = string
}

variable "callback_urls" {
  description = "List of allowed callback URLs for OAuth redirects"
  type        = list(string)
  default     = ["http://localhost:3000/auth/callback"]
}

variable "logout_urls" {
  description = "List of allowed logout redirect URLs"
  type        = list(string)
  default     = ["http://localhost:3000"]
}

variable "enabled_identity_providers" {
  description = "List of enabled identity providers (Google, GitHub)"
  type        = list(string)
  default     = []
}

# Google OAuth credentials
variable "google_client_id" {
  description = "Google OAuth client ID (from Google Cloud Console)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}

# GitHub OAuth credentials
variable "github_client_id" {
  description = "GitHub OAuth client ID (from GitHub Developer Settings)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "github_client_secret" {
  description = "GitHub OAuth client secret"
  type        = string
  default     = ""
  sensitive   = true
}
