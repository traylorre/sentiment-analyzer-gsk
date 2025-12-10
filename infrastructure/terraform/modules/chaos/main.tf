# AWS Fault Injection Service (FIS) for Chaos Testing
# =====================================================
#
# Chaos Engineering for Sentiment Analyzer
#
# STATUS: TEMPORARILY DISABLED
# The Terraform AWS provider doesn't support Lambda FIS targets yet.
# See: https://github.com/hashicorp/terraform-provider-aws/issues/41208
#
# When the provider is updated:
# 1. Uncomment the Lambda FIS templates below
# 2. Set enable_chaos_testing = true in main.tf for preprod
#
# NOTE: DynamoDB does NOT support API-level fault injection via FIS.
# FIS only supports:
#   - aws:dynamodb:global-table-pause-replication (requires global tables)
#   - aws:network:disrupt-connectivity (requires VPC/subnets)
#
# Our Lambdas are not VPC-attached, so we focus on Lambda-level chaos.
# DynamoDB is highly durable; test your app's retry/backoff logic instead.
#
# Reference: https://docs.aws.amazon.com/fis/latest/userguide/fis-actions-reference.html

# ============================================================================
# IAM Role for FIS Execution (placeholder - will be used when FIS is enabled)
# ============================================================================

resource "aws_iam_role" "fis_execution" {
  count = var.enable_chaos_testing ? 1 : 0
  name  = "${var.environment}-fis-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "fis.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name        = "${var.environment}-sentiment-fis-execution"
    Environment = var.environment
    Purpose     = "chaos-testing"
    ManagedBy   = "Terraform"
  }
}

# IAM policy for FIS Lambda fault injection (October 2024 actions)
resource "aws_iam_role_policy" "fis_lambda" {
  count = var.enable_chaos_testing ? 1 : 0
  name  = "fis-lambda-fault-injection"
  role  = aws_iam_role.fis_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaFaultInjection"
        Effect = "Allow"
        Action = [
          "lambda:GetFunction",
          "lambda:GetFunctionConfiguration"
        ]
        Resource = var.lambda_arns
      },
      {
        Sid    = "TagResources"
        Effect = "Allow"
        Action = [
          "tag:GetResources"
        ]
        Resource = "*"
      },
      {
        Sid    = "FISS3ConfigBucket"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::aws-fis-*/*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogDelivery",
          "logs:DeleteLogDelivery",
          "logs:GetLogDelivery",
          "logs:ListLogDeliveries"
        ]
        Resource = "*"
      }
    ]
  })
}

# ============================================================================
# CloudWatch Log Group for FIS Experiment Logs
# ============================================================================

resource "aws_cloudwatch_log_group" "fis_experiments" {
  count             = var.enable_chaos_testing ? 1 : 0
  name              = "/aws/fis/${var.environment}-chaos-experiments"
  retention_in_days = 14 # 2 weeks for chaos testing analysis

  tags = {
    Name        = "${var.environment}-sentiment-fis-logs"
    Environment = var.environment
    Purpose     = "chaos-testing"
    ManagedBy   = "Terraform"
  }
}

# ============================================================================
# FIS Experiment Templates - DISABLED
# ============================================================================
#
# The aws_fis_experiment_template resources are commented out because the
# Terraform AWS provider doesn't recognize "Functions" as a valid target key.
# This is tracked in: https://github.com/hashicorp/terraform-provider-aws/issues/41208
#
# When the provider is updated, uncomment the following resources:
#
# resource "aws_fis_experiment_template" "lambda_latency" {
#   count       = var.enable_chaos_testing ? 1 : 0
#   description = "Inject latency into Lambda invocations to test timeout handling"
#
#   stop_condition {
#     source = "aws:cloudwatch:alarm"
#     value  = var.lambda_error_alarm_arn
#   }
#
#   role_arn = aws_iam_role.fis_execution[0].arn
#
#   action {
#     name      = "inject-lambda-latency"
#     action_id = "aws:lambda:invocation-add-delay"
#
#     parameter {
#       key   = "duration"
#       value = "PT3M" # 3 minutes
#     }
#
#     parameter {
#       key   = "invocationPercentage"
#       value = "25" # Affect 25% of invocations
#     }
#
#     parameter {
#       key   = "startupDelayMilliseconds"
#       value = "5000" # 5 second delay
#     }
#
#     target {
#       key   = "Functions"
#       value = "lambda-targets"
#     }
#   }
#
#   target {
#     name           = "lambda-targets"
#     resource_type  = "aws:lambda:function"
#     resource_arns  = var.lambda_arns
#     selection_mode = "ALL"
#   }
#
#   log_configuration {
#     cloudwatch_logs_configuration {
#       log_group_arn = "${aws_cloudwatch_log_group.fis_experiments[0].arn}:*"
#     }
#     log_schema_version = 2
#   }
#
#   tags = {
#     Name        = "${var.environment}-lambda-latency"
#     Environment = var.environment
#     Purpose     = "chaos-testing"
#     Scenario    = "lambda_latency"
#     ManagedBy   = "Terraform"
#   }
# }
#
# resource "aws_fis_experiment_template" "lambda_error" {
#   count       = var.enable_chaos_testing ? 1 : 0
#   description = "Inject errors into Lambda invocations to test failure handling"
#
#   stop_condition {
#     source = "aws:cloudwatch:alarm"
#     value  = var.lambda_error_alarm_arn
#   }
#
#   role_arn = aws_iam_role.fis_execution[0].arn
#
#   action {
#     name      = "inject-lambda-error"
#     action_id = "aws:lambda:invocation-error"
#
#     parameter {
#       key   = "duration"
#       value = "PT2M" # 2 minutes
#     }
#
#     parameter {
#       key   = "invocationPercentage"
#       value = "10" # Affect 10% of invocations
#     }
#
#     parameter {
#       key   = "preventExecution"
#       value = "true" # Prevent Lambda from executing
#     }
#
#     target {
#       key   = "Functions"
#       value = "lambda-error-targets"
#     }
#   }
#
#   target {
#     name           = "lambda-error-targets"
#     resource_type  = "aws:lambda:function"
#     resource_arns  = var.lambda_arns
#     selection_mode = "ALL"
#   }
#
#   log_configuration {
#     cloudwatch_logs_configuration {
#       log_group_arn = "${aws_cloudwatch_log_group.fis_experiments[0].arn}:*"
#     }
#     log_schema_version = 2
#   }
#
#   tags = {
#     Name        = "${var.environment}-lambda-error"
#     Environment = var.environment
#     Purpose     = "chaos-testing"
#     Scenario    = "lambda_error"
#     ManagedBy   = "Terraform"
#   }
# }
