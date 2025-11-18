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
  handler       = var.handler
  runtime       = var.runtime
  timeout       = var.timeout
  memory_size   = var.memory_size

  # Deployment package from S3
  s3_bucket = var.s3_bucket
  s3_key    = var.s3_key

  # Optional: specific version of the package
  source_code_hash = var.source_code_hash

  # Environment variables
  dynamic "environment" {
    for_each = length(var.environment_variables) > 0 ? [1] : []
    content {
      variables = var.environment_variables
    }
  }

  # Optional Lambda layers (e.g., for DistilBERT model)
  layers = var.layers

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

  # Ensure log group is created first
  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = merge(var.tags, {
    Name = var.function_name
  })

  # Lifecycle: ignore changes to s3_key if using aliases for deployment
  lifecycle {
    ignore_changes = var.ignore_source_code_changes ? [s3_key, source_code_hash] : []
  }
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
  statistic           = "p90"
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
