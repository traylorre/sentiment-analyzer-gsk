# Test fixture: Valid resource naming patterns
# All resources follow the convention: {env}-sentiment-{service}

variable "environment" {
  description = "Environment name (preprod or prod)"
  default     = "preprod"
}

# Lambda functions - valid naming
resource "aws_lambda_function" "dashboard" {
  function_name = "${var.environment}-sentiment-dashboard"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

resource "aws_lambda_function" "api" {
  function_name = "${var.environment}-sentiment-api"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

resource "aws_lambda_function" "processor" {
  function_name = "${var.environment}-sentiment-processor"
  handler       = "index.handler"
  runtime       = "python3.13"
  role          = aws_iam_role.lambda.arn
}

# DynamoDB tables - valid naming
resource "aws_dynamodb_table" "items" {
  name         = "${var.environment}-sentiment-items"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

resource "aws_dynamodb_table" "sessions" {
  name         = "${var.environment}-sentiment-sessions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "session_id"

  attribute {
    name = "session_id"
    type = "S"
  }
}

# SQS queues - valid naming
resource "aws_sqs_queue" "events" {
  name = "${var.environment}-sentiment-events"
}

resource "aws_sqs_queue" "deadletter" {
  name = "${var.environment}-sentiment-deadletter"
}

# SNS topics - valid naming
resource "aws_sns_topic" "alerts" {
  name = "${var.environment}-sentiment-alerts"
}

resource "aws_sns_topic" "notifications" {
  name = "${var.environment}-sentiment-notifications"
}

# IAM role (not validated for naming)
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
