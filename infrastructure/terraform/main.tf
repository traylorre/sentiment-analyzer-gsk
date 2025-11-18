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

  # Backend configuration (commented out for initial setup)
  # Uncomment after creating S3 bucket and DynamoDB table for state locking
  # backend "s3" {
  #   bucket         = "sentiment-analyzer-terraform-state"
  #   key            = "sentiment-analyzer/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }
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
# PLACEHOLDER: Lambda Functions
# Note: Lambda functions will be deployed separately via CI/CD
# This section defines placeholders that will be updated after Lambda deployment
# ===================================================================

# These resources are marked as "data" sources because Lambdas are deployed
# by CI/CD pipeline (GitHub Actions) before Terraform runs
# Terraform will reference these existing resources rather than creating them

# Ingestion Lambda (to be created by CI/CD)
locals {
  ingestion_lambda_name = "${var.environment}-sentiment-ingestion"
  analysis_lambda_name  = "${var.environment}-sentiment-analysis"
  dashboard_lambda_name = "${var.environment}-sentiment-dashboard"
  metrics_lambda_name   = "${var.environment}-sentiment-metrics"
}

# NOTE: These data sources will fail on first `terraform plan` because Lambdas don't exist yet
# Solution: Comment out EventBridge + SNS modules on first apply, uncomment after Lambda deployment

# data "aws_lambda_function" "ingestion" {
#   function_name = local.ingestion_lambda_name
# }
#
# data "aws_lambda_function" "analysis" {
#   function_name = local.analysis_lambda_name
# }
#
# data "aws_lambda_function" "dashboard" {
#   function_name = local.dashboard_lambda_name
# }
#
# data "aws_lambda_function" "metrics" {
#   function_name = local.metrics_lambda_name
# }

# ===================================================================
# Module: SNS Topic (for Analysis Triggers)
# ===================================================================

# Commented out until Lambdas are deployed
# module "sns" {
#   source = "./modules/sns"
#
#   environment                    = var.environment
#   analysis_lambda_arn            = data.aws_lambda_function.analysis.arn
#   analysis_lambda_function_name  = data.aws_lambda_function.analysis.function_name
# }

# ===================================================================
# Module: IAM Roles (for Lambda Functions)
# ===================================================================

# Commented out until SNS topic exists
# module "iam" {
#   source = "./modules/iam"
#
#   environment                   = var.environment
#   dynamodb_table_arn            = module.dynamodb.table_arn
#   newsapi_secret_arn            = module.secrets.newsapi_secret_arn
#   dashboard_api_key_secret_arn  = module.secrets.dashboard_api_key_secret_arn
#   analysis_topic_arn            = module.sns.topic_arn
# }

# ===================================================================
# Module: EventBridge Schedules
# ===================================================================

# Commented out until Lambdas are deployed
# module "eventbridge" {
#   source = "./modules/eventbridge"
#
#   environment                      = var.environment
#   ingestion_lambda_arn             = data.aws_lambda_function.ingestion.arn
#   ingestion_lambda_function_name   = data.aws_lambda_function.ingestion.function_name
#   metrics_lambda_arn               = data.aws_lambda_function.metrics.arn
#   metrics_lambda_function_name     = data.aws_lambda_function.metrics.function_name
# }

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

# Outputs that will be available after uncommenting IAM/SNS/EventBridge modules
# output "sns_topic_arn" {
#   description = "ARN of the SNS topic"
#   value       = module.sns.topic_arn
# }
#
# output "ingestion_lambda_role_arn" {
#   description = "ARN of the Ingestion Lambda IAM role"
#   value       = module.iam.ingestion_lambda_role_arn
# }
