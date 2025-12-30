# AWS Amplify App Configuration
# Feature 1105: Next.js Frontend Migration via AWS Amplify SSR

# ===================================================================
# Amplify App
# ===================================================================

resource "aws_amplify_app" "frontend" {
  name       = "${var.environment}-sentiment-frontend"
  repository = var.github_repository

  # SSR mode for Next.js with middleware support
  platform = "WEB_COMPUTE"

  # GitHub access token for repo connection
  access_token = var.github_access_token

  # Build specification for monorepo
  build_spec = <<-EOT
    version: 1
    applications:
      - appRoot: frontend
        frontend:
          phases:
            preBuild:
              commands:
                - npm ci
            build:
              commands:
                - npm run build
          artifacts:
            baseDirectory: .next
            files:
              - '**/*'
          cache:
            paths:
              - node_modules/**/*
              - .next/cache/**/*
  EOT

  # Environment variables for Next.js
  environment_variables = {
    NEXT_PUBLIC_API_URL              = var.api_gateway_url
    NEXT_PUBLIC_SSE_URL              = var.sse_lambda_url
    NEXT_PUBLIC_COGNITO_USER_POOL_ID = var.cognito_user_pool_id
    NEXT_PUBLIC_COGNITO_CLIENT_ID    = var.cognito_client_id
    NEXT_PUBLIC_COGNITO_DOMAIN       = var.cognito_domain
    NEXT_PUBLIC_ENABLE_HAPTICS       = "true"
    AMPLIFY_MONOREPO_APP_ROOT        = "frontend"
    # Required for SSR
    _LIVE_UPDATES = "[{\"name\":\"Next.js version\",\"pkg\":\"next-version\",\"type\":\"internal\",\"version\":\"latest\"}]"
  }

  # Enable branch auto-detection
  enable_branch_auto_build = var.enable_auto_build

  # Custom rules - NO SPA fallback for SSR (Gap 2: 404-200 breaks Next.js middleware)
  # Only www redirect:

  # Redirect www to non-www (if custom domain is used)
  custom_rule {
    source = "https://www.<*>"
    status = "301"
    target = "https://<*>"
  }

  # IAM service role
  iam_service_role_arn = aws_iam_role.amplify_service.arn

  # Auto branch creation settings
  enable_auto_branch_creation = false

  tags = {
    Environment = var.environment
    Feature     = "1105-nextjs-migration"
    Component   = "amplify-frontend"
  }
}

# ===================================================================
# Amplify Branch (Main)
# ===================================================================

resource "aws_amplify_branch" "main" {
  app_id      = aws_amplify_app.frontend.id
  branch_name = var.branch_name

  # Stage configuration
  stage = var.environment == "prod" ? "PRODUCTION" : "DEVELOPMENT"

  # Enable auto-build on push
  enable_auto_build = var.enable_auto_build

  # Framework detection
  framework = "Next.js - SSR"

  # Enable notifications
  enable_notification = true

  # Pull request previews (disabled for main)
  enable_pull_request_preview = false

  tags = {
    Environment = var.environment
    Feature     = "1105-nextjs-migration"
    Component   = "amplify-branch"
  }
}
