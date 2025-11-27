# CloudWatch Dashboard for Sentiment Analyzer (Feature 006 - T169)
#
# For On-Call Engineers:
#   This dashboard provides at-a-glance visibility into system health.
#   All metrics are organized by category for easy troubleshooting.
#
# Dashboard URL: https://console.aws.amazon.com/cloudwatch/home?region=${region}#dashboards:name=${dashboard_name}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.environment}-sentiment-analyzer"

  dashboard_body = jsonencode({
    widgets = [
      # Row 1: Lambda Invocations & Errors
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Invocations"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", "${var.environment}-sentiment-dashboard", { stat = "Sum", period = 300 }],
            [".", ".", ".", "${var.environment}-sentiment-ingestion", { stat = "Sum", period = 300 }],
            [".", ".", ".", "${var.environment}-sentiment-analysis", { stat = "Sum", period = 300 }],
            [".", ".", ".", "${var.environment}-sentiment-notification", { stat = "Sum", period = 300 }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Errors"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/Lambda", "Errors", "FunctionName", "${var.environment}-sentiment-dashboard", { stat = "Sum", period = 300, color = "#d62728" }],
            [".", ".", ".", "${var.environment}-sentiment-ingestion", { stat = "Sum", period = 300, color = "#ff7f0e" }],
            [".", ".", ".", "${var.environment}-sentiment-analysis", { stat = "Sum", period = 300, color = "#2ca02c" }],
            [".", ".", ".", "${var.environment}-sentiment-notification", { stat = "Sum", period = 300, color = "#9467bd" }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 0
        width  = 8
        height = 6
        properties = {
          title  = "Lambda Duration (P95)"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", "${var.environment}-sentiment-dashboard", { stat = "p95", period = 300 }],
            [".", ".", ".", "${var.environment}-sentiment-analysis", { stat = "p95", period = 300 }],
          ]
          view    = "timeSeries"
          yAxis   = { left = { min = 0 } }
          period  = 300
          stacked = false
        }
      },

      # Row 2: API & External Services
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "External API Calls"
          region = data.aws_region.current.name
          metrics = [
            ["SentimentAnalyzer/Ingestion", "TiingoApiCalls", { stat = "Sum", period = 300 }],
            [".", "FinnhubApiCalls", { stat = "Sum", period = 300 }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "External API Errors"
          region = data.aws_region.current.name
          metrics = [
            ["SentimentAnalyzer/Ingestion", "TiingoApiErrors", { stat = "Sum", period = 300, color = "#d62728" }],
            [".", "FinnhubApiErrors", { stat = "Sum", period = 300, color = "#ff7f0e" }],
            [".", "CircuitBreakerOpen", { stat = "Sum", period = 300, color = "#9467bd" }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 6
        width  = 8
        height = 6
        properties = {
          title  = "Email Notifications"
          region = data.aws_region.current.name
          metrics = [
            ["SentimentAnalyzer/Notifications", "EmailsSent", { stat = "Sum", period = 3600 }],
            [".", "EmailQuotaUsed", { stat = "Maximum", period = 3600 }],
            [".", "EmailsFailed", { stat = "Sum", period = 3600, color = "#d62728" }],
          ]
          view = "timeSeries"
        }
      },

      # Row 3: DynamoDB & SNS
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "DynamoDB Consumed Capacity"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", "${var.environment}-sentiment-items", { stat = "Sum", period = 300 }],
            [".", "ConsumedWriteCapacityUnits", ".", ".", { stat = "Sum", period = 300 }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 8
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "DynamoDB Throttled Requests"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/DynamoDB", "ThrottledRequests", "TableName", "${var.environment}-sentiment-items", { stat = "Sum", period = 300, color = "#d62728" }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 16
        y      = 12
        width  = 8
        height = 6
        properties = {
          title  = "SNS Messages"
          region = data.aws_region.current.name
          metrics = [
            ["AWS/SNS", "NumberOfMessagesPublished", "TopicName", "${var.environment}-sentiment-analysis-requests", { stat = "Sum", period = 300 }],
            [".", "NumberOfNotificationsDelivered", ".", ".", { stat = "Sum", period = 300 }],
            [".", "NumberOfNotificationsFailed", ".", ".", { stat = "Sum", period = 300, color = "#d62728" }],
          ]
          view = "timeSeries"
        }
      },

      # Row 4: Alarm Status
      {
        type   = "alarm"
        x      = 0
        y      = 18
        width  = 24
        height = 3
        properties = {
          title = "Active Alarms"
          alarms = [
            aws_cloudwatch_metric_alarm.ingestion_errors.arn,
            aws_cloudwatch_metric_alarm.analysis_errors.arn,
            aws_cloudwatch_metric_alarm.dashboard_errors.arn,
            aws_cloudwatch_metric_alarm.sendgrid_quota_warning.arn,
            aws_cloudwatch_metric_alarm.sendgrid_quota_critical.arn,
          ]
        }
      },

      # Row 5: Custom Business Metrics
      {
        type   = "metric"
        x      = 0
        y      = 21
        width  = 12
        height = 6
        properties = {
          title  = "Items Ingested & Analyzed"
          region = data.aws_region.current.name
          metrics = [
            ["SentimentAnalyzer", "NewItemsIngested", { stat = "Sum", period = 3600 }],
            [".", "ItemsAnalyzed", { stat = "Sum", period = 3600 }],
          ]
          view = "timeSeries"
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 21
        width  = 12
        height = 6
        properties = {
          title  = "Alerts Triggered"
          region = data.aws_region.current.name
          metrics = [
            ["SentimentAnalyzer/Alerts", "AlertsEvaluated", { stat = "Sum", period = 3600 }],
            [".", "AlertsTriggered", { stat = "Sum", period = 3600 }],
            [".", "NotificationsQueued", { stat = "Sum", period = 3600 }],
          ]
          view = "timeSeries"
        }
      },
    ]
  })
}

# Data source for current region
data "aws_region" "current" {}
