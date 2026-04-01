# AWS Amplify Module Variables
# Feature 1105: Next.js Frontend Migration via AWS Amplify SSR

variable "environment" {
  description = "Environment name (dev, preprod, prod)"
  type        = string
}

variable "github_repository" {
  description = "GitHub repository URL (e.g., https://github.com/owner/repo)"
  type        = string
}

variable "api_gateway_url" {
  description = "API Gateway endpoint URL for backend API calls (Feature 1253: primary API endpoint with Cognito auth)"
  type        = string

  validation {
    condition     = var.api_gateway_url != ""
    error_message = "api_gateway_url is required. The Function URL fallback was removed in Feature 1297 because Function URLs are IAM-protected (Feature 1256) and would silently return 403 to the frontend."
  }
}

variable "sse_cloudfront_url" {
  description = "CloudFront URL for SSE streaming (Feature 1255: primary SSE endpoint with WAF + Shield)"
  type        = string

  validation {
    condition     = var.sse_cloudfront_url != ""
    error_message = "sse_cloudfront_url is required. The SSE Function URL fallback was removed in Feature 1297 because Function URLs are IAM-protected (Feature 1256) and would silently return 403 to the frontend."
  }
}

variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for authentication"
  type        = string
}

variable "cognito_client_id" {
  description = "Cognito Client ID for authentication"
  type        = string
}

variable "cognito_domain" {
  description = "Cognito domain for hosted UI"
  type        = string
}

variable "branch_name" {
  description = "Git branch to deploy from"
  type        = string
  default     = "main"
}

variable "enable_auto_build" {
  description = "Enable automatic builds on push to branch"
  type        = bool
  default     = true
}

variable "github_token_secret_name" {
  description = "Name of the Secrets Manager secret containing GitHub PAT for Amplify"
  type        = string
}
