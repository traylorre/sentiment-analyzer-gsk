# CloudWatch Alarms for On-Call SOP
# All alarms map to scenarios in ON_CALL_SOP.md

# SNS Topic for alarm notifications
resource "aws_sns_topic" "alarms" {
  name              = "${var.environment}-sentiment-alarms"
  kms_master_key_id = "alias/aws/sns"

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Purpose     = "alarm-notifications"
  }
}

# Email subscription (configure email in variables)
resource "aws_sns_topic_subscription" "alarm_email" {
  count     = var.alarm_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alarms.arn
  protocol  = "email"
  endpoint  = var.alarm_email
}

# =============================================================================
# Lambda Error Alarms (SC-03, SC-04, SC-05)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "ingestion_errors" {
  alarm_name          = "${var.environment}-lambda-ingestion-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "SC-03: Ingestion Lambda errors > 3 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-ingestion"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-03"
  }
}

resource "aws_cloudwatch_metric_alarm" "analysis_errors" {
  alarm_name          = "${var.environment}-lambda-analysis-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "SC-04: Analysis Lambda errors > 3 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-analysis"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-04"
  }
}

resource "aws_cloudwatch_metric_alarm" "dashboard_errors" {
  alarm_name          = "${var.environment}-lambda-dashboard-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "SC-05: Dashboard Lambda errors > 5 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-dashboard"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-05"
  }
}

# =============================================================================
# Lambda Latency Alarms (SC-11, SC-12)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "analysis_latency" {
  alarm_name          = "${var.environment}-analysis-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 25000
  alarm_description   = "SC-11: Analysis Lambda P95 latency > 25 seconds"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-analysis"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-11"
  }
}

resource "aws_cloudwatch_metric_alarm" "dashboard_latency" {
  alarm_name          = "${var.environment}-dashboard-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = 1000
  alarm_description   = "SC-12: Dashboard Lambda P95 latency > 1 second"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-dashboard"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-12"
  }
}

# =============================================================================
# SNS Delivery Alarm (SC-06)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "sns_delivery_failures" {
  alarm_name          = "${var.environment}-sns-delivery-failures"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NumberOfNotificationsFailed"
  namespace           = "AWS/SNS"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  alarm_description   = "SC-06: SNS delivery failures > 5 in 5 minutes"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TopicName = "${var.environment}-sentiment-analysis-requests"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-06"
  }
}

# =============================================================================
# Custom Metric Alarms (SC-07, SC-10)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "newsapi_rate_limit" {
  alarm_name          = "${var.environment}-newsapi-rate-limit"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NewsAPIRateLimitHit"
  namespace           = "SentimentAnalyzer"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "SC-07: NewsAPI rate limit exceeded"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-07"
  }
}

resource "aws_cloudwatch_metric_alarm" "no_new_items" {
  alarm_name          = "${var.environment}-no-new-items-1h"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 6  # 6 x 10 min = 1 hour
  metric_name         = "NewItemsIngested"
  namespace           = "SentimentAnalyzer"
  period              = 600
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "SC-10: No new items ingested for 1 hour"
  treat_missing_data  = "breaching"  # Missing data means no ingestion

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-10"
  }
}

# =============================================================================
# DLQ Depth Alarm (SC-09)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "dlq_depth" {
  alarm_name          = "${var.environment}-dlq-depth-exceeded"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 100
  alarm_description   = "SC-09: DLQ depth > 100 messages"
  treat_missing_data  = "notBreaching"

  dimensions = {
    QueueName = "${var.environment}-sentiment-analysis-dlq"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "001-interactive-dashboard-demo"
    Scenario    = "SC-09"
  }
}

# =============================================================================
# Budget Alarms (SC-08)
# =============================================================================

resource "aws_budgets_budget" "monthly" {
  name         = "${var.environment}-sentiment-monthly-budget"
  budget_type  = "COST"
  limit_amount = var.monthly_budget_limit
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Feature$001-interactive-dashboard-demo"
    ]
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = var.alarm_email != "" ? [var.alarm_email] : []
  }
}
