# CloudWatch Alarm for Notification Delivery (Feature 006 - T172)
#
# For On-Call Engineers:
#   This alarm monitors email notification delivery success rate.
#   <95% success rate indicates potential SendGrid issues.
#
# Runbook:
#   1. Check SendGrid dashboard for delivery status
#   2. Verify SendGrid API key in Secrets Manager
#   3. Check for bounce/spam complaints in SendGrid
#   4. Review recent email template changes

# =============================================================================
# Notification Delivery Success Rate Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "notification_delivery_rate" {
  alarm_name          = "${var.environment}-sentiment-notification-delivery-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  threshold           = 95 # 95% success rate

  metric_query {
    id          = "success_rate"
    expression  = "IF(total > 0, (sent / total) * 100, 100)"
    label       = "Notification Delivery Rate %"
    return_data = true
  }

  metric_query {
    id = "sent"
    metric {
      metric_name = "EmailsSent"
      namespace   = "SentimentAnalyzer/Notifications"
      period      = 3600 # 1 hour
      stat        = "Sum"
    }
  }

  metric_query {
    id = "total"
    metric {
      metric_name = "EmailsAttempted"
      namespace   = "SentimentAnalyzer/Notifications"
      period      = 3600 # 1 hour
      stat        = "Sum"
    }
  }

  alarm_description  = "Email notification delivery rate < 95%. Check SendGrid status and credentials."
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "notification-delivery"
  }
}

# =============================================================================
# Alert Trigger Rate Alarm (Too Many Triggers)
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "alert_trigger_rate_high" {
  alarm_name          = "${var.environment}-sentiment-alert-triggers-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "AlertsTriggered"
  namespace           = "SentimentAnalyzer/Alerts"
  period              = 3600 # 1 hour
  statistic           = "Sum"
  threshold           = 50 # More than 50 alerts/hour indicates abnormal activity
  alarm_description   = "High alert trigger rate (>50/hr). May indicate market volatility or misconfigured thresholds."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "alert-storm"
  }
}

# =============================================================================
# Notification Lambda Errors Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "notification_lambda_errors" {
  alarm_name          = "${var.environment}-sentiment-notification-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 3
  alarm_description   = "Notification Lambda errors > 3 in 5 minutes. Email delivery may be impacted."
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = "${var.environment}-sentiment-notification"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "notification-errors"
  }
}
