# SNS Topic for Analysis Triggers

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

# SNS Subscription: Analysis Lambda
resource "aws_sns_topic_subscription" "analysis_lambda" {
  topic_arn = aws_sns_topic.analysis_requests.arn
  protocol  = "lambda"
  endpoint  = var.analysis_lambda_arn
}

# Lambda permission to allow SNS to invoke Analysis Lambda
resource "aws_lambda_permission" "sns_invoke_analysis" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = var.analysis_lambda_function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.analysis_requests.arn
}
