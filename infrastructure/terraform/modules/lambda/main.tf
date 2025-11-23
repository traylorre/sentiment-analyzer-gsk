# Reusable Lambda Function Module
# ================================
#
# Creates a Lambda function with common configuration for the sentiment analyzer.
#
# For On-Call Engineers:
#     If Lambda fails to deploy:
#     1. Check IAM role exists and has correct permissions
#     2. Verify S3 bucket contains the deployment package
#     3. Check CloudWatch logs for initialization errors
#
#     See SC-06 in ON_CALL_SOP.md for Lambda deployment issues.
#
# For Developers:
#     - Memory and timeout configurable per Lambda
#     - Environment variables passed as map
#     - CloudWatch log group created with configurable retention
#     - Supports Lambda layers for dependencies/models

# CloudWatch Log Group
# Creates log group before Lambda to avoid race condition
resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${var.function_name}"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.function_name}-logs"
  })
}

# Lambda Function
resource "aws_lambda_function" "this" {
  function_name = var.function_name
  description   = var.description
  role          = var.iam_role_arn
  timeout       = var.timeout
  memory_size   = var.memory_size

  # Package type (Zip or Image)
  package_type = var.package_type

  # ZIP package configuration (only used when package_type = "Zip")
  handler = var.package_type == "Zip" ? var.handler : null
  runtime = var.package_type == "Zip" ? var.runtime : null

  # Deployment package from S3 (only used when package_type = "Zip")
  s3_bucket        = var.package_type == "Zip" ? var.s3_bucket : null
  s3_key           = var.package_type == "Zip" ? var.s3_key : null
  source_code_hash = var.package_type == "Zip" ? var.source_code_hash : null

  # Container image configuration (only used when package_type = "Image")
  image_uri = var.package_type == "Image" ? var.image_uri : null

  # Container image config overrides (optional)
  dynamic "image_config" {
    for_each = var.package_type == "Image" && var.image_config != null ? [var.image_config] : []
    content {
      command           = image_config.value.command
      entry_point       = image_config.value.entry_point
      working_directory = image_config.value.working_directory
    }
  }

  # Environment variables
  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  # Optional Lambda layers (only for ZIP packages, not supported for container images)
  layers = var.package_type == "Zip" ? var.layers : null

  # Reserved concurrency (0 = use unreserved account concurrency)
  reserved_concurrent_executions = var.reserved_concurrency

  # VPC configuration (optional)
  dynamic "vpc_config" {
    for_each = var.vpc_config != null ? [var.vpc_config] : []
    content {
      subnet_ids         = vpc_config.value.subnet_ids
      security_group_ids = vpc_config.value.security_group_ids
    }
  }

  # Dead letter queue configuration (optional)
  dynamic "dead_letter_config" {
    for_each = var.dlq_arn != null ? [1] : []
    content {
      target_arn = var.dlq_arn
    }
  }

  # Tracing configuration (X-Ray)
  tracing_config {
    mode = var.tracing_mode
  }

  # Ephemeral storage (/tmp) configuration
  ephemeral_storage {
    size = var.ephemeral_storage_size
  }

  # Ensure log group is created first
  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = merge(var.tags, {
    Name = var.function_name
  })

  # Note: ignore_source_code_changes variable is available but not used here
  # because Terraform requires static lists in lifecycle blocks.
  # For deployments that need to ignore source changes, use a separate resource
  # or manage deployments via Lambda aliases instead.
}

# Lambda Function URL (optional)
# Creates a public HTTPS endpoint for the Lambda
resource "aws_lambda_function_url" "this" {
  count = var.create_function_url ? 1 : 0

  function_name      = aws_lambda_function.this.function_name
  authorization_type = var.function_url_auth_type

  cors {
    allow_credentials = var.function_url_cors.allow_credentials
    allow_headers     = var.function_url_cors.allow_headers
    allow_methods     = var.function_url_cors.allow_methods
    allow_origins     = var.function_url_cors.allow_origins
    expose_headers    = var.function_url_cors.expose_headers
    max_age           = var.function_url_cors.max_age
  }
}

# CloudWatch Alarm for Lambda errors (optional)
resource "aws_cloudwatch_metric_alarm" "errors" {
  count = var.create_error_alarm ? 1 : 0

  alarm_name          = "${var.function_name}-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_alarm_threshold
  alarm_description   = "Lambda function ${var.function_name} error rate exceeded threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.alarm_actions

  tags = var.tags
}

# CloudWatch Alarm for Lambda duration (optional)
resource "aws_cloudwatch_metric_alarm" "duration" {
  count = var.create_duration_alarm ? 1 : 0

  alarm_name          = "${var.function_name}-duration"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p90"
  threshold           = var.duration_alarm_threshold
  alarm_description   = "Lambda function ${var.function_name} duration exceeded threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = aws_lambda_function.this.function_name
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.alarm_actions

  tags = var.tags
}
