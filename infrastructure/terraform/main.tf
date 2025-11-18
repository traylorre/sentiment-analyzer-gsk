# Main Terraform Configuration for Sentiment Analyzer
# Regional Multi-AZ Architecture (us-east-1)

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
  # IMPORTANT: After running bootstrap, update the bucket name below with the
  # output from: terraform output state_bucket_name
  backend "s3" {
    bucket         = "sentiment-analyzer-tfstate-218795110243"
    key            = "sentiment-analyzer/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
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
# Module: DynamoDB Table
# ===================================================================

module "dynamodb" {
  source = "./modules/dynamodb"

  environment = var.environment
  aws_region  = var.aws_region
}

# ===================================================================
# Lambda Functions
# ===================================================================

# S3 bucket for Lambda deployment packages
# Note: This should be created before deploying Lambdas
resource "aws_s3_bucket" "lambda_deployments" {
  bucket = "${var.environment}-sentiment-lambda-deployments"

  tags = {
    Name = "${var.environment}-sentiment-lambda-deployments"
  }
}

resource "aws_s3_bucket_versioning" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id
  versioning_configuration {
    status = "Enabled"
  }
}

# Block public access to Lambda deployment bucket
resource "aws_s3_bucket_public_access_block" "lambda_deployments" {
  bucket = aws_s3_bucket.lambda_deployments.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lambda naming
locals {
  ingestion_lambda_name = "${var.environment}-sentiment-ingestion"
  analysis_lambda_name  = "${var.environment}-sentiment-analysis"
  dashboard_lambda_name = "${var.environment}-sentiment-dashboard"
  metrics_lambda_name   = "${var.environment}-sentiment-metrics"
}

# ===================================================================
# Module: Ingestion Lambda (T051)
# ===================================================================

module "ingestion_lambda" {
  source = "./modules/lambda"

  function_name = local.ingestion_lambda_name
  description   = "Fetches articles from NewsAPI and stores in DynamoDB"
  iam_role_arn  = module.iam.ingestion_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = aws_s3_bucket.lambda_deployments.id
  s3_key        = "ingestion/lambda.zip"

  # Resource configuration per task spec
  memory_size          = 512
  timeout              = 60
  reserved_concurrency = 1

  # Environment variables
  environment_variables = {
    WATCH_TAGS         = var.watch_tags
    DYNAMODB_TABLE     = module.dynamodb.table_name
    SNS_TOPIC_ARN      = module.sns.topic_arn
    NEWSAPI_SECRET_ARN = module.secrets.newsapi_secret_arn
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
  description   = "Performs sentiment analysis using DistilBERT model"
  iam_role_arn  = module.iam.analysis_lambda_role_arn
  handler       = "handler.lambda_handler"
  s3_bucket     = aws_s3_bucket.lambda_deployments.id
  s3_key        = "analysis/lambda.zip"

  # Resource configuration per task spec
  memory_size          = 1024
  timeout              = 30
  reserved_concurrency = 5

  # Lambda layer for DistilBERT model
  layers = var.model_layer_arns

  # Environment variables
  environment_variables = {
    DYNAMODB_TABLE = module.dynamodb.table_name
    MODEL_PATH     = "/opt/model"
    MODEL_VERSION  = var.model_version
    ENVIRONMENT    = var.environment
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
  s3_bucket     = aws_s3_bucket.lambda_deployments.id
  s3_key        = "dashboard/lambda.zip"

  # Resource configuration per task spec
  memory_size          = 512
  timeout              = 60
  reserved_concurrency = 10

  # Environment variables
  environment_variables = {
    DYNAMODB_TABLE               = module.dynamodb.table_name
    API_KEY                      = "" # Will be fetched from Secrets Manager at runtime
    DASHBOARD_API_KEY_SECRET_ARN = module.secrets.dashboard_api_key_secret_arn
    SSE_POLL_INTERVAL            = "5"
    ENVIRONMENT                  = var.environment
  }

  # Function URL with CORS
  create_function_url    = true
  function_url_auth_type = "NONE"
  function_url_cors = {
    allow_credentials = false
    allow_headers     = ["content-type", "authorization"]
    allow_methods     = ["GET", "OPTIONS"]
    allow_origins     = ["*"] # Restrict in production
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
# Module: SNS Topic (for Analysis Triggers)
# ===================================================================

module "sns" {
  source = "./modules/sns"

  environment = var.environment

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
}

# ===================================================================
# Module: EventBridge Schedules
# ===================================================================

module "eventbridge" {
  source = "./modules/eventbridge"

  environment                    = var.environment
  ingestion_lambda_arn           = module.ingestion_lambda.function_arn
  ingestion_lambda_function_name = module.ingestion_lambda.function_name

  # Metrics Lambda not implemented in Demo 1
  # Dashboard Lambda handles metrics via /api/metrics endpoint
  create_metrics_schedule = false

  depends_on = [module.ingestion_lambda]
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
  description = "URL of the Dashboard Lambda Function URL"
  value       = module.dashboard_lambda.function_url
}

output "lambda_deployment_bucket" {
  description = "S3 bucket for Lambda deployment packages"
  value       = aws_s3_bucket.lambda_deployments.id
}

# EventBridge outputs
output "ingestion_schedule_arn" {
  description = "ARN of the ingestion EventBridge rule"
  value       = module.eventbridge.ingestion_schedule_arn
}
