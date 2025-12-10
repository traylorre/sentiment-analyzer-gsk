# Test fixture: Invalid resource naming patterns
# Resources that do NOT follow the convention: {env}-sentiment-{service}

variable "environment" {
  description = "Environment name"
  default     = "preprod"
}

# Lambda functions - INVALID naming (missing sentiment segment)
resource "aws_lambda_function" "bad_dashboard" {
  function_name = "${var.environment}-dashboard"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

# Missing environment prefix
resource "aws_lambda_function" "no_env" {
  function_name = "sentiment-api"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

# DynamoDB tables - INVALID naming
resource "aws_dynamodb_table" "wrong_format" {
  name         = "my-custom-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Uses 'dev' instead of 'preprod' or 'prod'
resource "aws_dynamodb_table" "wrong_env" {
  name         = "dev-sentiment-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# SQS queues - INVALID naming
resource "aws_sqs_queue" "no_pattern" {
  name = "event-queue"
}

# SNS topics - INVALID naming (uppercase)
resource "aws_sns_topic" "wrong_case" {
  name = "${var.environment}-Sentiment-Alerts"
}

# IAM role (not validated)
resource "aws_iam_role" "lambda" {
  name = "lambda-execution-role"

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
