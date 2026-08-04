# AWS Amplify App Configuration
# Feature 1105: Next.js Frontend Migration via AWS Amplify SSR

# ===================================================================
# GitHub Token from Secrets Manager
# ===================================================================
# The token must be pre-provisioned in Secrets Manager before Terraform runs.
# This breaks the chicken-and-egg problem: we read the token at plan time,
# not via a provisioner that runs after creation.

data "aws_secretsmanager_secret_version" "github_token" {
  secret_id = var.github_token_secret_name
}

locals {
  github_token = jsondecode(data.aws_secretsmanager_secret_version.github_token.secret_string)["token"]
}

# ===================================================================
# Amplify App
# ===================================================================

resource "aws_amplify_app" "frontend" {
  name = "${var.environment}-sentiment-frontend"

  # Repository connection with token from Secrets Manager
  # Feature 1106: Token bootstrap via data source (not provisioner)
  repository   = var.github_repository
  access_token = local.github_token

  # SSR mode for Next.js with middleware support
  platform = "WEB_COMPUTE"

  # Build specification for monorepo
  #
  # The Node version is pinned here because nothing else pins it. The `node-version`
  # entries in .github/workflows are test runners; no workflow runs `npm run build`,
  # so this buildspec is the only place the production bundle is built. Without
  # `nvm use`, the build silently takes whatever Node the Amplify image defaults to,
  # and that default moves without notice.
  #
  # Keep this in step with frontend/.nvmrc and the `engines` field in
  # frontend/package.json. 20 is the floor Next 16 requires (>=20.9) and runs the
  # current Next 14.2.35, so it holds across the pending frontend major.
  build_spec = <<-EOT
    version: 1
    applications:
      - appRoot: frontend
        frontend:
          phases:
            preBuild:
              commands:
                - nvm install 20
                - nvm use 20
                - node --version
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
  # Feature 1253: API Gateway is the sole API endpoint (Cognito auth + rate limiting + WAF)
  # Feature 1255: CloudFront is the sole SSE endpoint (WAF + Shield Standard)
  # Feature 1297: Removed Function URL fallbacks — they are IAM-protected (Feature 1256)
  # and would silently return 403 to the frontend.
  environment_variables = {
    NEXT_PUBLIC_API_URL              = var.api_gateway_url
    NEXT_PUBLIC_SSE_URL              = var.sse_cloudfront_url
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

  # NOTE: repository and access_token are now set directly from Secrets Manager
  # data source (Feature 1106). No lifecycle ignore needed - token is read at
  # plan time, not patched post-creation.
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
