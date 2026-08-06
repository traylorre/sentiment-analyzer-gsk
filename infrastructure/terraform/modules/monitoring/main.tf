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
  name           = "${var.environment}-sentiment-dashboard-import-errors"
  log_group_name = "/aws/lambda/${var.environment}-sentiment-dashboard"
  pattern        = "[time, request_id, level=ERROR*, msg=\"*ImportModuleError*\" || msg=\"*No module named*\" || msg=\"*cannot import name*\"]"

  metric_transformation {
    name      = "DashboardImportErrors"
    namespace = "SentimentAnalyzer/Packaging"
    value     = "1"
    unit      = "Count"
  }
}

# =============================================================================
# Lambda Latency Alarms (SC-11, SC-12)
# =============================================================================

# =============================================================================
# SNS Delivery Alarm (SC-06)
# =============================================================================

# =============================================================================
# Custom Metric Alarms (SC-10)
# =============================================================================

# NOTE: NewsAPI alarm removed in Feature 006 - replaced by Tiingo/Finnhub alarms
# See api_alarms.tf for tiingo_error_rate and finnhub_error_rate alarms

# =============================================================================
# DLQ Depth Alarm (SC-09)
# =============================================================================

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

# =============================================================================
# SendGrid Email Quota Alarm (Feature 006 - T152)
# =============================================================================
# Monitors the custom metric for SendGrid email quota usage.
# The notification Lambda writes EmailQuotaUsed metric to CloudWatch.
# Alert at 50% to allow time to respond before hitting hard limit.
# =============================================================================

# =============================================================================
# Feature 1010: Cross-Source Collision Rate Alarms (SC-008)
# =============================================================================
# Monitors collision rate from parallel ingestion with Tiingo + Finnhub.
# Expected range: 15-25% for typical financial news overlap.
# Alerts when rate is too high (>40%) or too low (<5%) indicating issues.
# =============================================================================
