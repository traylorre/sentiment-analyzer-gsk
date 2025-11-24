# AWS Fault Injection Simulator (FIS) for Chaos Testing
# ========================================================
#
# Phase 2: DynamoDB Throttling Experiment
#
# This module creates FIS experiment templates for controlled chaos testing.
# Only deployed in preprod/dev environments for safety.

# IAM role for FIS to assume when running experiments
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
    Environment = var.environment
    Purpose     = "chaos-testing"
    ManagedBy   = "Terraform"
  }
}

# IAM policy for FIS to inject faults into DynamoDB
resource "aws_iam_role_policy" "fis_dynamodb" {
  count = var.enable_chaos_testing ? 1 : 0
  name  = "fis-dynamodb-fault-injection"
  role  = aws_iam_role.fis_execution[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:DescribeTable",
          "dynamodb:ListTables"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "fis:InjectApiThrottleError",
          "fis:InjectApiInternalError"
        ]
        Resource = var.dynamodb_table_arn
      }
    ]
  })
}

# FIS Experiment Template: DynamoDB Write Throttling
resource "aws_fis_experiment_template" "dynamodb_throttle" {
  count       = var.enable_chaos_testing ? 1 : 0
  description = "Inject DynamoDB write throttling to test backpressure and DLQ behavior"

  stop_condition {
    source = "aws:cloudwatch:alarm"
    value  = var.write_throttle_alarm_arn
  }

  role_arn = aws_iam_role.fis_execution[0].arn

  action {
    name      = "dynamodb-throttle-writes"
    action_id = "aws:dynamodb:api-error"

    parameter {
      key   = "service"
      value = "dynamodb"
    }

    parameter {
      key   = "api"
      value = "PutItem,UpdateItem,BatchWriteItem"
    }

    parameter {
      key   = "percentage"
      value = "25"
    }

    parameter {
      key   = "duration"
      value = "PT5M"
    }

    parameter {
      key   = "errorCode"
      value = "ThrottlingException"
    }

    target {
      key   = "Tables"
      value = "dynamodb-tables"
    }
  }

  target {
    name          = "dynamodb-tables"
    resource_type = "aws:dynamodb:table"

    resource_arns = [
      var.dynamodb_table_arn
    ]

    selection_mode = "ALL"
  }

  tags = {
    Name        = "${var.environment}-dynamodb-throttle"
    Environment = var.environment
    Purpose     = "chaos-testing"
    Scenario    = "dynamodb_throttle"
    ManagedBy   = "Terraform"
  }
}

# CloudWatch Log Group for FIS experiment logs
resource "aws_cloudwatch_log_group" "fis_experiments" {
  count             = var.enable_chaos_testing ? 1 : 0
  name              = "/aws/fis/${var.environment}-chaos-experiments"
  retention_in_days = 7 # 7-day retention for chaos testing logs

  tags = {
    Environment = var.environment
    Purpose     = "chaos-testing"
    ManagedBy   = "Terraform"
  }
}

# FIS Experiment Template: Lambda Delay Injection (Phase 4)
# Commented out for now - will be enabled in Phase 4
#
# resource "aws_fis_experiment_template" "lambda_delay" {
#   count       = var.enable_chaos_testing ? 1 : 0
#   description = "Add artificial delay to Lambda cold starts"
#
#   stop_conditions {
#     source = "aws:cloudwatch:alarm"
#     value  = var.lambda_error_alarm_arn
#   }
#
#   role_arn = aws_iam_role.fis_execution[0].arn
#
#   actions {
#     name      = "lambda-add-latency"
#     action_id = "aws:lambda:invocation-add-delay"
#
#     parameters = {
#       duration = "PT3M"
#       delay    = "5000" # 5 seconds
#     }
#
#     targets = {
#       Functions = "lambda-functions"
#     }
#   }
#
#   targets {
#     name          = "lambda-functions"
#     resource_type = "aws:lambda:function"
#
#     resource_arns = [
#       var.analysis_lambda_arn
#     ]
#
#     selection_mode = "ALL"
#   }
#
#   tags = {
#     Name        = "${var.environment}-lambda-delay"
#     Environment = var.environment
#     Purpose     = "chaos-testing"
#     Scenario    = "lambda_cold_start"
#     ManagedBy   = "Terraform"
#   }
# }
