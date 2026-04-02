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

  # Package type: Image for Docker, Zip for S3
  package_type = var.image_uri != null ? "Image" : "Zip"

  # Docker-based Lambda (ECR image)
  image_uri = var.image_uri

  # Zip-based Lambda (S3 deployment)
  # Only set these when not using Docker
  handler   = var.image_uri == null ? var.handler : null
  runtime   = var.image_uri == null ? var.runtime : null
  s3_bucket = var.image_uri == null ? var.s3_bucket : null
  s3_key    = var.image_uri == null ? var.s3_key : null

  # Optional: specific version of the package (works for both Zip and Image)
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

  # Ephemeral storage (/tmp) configuration
  ephemeral_storage {
    size = var.ephemeral_storage_size
  }

  # Ensure log group is created first
  depends_on = [aws_cloudwatch_log_group.lambda]

  tags = merge(var.tags, {
    Name = var.function_name
  })

  # Feature 1224: Ignore image_uri changes made by CI/CD force-update step.
  # Without this, Terraform apply reverts image_uri to :latest, then the
  # Force Image Update step changes it to :sha — causing a double function
  # update that breaks the Function URL routing (persistent 404).
  # CI manages image_uri via aws lambda update-function-code.
  # Feature 1290: environment added to break circular dependency cycle.
  # Cross-module env vars (SCHEDULER_ROLE_ARN, DASHBOARD_URL) are managed
  # by terraform_data wiring resources, not by this module block.
  # See docs/terraform-patterns.md for the split definition/wiring pattern.
  lifecycle {
    ignore_changes = [image_uri, environment]
  }
}

# Feature 1224.4: Lambda alias for stable Function URL deployment.
# Lambda alias for zero-downtime deployment. CI publishes a new version,
# pre-warms it, then flips the alias. API Gateway and Function URL both
# invoke via this alias.
#
# Feature 1300: Decoupled from create_function_url — the alias is needed by
# API Gateway (qualifier = "live") regardless of whether a Function URL exists.
# Previously gated on create_function_url, which destroyed the alias when
# Dashboard Lambda disabled its Function URL, breaking API Gateway invocation.
resource "aws_lambda_alias" "live" {
  name             = "live"
  description      = "Active version for API Gateway and Function URL traffic"
  function_name    = aws_lambda_function.this.function_name
  function_version = aws_lambda_function.this.version

  # CI manages the alias version via aws lambda update-alias.
  # Terraform should not revert it on every apply.
  lifecycle {
    ignore_changes = [function_version]
  }
}

# Lambda Function URL (optional)
# Creates a public HTTPS endpoint for the Lambda
# Note: For SSE/streaming responses, set invoke_mode = "RESPONSE_STREAM"
# Feature 1224.4: Points to alias, not $LATEST, for stable routing.
resource "aws_lambda_function_url" "this" {
  count = var.create_function_url ? 1 : 0

  function_name      = aws_lambda_function.this.function_name
  qualifier          = aws_lambda_alias.live.name
  authorization_type = var.function_url_auth_type
  invoke_mode        = var.function_url_invoke_mode

  cors {
    allow_credentials = var.function_url_cors.allow_credentials
    allow_headers     = var.function_url_cors.allow_headers
    allow_methods     = var.function_url_cors.allow_methods
    allow_origins     = var.function_url_cors.allow_origins
    expose_headers    = var.function_url_cors.expose_headers
    max_age           = var.function_url_cors.max_age
  }
}

# Feature 1224.4: Allow Function URL to invoke via the alias
# Function URL public access permission — only created when auth_type = NONE.
# When auth_type = AWS_IAM, callers (API Gateway, CloudFront OAC) use their own
# explicit aws_lambda_permission resources instead.
resource "aws_lambda_permission" "function_url_alias" {
  count = var.create_function_url && var.function_url_auth_type == "NONE" ? 1 : 0

  statement_id           = "FunctionURLAllowPublicAccess"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.this.function_name
  qualifier              = aws_lambda_alias.live.name
  principal              = "*"
  function_url_auth_type = "NONE"
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
