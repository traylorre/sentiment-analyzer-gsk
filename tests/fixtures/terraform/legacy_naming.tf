# Test fixture: Legacy naming patterns
# Resources using the old "sentiment-analyzer-*" naming convention
# These should be detected and flagged for migration

variable "environment" {
  description = "Environment name"
  default     = "preprod"
}

# Lambda functions - LEGACY naming pattern
resource "aws_lambda_function" "legacy_api" {
  function_name = "sentiment-analyzer-api"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

resource "aws_lambda_function" "legacy_processor" {
  function_name = "sentiment-analyzer-processor"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

# DynamoDB tables - LEGACY naming
resource "aws_dynamodb_table" "legacy_items" {
  name         = "sentiment-analyzer-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# SQS queues - LEGACY naming
resource "aws_sqs_queue" "legacy_events" {
  name = "sentiment-analyzer-events"
}

# SNS topics - LEGACY naming
resource "aws_sns_topic" "legacy_alerts" {
  name = "sentiment-analyzer-alerts"
}

# IAM role (not validated)
resource "aws_iam_role" "lambda" {
  name = "legacy-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}
