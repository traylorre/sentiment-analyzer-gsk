# EventBridge Schedule for Ingestion Lambda

resource "aws_cloudwatch_event_rule" "ingestion_schedule" {
  name                = "${var.environment}-sentiment-ingestion-schedule"
  description         = "Trigger sentiment analysis ingestion every 5 minutes"
  schedule_expression = "rate(5 minutes)"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_cloudwatch_event_target" "ingestion_lambda" {
  rule      = aws_cloudwatch_event_rule.ingestion_schedule.name
  target_id = "IngestionLambdaTarget"
  arn       = var.ingestion_lambda_arn
}

# Lambda permission to allow EventBridge to invoke Ingestion Lambda
resource "aws_lambda_permission" "eventbridge_invoke_ingestion" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.ingestion_lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ingestion_schedule.arn
}

# EventBridge Schedule for Metrics Lambda (every 1 minute)
resource "aws_cloudwatch_event_rule" "metrics_schedule" {
  name                = "${var.environment}-sentiment-metrics-schedule"
  description         = "Trigger metrics collection every 1 minute"
  schedule_expression = "rate(1 minute)"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_cloudwatch_event_target" "metrics_lambda" {
  rule      = aws_cloudwatch_event_rule.metrics_schedule.name
  target_id = "MetricsLambdaTarget"
  arn       = var.metrics_lambda_arn
}

# Lambda permission to allow EventBridge to invoke Metrics Lambda
resource "aws_lambda_permission" "eventbridge_invoke_metrics" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.metrics_lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_schedule.arn
}
