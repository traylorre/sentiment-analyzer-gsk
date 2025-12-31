# Cognito User Pool for Feature 006: Financial News Sentiment Dashboard
#
# Authentication options:
# 1. Magic link email (custom Lambda trigger)
# 2. Google OAuth (social identity provider)
# 3. GitHub OAuth (social identity provider)

# ===================================================================
# User Pool Configuration
# ===================================================================

resource "aws_cognito_user_pool" "main" {
  name = "${var.environment}-sentiment-users"

  # Username configuration
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Password policy (for OAuth users, passwords aren't used directly)
  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  # Account recovery via email
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User attributes
  schema {
    name                     = "email"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = true
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 5
      max_length = 256
    }
  }

  # Custom attribute for anonymous session migration
  schema {
    name                     = "anonymous_session_id"
    attribute_data_type      = "String"
    mutable                  = true
    required                 = false
    developer_only_attribute = false

    string_attribute_constraints {
      min_length = 0
      max_length = 64
    }
  }

  # MFA configuration (optional for users)
  mfa_configuration = "OPTIONAL"
  software_token_mfa_configuration {
    enabled = true
  }

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # Device tracking
  device_configuration {
    challenge_required_on_new_device      = false
    device_only_remembered_on_user_prompt = true
  }

  # User pool add-ons
  user_pool_add_ons {
    advanced_security_mode = var.environment == "prod" ? "ENFORCED" : "AUDIT"
  }

  # Deletion protection
  deletion_protection = var.environment == "prod" ? "ACTIVE" : "INACTIVE"

  tags = {
    Name        = "${var.environment}-sentiment-users" # Required for CI IAM policy condition
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "authentication"
  }
}

# ===================================================================
# User Pool Client (Dashboard Application)
# ===================================================================

resource "aws_cognito_user_pool_client" "dashboard" {
  name         = "${var.environment}-sentiment-dashboard-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Token configuration
  access_token_validity  = 1  # hours
  id_token_validity      = 1  # hours
  refresh_token_validity = 30 # days

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  # Prevent client secret (for public clients like SPAs)
  generate_secret = false

  # OAuth configuration
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  callback_urls                        = var.callback_urls
  logout_urls                          = var.logout_urls
  supported_identity_providers         = concat(["COGNITO"], var.enabled_identity_providers)

  # Explicit auth flows
  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_CUSTOM_AUTH" # For magic link flow
  ]

  # Security settings
  prevent_user_existence_errors = "ENABLED"
  enable_token_revocation       = true

  # Read/write attributes
  read_attributes  = ["email", "email_verified", "custom:anonymous_session_id"]
  write_attributes = ["email", "custom:anonymous_session_id"]

  # Gap 3: Ignore callback/logout URLs to break circular dependency with Amplify
  # These URLs are patched by terraform_data after Amplify URL is known
  lifecycle {
    ignore_changes = [callback_urls, logout_urls]
  }
}

# ===================================================================
# User Pool Domain (for hosted UI and OAuth redirects)
# ===================================================================

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.environment}-sentiment-${var.domain_suffix}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# ===================================================================
# Resource Server (API scopes)
# ===================================================================

resource "aws_cognito_resource_server" "api" {
  identifier   = "sentiment-api"
  name         = "Sentiment Analyzer API"
  user_pool_id = aws_cognito_user_pool.main.id

  scope {
    scope_name        = "read:config"
    scope_description = "Read user configurations"
  }

  scope {
    scope_name        = "write:config"
    scope_description = "Create and update configurations"
  }

  scope {
    scope_name        = "read:alerts"
    scope_description = "Read alert rules"
  }

  scope {
    scope_name        = "write:alerts"
    scope_description = "Create and update alert rules"
  }
}
