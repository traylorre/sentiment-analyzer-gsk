# CloudWatch RUM (Real User Monitoring) for Feature 006
#
# Provides client-side analytics and error tracking for the dashboard.
# Tracks page load times, JavaScript errors, and user interactions.

# ===================================================================
# CloudWatch RUM App Monitor
# ===================================================================

resource "aws_rum_app_monitor" "dashboard" {
  name   = "${var.environment}-sentiment-dashboard"
  domain = var.domain

  # App monitor configuration
  app_monitor_configuration {
    allow_cookies       = var.allow_cookies
    enable_xray         = var.enable_xray
    guest_role_arn      = aws_iam_role.rum_guest.arn
    identity_pool_id    = aws_cognito_identity_pool.rum.id
    session_sample_rate = var.session_sample_rate

    # Telemetry types to collect
    telemetries = var.telemetries

    # Included/excluded pages (optional)
    included_pages = var.included_pages
    excluded_pages = var.excluded_pages
  }

  # Store events in CloudWatch Logs (for custom analysis)
  cw_log_enabled = var.enable_cw_logs

  # Custom events (for tracking specific user actions)
  custom_events {
    status = var.enable_custom_events ? "ENABLED" : "DISABLED"
  }

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "rum"
  }
}

# ===================================================================
# Cognito Identity Pool for RUM
# ===================================================================

resource "aws_cognito_identity_pool" "rum" {
  identity_pool_name               = "${var.environment}-sentiment-rum"
  allow_unauthenticated_identities = true
  allow_classic_flow               = false

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "rum-identity"
  }
}

# ===================================================================
# IAM Role for RUM Guest Users
# ===================================================================

resource "aws_iam_role" "rum_guest" {
  name = "${var.environment}-sentiment-rum-guest"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.rum.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "unauthenticated"
          }
        }
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "rum-iam"
  }
}

resource "aws_iam_role_policy" "rum_guest" {
  name = "${var.environment}-sentiment-rum-guest-policy"
  role = aws_iam_role.rum_guest.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rum:PutRumEvents"
        ]
        Resource = aws_rum_app_monitor.dashboard.arn
      }
    ]
  })
}

# ===================================================================
# Identity Pool Role Attachment
# ===================================================================

resource "aws_cognito_identity_pool_roles_attachment" "rum" {
  identity_pool_id = aws_cognito_identity_pool.rum.id

  roles = {
    unauthenticated = aws_iam_role.rum_guest.arn
  }
}
