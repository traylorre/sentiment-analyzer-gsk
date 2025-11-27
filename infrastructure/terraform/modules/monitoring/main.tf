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

# Alarm: Lambda ImportModuleError (critical packaging issue)
# Catches binary incompatibility issues like pydantic ImportModuleError
resource "aws_cloudwatch_log_metric_filter" "dashboard_import_errors" {
  name           = "${var.environment}-dashboard-import-errors"
  log_group_name = "/aws/lambda/${var.environment}-sentiment-dashboard"
  pattern        = "[time, request_id, level=ERROR*, msg=\"*ImportModuleError*\" || msg=\"*No module named*\" || msg=\"*cannot import name*\"]"

  metric_transformation {
    name      = "DashboardImportErrors"
    namespace = "SentimentAnalyzer/Packaging"
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_metric_alarm" "dashboard_import_errors" {
  alarm_name          = "${var.environment}-dashboard-import-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "DashboardImportErrors"
  namespace           = "SentimentAnalyzer/Packaging"
  period              = 60 # 1 minute (critical - immediate alert)
  statistic           = "Sum"
  threshold           = 0 # ANY import error is critical
  alarm_description   = "CRITICAL: Dashboard Lambda ImportModuleError detected (packaging/binary compatibility issue)"
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Severity    = "CRITICAL"
    Scenario    = "packaging-failure"
  }
}

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
# Custom Metric Alarms (SC-10)
# =============================================================================

# NOTE: NewsAPI alarm removed in Feature 006 - replaced by Tiingo/Finnhub alarms
# See api_alarms.tf for tiingo_error_rate and finnhub_error_rate alarms

resource "aws_cloudwatch_metric_alarm" "no_new_items" {
  alarm_name          = "${var.environment}-no-new-items-1h"
  comparison_operator = "LessThanOrEqualToThreshold"
  evaluation_periods  = 6 # 6 x 10 min = 1 hour
  metric_name         = "NewItemsIngested"
  namespace           = "SentimentAnalyzer"
  period              = 600
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "SC-10: No new items ingested for 1 hour"
  treat_missing_data  = "breaching" # Missing data means no ingestion

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
# Budget Alarms (SC-08) - Enhanced for P0 Security
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

  # Notification 1: 25% threshold (early warning for attacks)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 25
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Notification 2: 50% threshold (investigate)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 50
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Notification 3: 75% threshold (take action)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 75
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Notification 4: 90% threshold (emergency - consider shutdown)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 90
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Notification 5: 100% of budget (budget exceeded)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 100
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Notification 6: Forecasted overspend (predictive alert)
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1] : []
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = 100
      threshold_type             = "PERCENTAGE"
      notification_type          = "FORECASTED"
      subscriber_email_addresses = [var.alarm_email]
    }
  }

  # Also send to SNS topic for programmatic handling
  dynamic "notification" {
    for_each = var.alarm_email != "" ? [1, 2, 3, 4, 5] : []
    content {
      comparison_operator       = "GREATER_THAN"
      threshold                 = notification.value * 20 # 20%, 40%, 60%, 80%, 100%
      threshold_type            = "PERCENTAGE"
      notification_type         = "ACTUAL"
      subscriber_sns_topic_arns = [aws_sns_topic.alarms.arn]
    }
  }
}

# =============================================================================
# Cost Anomaly Detection Alarms (P0 Security - Budget Protection)
# =============================================================================

# Alarm: High DynamoDB read capacity (primary cost driver in attacks)
resource "aws_cloudwatch_metric_alarm" "dynamodb_high_reads" {
  alarm_name          = "${var.environment}-dynamodb-high-read-capacity"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ConsumedReadCapacityUnits"
  namespace           = "AWS/DynamoDB"
  period              = 300 # 5 minutes
  statistic           = "Sum"
  threshold           = 10000 # Alert if >10K reads in 5 minutes (normal: ~100-500)
  alarm_description   = "P0-Security: DynamoDB read capacity exceeds normal rate (possible cost attack)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    TableName = "${var.environment}-sentiment-items"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Security    = "P0-cost-protection"
    Scenario    = "budget-exhaustion-attack"
  }
}

# =============================================================================
# SendGrid Email Quota Alarm (Feature 006 - T152)
# =============================================================================
# Monitors the custom metric for SendGrid email quota usage.
# The notification Lambda writes EmailQuotaUsed metric to CloudWatch.
# Alert at 50% to allow time to respond before hitting hard limit.
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "sendgrid_quota_warning" {
  alarm_name          = "${var.environment}-sendgrid-quota-50-percent"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "EmailQuotaUsed"
  namespace           = "SentimentAnalyzer/Notifications"
  period              = 3600 # 1 hour
  statistic           = "Maximum"
  threshold           = 50 # 50 emails = 50% of daily limit
  alarm_description   = "SendGrid email quota at 50% (50/100). Consider throttling alert notifications."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "sendgrid-quota-warning"
  }
}

resource "aws_cloudwatch_metric_alarm" "sendgrid_quota_critical" {
  alarm_name          = "${var.environment}-sendgrid-quota-80-percent"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "EmailQuotaUsed"
  namespace           = "SentimentAnalyzer/Notifications"
  period              = 3600 # 1 hour
  statistic           = "Maximum"
  threshold           = 80 # 80 emails = 80% of daily limit
  alarm_description   = "CRITICAL: SendGrid email quota at 80% (80/100). Disable non-essential notifications."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "sendgrid-quota-critical"
    Severity    = "CRITICAL"
  }
}
