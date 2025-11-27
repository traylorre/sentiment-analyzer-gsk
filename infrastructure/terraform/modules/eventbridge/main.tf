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
# Optional - only created if create_metrics_schedule is true
resource "aws_cloudwatch_event_rule" "metrics_schedule" {
  count = var.create_metrics_schedule ? 1 : 0

  name                = "${var.environment}-sentiment-metrics-schedule"
  description         = "Trigger metrics collection every 1 minute"
  schedule_expression = "rate(1 minute)"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
  }
}

resource "aws_cloudwatch_event_target" "metrics_lambda" {
  count = var.create_metrics_schedule ? 1 : 0

  rule      = aws_cloudwatch_event_rule.metrics_schedule[0].name
  target_id = "MetricsLambdaTarget"
  arn       = var.metrics_lambda_arn
}

# Lambda permission to allow EventBridge to invoke Metrics Lambda
resource "aws_lambda_permission" "eventbridge_invoke_metrics" {
  count = var.create_metrics_schedule ? 1 : 0

  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.metrics_lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.metrics_schedule[0].arn
}

# =============================================================================
# Daily Digest Schedule (Feature 006 - T151)
# =============================================================================
# Triggers the notification Lambda every hour to process users who have their
# digest scheduled for that hour. The Lambda queries DynamoDB for users with
# digest_time matching the current hour and sends personalized digest emails.
# =============================================================================

resource "aws_cloudwatch_event_rule" "daily_digest_schedule" {
  count = var.create_digest_schedule ? 1 : 0

  name                = "${var.environment}-sentiment-daily-digest"
  description         = "Trigger daily digest email processing every hour"
  schedule_expression = "cron(0 * * * ? *)" # Every hour at minute 0

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
  }
}

resource "aws_cloudwatch_event_target" "daily_digest_notification" {
  count = var.create_digest_schedule ? 1 : 0

  rule      = aws_cloudwatch_event_rule.daily_digest_schedule[0].name
  target_id = "DailyDigestNotificationTarget"
  arn       = var.notification_lambda_arn

  # Pass event to indicate this is a digest trigger
  input = jsonencode({
    "detail-type" = "Scheduled Event"
    "source"      = "aws.events"
    "detail" = {
      "notification_type" = "digest"
    }
  })
}

# Lambda permission to allow EventBridge to invoke Notification Lambda for digest
resource "aws_lambda_permission" "eventbridge_invoke_digest" {
  count = var.create_digest_schedule ? 1 : 0

  statement_id  = "AllowDigestExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.notification_lambda_function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily_digest_schedule[0].arn
}
