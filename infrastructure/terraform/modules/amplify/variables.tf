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
  description = "API Gateway endpoint URL for backend API calls"
  type        = string
}

variable "sse_lambda_url" {
  description = "SSE Lambda Function URL for real-time streaming"
  type        = string
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
