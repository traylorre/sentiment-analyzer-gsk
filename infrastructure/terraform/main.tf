# Main Terraform Configuration for Sentiment Analyzer
# Regional Multi-AZ Architecture (region configured via aws_region variable)

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Backend configuration for persistent state
  # Resources created by infrastructure/terraform/bootstrap
  #
  # CRITICAL: Use partial backend configuration to separate dev/prod state
  # Initialize with: terraform init -backend-config=backend-dev.hcl
  #              or: terraform init -backend-config=backend-prod.hcl
  backend "s3" {
    # Values provided by backend-{env}.hcl files
    # region is passed via -backend-config="region=${AWS_REGION}" in CI/CD
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "sentiment-analyzer"
      Feature     = "001-interactive-dashboard-demo"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ===================================================================
# Module: Secrets Manager
# ===================================================================

module "secrets" {
  source = "./modules/secrets"

  environment         = var.environment
  rotation_lambda_arn = null # No rotation Lambda for Demo 1
}

# ===================================================================
# Module: Cognito User Pool (Feature 006)
# ===================================================================

module "cognito" {
  source = "./modules/cognito"

  environment   = var.environment
  domain_suffix = var.cognito_domain_suffix

  callback_urls = var.cognito_callback_urls
  logout_urls   = var.cognito_logout_urls

  # OAuth providers (configured via variables)
  enabled_identity_providers = var.cognito_identity_providers
  google_client_id           = var.google_oauth_client_id
  google_client_secret       = var.google_oauth_client_secret
  github_client_id           = var.github_oauth_client_id
  github_client_secret       = var.github_oauth_client_secret
}

# ===================================================================
# Module: CloudFront CDN (Feature 006)
# ===================================================================

module "cloudfront" {
  source = "./modules/cloudfront"

  environment    = var.environment
  account_suffix = data.aws_caller_identity.current.account_id

  # API Gateway integration
  api_gateway_domain = replace(module.api_gateway.api_endpoint, "https://", "")

  # Custom domain (optional)
  custom_domain       = var.cloudfront_custom_domain
  acm_certificate_arn = var.cloudfront_acm_certificate_arn

  depends_on = [module.api_gateway]
}

# ===================================================================
# Module: CloudWatch RUM (Feature 006)
# ===================================================================

module "cloudwatch_rum" {
  source = "./modules/cloudwatch-rum"

  environment = var.environment
  domain      = var.cloudfront_custom_domain != "" ? var.cloudfront_custom_domain : module.cloudfront.distribution_domain_name

  # RUM configuration
  allow_cookies       = true
  enable_xray         = true
  session_sample_rate = var.environment == "prod" ? 0.1 : 1.0 # 10% in prod, 100% in dev/preprod

  depends_on = [module.cloudfront]
}

# Data source for AWS account ID
data "aws_caller_identity" "current" {}

# ===================================================================
# Module: DynamoDB Table
# ===================================================================

module "dynamodb" {
  source = "./modules/dynamodb"

  environment   = var.environment
  aws_region    = var.aws_region
  enable_backup = var.environment == "preprod" ? false : true
}

# ===================================================================
# Lambda Functions
# ===================================================================

# S3 bucket for Lambda deployment packages
# BOOTSTRAP INFRASTRUCTURE: This bucket must be created manually before deployment.
# The promotion pipeline uploads Lambda packages to S3 *before* Terraform runs,
# so the bucket cannot be managed by Terraform.
#
# Manual creation (one-time setup):
#   aws s3api create-bucket --bucket preprod-sentiment-lambda-deployments --region $AWS_REGION
#   aws s3api put-bucket-versioning --bucket preprod-sentiment-lambda-deployments --versioning-configuration Status=Enabled
#   aws s3api put-bucket-public-access-block --bucket preprod-sentiment-lambda-deployments --block-public-acls=true --block-public-policy=true --ignore-public-acls=true --restrict-public-buckets=true
#
# resource "aws_s3_bucket" "lambda_deployments" {
#   bucket = "${var.environment}-sentiment-lambda-deployments"
#
#   tags = {
#     Name = "${var.environment}-sentiment-lambda-deployments"
#   }
# }
#
# resource "aws_s3_bucket_versioning" "lambda_deployments" {
#   bucket = aws_s3_bucket.lambda_deployments.id
#   versioning_configuration {
#     status = "Enabled"
#   }
# }
#
# # Block public access to Lambda deployment bucket
# resource "aws_s3_bucket_public_access_block" "lambda_deployments" {
#   bucket = aws_s3_bucket.lambda_deployments.id
#
#   block_public_acls       = true
#   block_public_policy     = true
#   ignore_public_acls      = true
#   restrict_public_buckets = true
# }

# Lambda naming
locals {
  ingestion_lambda_name = "${var.environment}-sentiment-ingestion"
  analysis_lambda_name  = "${var.environment}-sentiment-analysis"
  dashboard_lambda_name = "${var.environment}-sentiment-dashboard"
  metrics_lambda_name   = "${var.environment}-sentiment-metrics"

  # S3 bucket for ML model storage
  model_s3_bucket = "sentiment-analyzer-models-218795110243"

  # S3 bucket for ticker cache data (Feature 006)
  ticker_cache_bucket = "${var.environment}-sentiment-ticker-cache-${data.aws_caller_identity.current.account_id}"
}

# ===================================================================
# S3 Bucket for Ticker Cache Data (Feature 006)
# ===================================================================
# Contains ~8K US stock symbols for autocomplete and validation
# Loaded by Lambda at cold start

resource "aws_s3_bucket" "ticker_cache" {
  bucket = local.ticker_cache_bucket

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "ticker-cache"
  }
}

resource "aws_s3_bucket_versioning" "ticker_cache" {
  bucket = aws_s3_bucket.ticker_cache.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "ticker_cache" {
  bucket = aws_s3_bucket.ticker_cache.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ticker_cache" {
  bucket = aws_s3_bucket.ticker_cache.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Upload initial ticker cache data
resource "aws_s3_object" "ticker_cache_symbols" {
  bucket       = aws_s3_bucket.ticker_cache.id
  key          = "ticker-cache/us-symbols.json"
  source       = "${path.module}/../data/us-symbols.json"
  content_type = "application/json"
  etag         = filemd5("${path.module}/../data/us-symbols.json")
}

# ===================================================================
# Module: Ingestion Lambda (T051)
# ===================================================================

module "ingestion_lambda" {
  source = "./modules/lambda"

  function_name = local.ingestion_lambda_name
  description   = "Fetches articles from financial news APIs and stores in DynamoDB"
  iam_role_arn  = module.iam.ingestion_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = "${var.environment}-sentiment-lambda-deployments"
  s3_key        = "ingestion/lambda.zip"

  # Force update when package changes (git SHA triggers redeployment)
  source_code_hash = var.lambda_package_version

  # Resource configuration per task spec
  memory_size          = 512
  timeout              = 60
  reserved_concurrency = 1

  # X-Ray tracing (Feature 006 - Day 1 mandatory)
  tracing_mode = "Active"

  # Environment variables
  environment_variables = {
    WATCH_TAGS         = var.watch_tags
    DYNAMODB_TABLE     = module.dynamodb.table_name
    SNS_TOPIC_ARN      = module.sns.topic_arn
    NEWSAPI_SECRET_ARN = module.secrets.newsapi_secret_arn
    TIINGO_SECRET_ARN  = module.secrets.tiingo_secret_arn
    FINNHUB_SECRET_ARN = module.secrets.finnhub_secret_arn
    ENVIRONMENT        = var.environment
    MODEL_VERSION      = var.model_version
  }

  # Logging
  log_retention_days = var.environment == "prod" ? 90 : 30

  # Alarms
  create_error_alarm    = true
  error_alarm_threshold = 5
  alarm_actions         = [module.monitoring.alarm_topic_arn]

  tags = {
    Lambda = "ingestion"
  }

  depends_on = [module.iam, module.sns]
}

# ===================================================================
# Module: Analysis Lambda (T052)
# ===================================================================

module "analysis_lambda" {
  source = "./modules/lambda"

  function_name = local.analysis_lambda_name
  description   = "Performs sentiment analysis using DistilBERT model from S3"
  iam_role_arn  = module.iam.analysis_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = "${var.environment}-sentiment-lambda-deployments"
  s3_key        = "analysis/lambda.zip"

  # Force update when package changes (git SHA triggers redeployment)
  source_code_hash = var.lambda_package_version

  # Resource configuration per task spec
  memory_size          = 1024
  timeout              = 30
  reserved_concurrency = 5

  # X-Ray tracing (Feature 006 - Day 1 mandatory)
  tracing_mode = "Active"

  # Ephemeral storage for ML model (~250MB extracted, 3GB for headroom)
  ephemeral_storage_size = 3072 # 3GB

  # Lambda layer for DistilBERT model (deprecated - now using S3)
  layers = var.model_layer_arns

  # Environment variables
  environment_variables = {
    DYNAMODB_TABLE  = module.dynamodb.table_name
    MODEL_S3_BUCKET = local.model_s3_bucket
    MODEL_VERSION   = var.model_version
    ENVIRONMENT     = var.environment
  }

  # Dead letter queue
  dlq_arn = module.sns.dlq_arn

  # Logging
  log_retention_days = var.environment == "prod" ? 90 : 30

  # Alarms
  create_error_alarm       = true
  error_alarm_threshold    = 5
  create_duration_alarm    = true
  duration_alarm_threshold = 5000 # 5 seconds
  alarm_actions            = [module.monitoring.alarm_topic_arn]

  tags = {
    Lambda = "analysis"
  }

  depends_on = [module.iam]
}

# ===================================================================
# Module: Dashboard Lambda (T053)
# ===================================================================

module "dashboard_lambda" {
  source = "./modules/lambda"

  function_name = local.dashboard_lambda_name
  description   = "Serves dashboard UI and API endpoints"
  iam_role_arn  = module.iam.dashboard_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = "${var.environment}-sentiment-lambda-deployments"
  s3_key        = "dashboard/lambda.zip"

  # Force update when package changes (git SHA triggers redeployment)
  source_code_hash = var.lambda_package_version

  # Resource configuration per task spec
  memory_size          = 1024
  timeout              = 60
  reserved_concurrency = 10

  # X-Ray tracing (Feature 006 - Day 1 mandatory)
  tracing_mode = "Active"

  # Environment variables
  # NOTE: FIS template IDs removed to break circular dependency with chaos module.
  # The chaos module needs Lambda ARNs, and Lambda needs chaos outputs = cycle.
  # Dashboard can look up FIS templates at runtime via AWS SDK if needed.
  environment_variables = {
    DYNAMODB_TABLE               = module.dynamodb.table_name
    API_KEY                      = "" # Will be fetched from Secrets Manager at runtime
    DASHBOARD_API_KEY_SECRET_ARN = module.secrets.dashboard_api_key_secret_arn
    SENDGRID_SECRET_ARN          = module.secrets.sendgrid_secret_arn
    HCAPTCHA_SECRET_ARN          = module.secrets.hcaptcha_secret_arn
    COGNITO_USER_POOL_ID         = module.cognito.user_pool_id
    COGNITO_CLIENT_ID            = module.cognito.client_id
    TICKER_CACHE_BUCKET          = aws_s3_bucket.ticker_cache.id
    SSE_POLL_INTERVAL            = "5"
    ENVIRONMENT                  = var.environment
    CHAOS_EXPERIMENTS_TABLE      = module.dynamodb.chaos_experiments_table_name
    CORS_ORIGINS                 = join(",", var.cors_allowed_origins)
  }

  # Function URL with CORS
  create_function_url    = true
  function_url_auth_type = "NONE"
  function_url_cors = {
    allow_credentials = false
    allow_headers     = ["content-type", "authorization", "x-api-key"]
    allow_methods     = ["GET"] # AWS handles OPTIONS preflight automatically; not in allowed values
    allow_origins     = length(var.cors_allowed_origins) > 0 ? var.cors_allowed_origins : ["*"]
    expose_headers    = []
    max_age           = 86400
  }

  # Logging
  log_retention_days = var.environment == "prod" ? 90 : 30

  # Alarms
  create_error_alarm    = true
  error_alarm_threshold = 10
  alarm_actions         = [module.monitoring.alarm_topic_arn]

  tags = {
    Lambda = "dashboard"
  }

  depends_on = [module.iam]
}

# ===================================================================
# Module: Metrics Lambda (TD-011 - Operational Monitoring)
# ===================================================================

module "metrics_lambda" {
  source = "./modules/lambda"

  function_name = "${var.environment}-sentiment-metrics"
  description   = "Monitors for stuck items and emits CloudWatch metrics"
  iam_role_arn  = module.iam.metrics_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = "${var.environment}-sentiment-lambda-deployments"
  s3_key        = "metrics/lambda.zip"

  # Force update when package changes (git SHA triggers redeployment)
  source_code_hash = var.lambda_package_version

  # Lightweight Lambda - minimal resources needed
  memory_size          = 128
  timeout              = 30
  reserved_concurrency = 1 # Only one instance needed

  # X-Ray tracing (Feature 006 - Day 1 mandatory)
  tracing_mode = "Active"

  # Environment variables
  environment_variables = {
    DYNAMODB_TABLE = module.dynamodb.table_name
    ENVIRONMENT    = var.environment
  }

  # No Function URL needed - triggered by EventBridge only
  create_function_url = false

  # Logging
  log_retention_days = var.environment == "prod" ? 90 : 14

  # Alarms
  create_error_alarm    = true
  error_alarm_threshold = 5
  alarm_actions         = [module.monitoring.alarm_topic_arn]

  tags = {
    Lambda = "metrics"
  }

  depends_on = [module.iam]
}

# ===================================================================
# Module: API Gateway (Dashboard Rate Limiting - P0 Security)
# ===================================================================

module "api_gateway" {
  source = "./modules/api_gateway"

  environment          = var.environment
  lambda_function_name = module.dashboard_lambda.function_name
  lambda_invoke_arn    = module.dashboard_lambda.invoke_arn
  stage_name           = "v1"

  # Rate limiting configuration (P0-1 mitigation: prevent budget exhaustion)
  rate_limit  = 100 # Requests per second (steady state)
  burst_limit = 200 # Concurrent requests (burst)

  # CloudWatch logging
  log_retention_days  = var.environment == "prod" ? 90 : 30
  enable_xray_tracing = true

  # CloudWatch alarms
  create_alarms       = true
  alarm_actions       = [module.monitoring.alarm_topic_arn]
  error_4xx_threshold = 100  # Alert after 100 client errors in 5 minutes
  error_5xx_threshold = 10   # Alert after 10 server errors in 5 minutes
  latency_threshold   = 5000 # Alert if p90 latency > 5 seconds

  tags = {
    Component = "api-gateway"
    Security  = "rate-limiting"
  }

  depends_on = [module.dashboard_lambda]
}

# ===================================================================
# Module: SNS Topic (for Analysis Triggers)
# ===================================================================

module "sns" {
  source = "./modules/sns"

  environment = var.environment

  # Zero-Trust: Restrict SNS topic policy to specific Ingestion Lambda role
  ingestion_lambda_role_arn = module.iam.ingestion_lambda_role_arn

  # Subscription created separately below to avoid circular dependency
  # (ingestion needs topic_arn, but subscription needs analysis lambda)
  create_subscription = false
}

# SNS subscription for Analysis Lambda
# Created after both SNS and Analysis Lambda modules
resource "aws_sns_topic_subscription" "analysis" {
  topic_arn = module.sns.topic_arn
  protocol  = "lambda"
  endpoint  = module.analysis_lambda.function_arn
}

# Allow SNS to invoke Analysis Lambda
resource "aws_lambda_permission" "analysis_sns" {
  statement_id  = "AllowSNSInvoke"
  action        = "lambda:InvokeFunction"
  function_name = module.analysis_lambda.function_name
  principal     = "sns.amazonaws.com"
  source_arn    = module.sns.topic_arn
}

# ===================================================================
# Module: IAM Roles (for Lambda Functions)
# ===================================================================

module "iam" {
  source = "./modules/iam"

  environment                  = var.environment
  dynamodb_table_arn           = module.dynamodb.table_arn
  newsapi_secret_arn           = module.secrets.newsapi_secret_arn
  dashboard_api_key_secret_arn = module.secrets.dashboard_api_key_secret_arn
  analysis_topic_arn           = module.sns.topic_arn
  dlq_arn                      = module.sns.dlq_arn
  model_s3_bucket_arn          = "arn:aws:s3:::${local.model_s3_bucket}"
  chaos_experiments_table_arn  = module.dynamodb.chaos_experiments_table_arn
  ticker_cache_bucket_arn      = aws_s3_bucket.ticker_cache.arn
}

# ===================================================================
# Module: EventBridge Schedules
# ===================================================================

module "eventbridge" {
  source = "./modules/eventbridge"

  environment                    = var.environment
  ingestion_lambda_arn           = module.ingestion_lambda.function_arn
  ingestion_lambda_function_name = module.ingestion_lambda.function_name

  # Metrics Lambda (TD-011) - monitors for stuck items
  create_metrics_schedule      = true
  metrics_lambda_arn           = module.metrics_lambda.function_arn
  metrics_lambda_function_name = module.metrics_lambda.function_name

  depends_on = [module.ingestion_lambda, module.metrics_lambda]
}

# ===================================================================
# Module: Monitoring & Alarms (On-Call SOP)
# ===================================================================

module "monitoring" {
  source = "./modules/monitoring"

  environment          = var.environment
  alarm_email          = var.alarm_email
  monthly_budget_limit = var.monthly_budget_limit
}

# ===================================================================
# Module: Chaos Testing (AWS FIS)
# ===================================================================
# Uses Lambda fault injection (latency/errors) to test system resilience.
# NOTE: DynamoDB doesn't support API-level FIS fault injection.
#       FIS only supports global table replication pause or VPC network disruption.
#       Our Lambdas aren't VPC-attached, so we test at the Lambda layer.

module "chaos" {
  source = "./modules/chaos"

  environment = var.environment
  # DISABLED: Terraform AWS provider doesn't support Lambda FIS target key "Functions" yet
  # See: https://github.com/hashicorp/terraform-provider-aws/issues/41208
  # Re-enable when provider version supports aws:lambda:invocation-add-delay targets
  enable_chaos_testing = false # var.environment == "preprod"

  # Lambda targets for chaos experiments
  lambda_arns = [
    module.ingestion_lambda.function_arn,
    module.analysis_lambda.function_arn,
    module.dashboard_lambda.function_arn
  ]

  # Kill switch - stops experiments if Lambda errors spike
  lambda_error_alarm_arn = module.monitoring.analysis_errors_alarm_arn

  # Deprecated - kept for backwards compatibility
  dynamodb_table_arn       = module.dynamodb.table_arn
  write_throttle_alarm_arn = module.dynamodb.cloudwatch_alarm_write_throttles_arn

  depends_on = [module.ingestion_lambda, module.analysis_lambda, module.dashboard_lambda, module.monitoring]
}

# ===================================================================
# Outputs
# ===================================================================

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = module.dynamodb.table_name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = module.dynamodb.table_arn
}

output "newsapi_secret_arn" {
  description = "ARN of the NewsAPI secret"
  value       = module.secrets.newsapi_secret_arn
}

output "dashboard_api_key_secret_arn" {
  description = "ARN of the Dashboard API key secret"
  value       = module.secrets.dashboard_api_key_secret_arn
}

output "gsi_by_sentiment" {
  description = "Name of the by_sentiment GSI"
  value       = module.dynamodb.gsi_by_sentiment_name
}

output "gsi_by_tag" {
  description = "Name of the by_tag GSI"
  value       = module.dynamodb.gsi_by_tag_name
}

output "gsi_by_status" {
  description = "Name of the by_status GSI"
  value       = module.dynamodb.gsi_by_status_name
}

output "alarm_topic_arn" {
  description = "ARN of the SNS topic for alarm notifications"
  value       = module.monitoring.alarm_topic_arn
}

output "alarm_names" {
  description = "List of all CloudWatch alarm names"
  value       = module.monitoring.alarm_names
}

# Lambda outputs
output "sns_topic_arn" {
  description = "ARN of the SNS topic"
  value       = module.sns.topic_arn
}

output "ingestion_lambda_arn" {
  description = "ARN of the Ingestion Lambda function"
  value       = module.ingestion_lambda.function_arn
}

output "analysis_lambda_arn" {
  description = "ARN of the Analysis Lambda function"
  value       = module.analysis_lambda.function_arn
}

output "dashboard_lambda_arn" {
  description = "ARN of the Dashboard Lambda function"
  value       = module.dashboard_lambda.function_arn
}

output "dashboard_function_url" {
  description = "URL of the Dashboard Lambda Function URL (legacy, use API Gateway URL)"
  value       = module.dashboard_lambda.function_url
}

output "dashboard_api_url" {
  description = "URL of the Dashboard API Gateway (recommended for production)"
  value       = module.api_gateway.api_endpoint
}

output "api_gateway_id" {
  description = "ID of the Dashboard API Gateway"
  value       = module.api_gateway.api_id
}

output "lambda_deployment_bucket" {
  description = "S3 bucket for Lambda deployment packages"
  value       = "${var.environment}-sentiment-lambda-deployments"
}

# EventBridge outputs
output "ingestion_schedule_arn" {
  description = "ARN of the ingestion EventBridge rule"
  value       = module.eventbridge.ingestion_schedule_arn
}

# Chaos Testing outputs
output "fis_lambda_latency_template_id" {
  description = "ID of the FIS experiment template for Lambda latency injection"
  value       = module.chaos.fis_lambda_latency_template_id
}

output "fis_lambda_error_template_id" {
  description = "ID of the FIS experiment template for Lambda error injection"
  value       = module.chaos.fis_lambda_error_template_id
}

output "fis_execution_role_arn" {
  description = "ARN of the IAM role used by FIS to execute experiments"
  value       = module.chaos.fis_execution_role_arn
}

# Deprecated output - kept for backwards compatibility
output "fis_dynamodb_throttle_template_id" {
  description = "DEPRECATED: DynamoDB throttling not supported by FIS"
  value       = ""
}

# ===================================================================
# Feature 006 Outputs
# ===================================================================

# Cognito outputs
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = module.cognito.client_id
}

output "cognito_hosted_ui_url" {
  description = "URL for Cognito hosted UI login"
  value       = module.cognito.hosted_ui_url
}

output "cognito_oauth_issuer" {
  description = "OAuth issuer URL for token validation"
  value       = module.cognito.oauth_issuer
}

# CloudFront outputs
output "cloudfront_distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = module.cloudfront.distribution_id
}

output "cloudfront_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = module.cloudfront.distribution_domain_name
}

output "dashboard_s3_bucket" {
  description = "S3 bucket for dashboard static assets"
  value       = module.cloudfront.s3_bucket_name
}

output "dashboard_url" {
  description = "URL for accessing the dashboard via CloudFront"
  value       = module.cloudfront.dashboard_url
}

# CloudWatch RUM outputs
output "rum_app_monitor_id" {
  description = "ID of the CloudWatch RUM App Monitor"
  value       = module.cloudwatch_rum.app_monitor_id
}

output "rum_identity_pool_id" {
  description = "Cognito Identity Pool ID for RUM"
  value       = module.cloudwatch_rum.identity_pool_id
}

# Feature 006 secrets
output "tiingo_secret_arn" {
  description = "ARN of the Tiingo API secret"
  value       = module.secrets.tiingo_secret_arn
}

output "finnhub_secret_arn" {
  description = "ARN of the Finnhub API secret"
  value       = module.secrets.finnhub_secret_arn
}

output "sendgrid_secret_arn" {
  description = "ARN of the SendGrid API secret"
  value       = module.secrets.sendgrid_secret_arn
}

output "hcaptcha_secret_arn" {
  description = "ARN of the hCaptcha secret"
  value       = module.secrets.hcaptcha_secret_arn
}

# Ticker cache outputs
output "ticker_cache_bucket" {
  description = "S3 bucket for ticker cache data"
  value       = aws_s3_bucket.ticker_cache.id
}

output "ticker_cache_bucket_arn" {
  description = "ARN of the ticker cache S3 bucket"
  value       = aws_s3_bucket.ticker_cache.arn
}
