# SNS Topic for Analysis Triggers

# Dead Letter Queue for failed Lambda invocations
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.environment}-sentiment-analysis-dlq"
  message_retention_seconds = 1209600 # 14 days

  tags = {
    Name        = "${var.environment}-analysis-dlq"
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_sns_topic" "analysis_requests" {
  name = "${var.environment}-sentiment-analysis-requests"

  # Enable encryption at rest
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Name        = "${var.environment}-analysis-requests"
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

# SNS Topic Policy (allow Lambda to publish)
resource "aws_sns_topic_policy" "analysis_requests" {
  arn = aws_sns_topic.analysis_requests.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "SNS:Publish"
        ]
        Resource = aws_sns_topic.analysis_requests.arn
      }
    ]
  })
}

# SNS Subscription: Analysis Lambda (optional)
resource "aws_sns_topic_subscription" "analysis_lambda" {
  count = var.create_subscription ? 1 : 0

  topic_arn = aws_sns_topic.analysis_requests.arn
  protocol  = "lambda"
  endpoint  = var.analysis_lambda_arn
}

# Lambda permission to allow SNS to invoke Analysis Lambda (optional)
resource "aws_lambda_permission" "sns_invoke_analysis" {
  count = var.create_subscription ? 1 : 0

  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = var.analysis_lambda_function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.analysis_requests.arn
}
