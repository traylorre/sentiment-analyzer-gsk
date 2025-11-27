# CloudWatch Alarm for Cost Monitoring (Feature 006 - T170)
#
# For On-Call Engineers:
#   This alarm monitors daily AWS cost burn rate.
#   $3.33/day threshold = $100/month budget.
#   Exceeding this rate may indicate runaway costs or attack.
#
# Runbook:
#   1. Check DynamoDB read/write usage (primary cost driver)
#   2. Review Lambda invocation counts
#   3. Check for unusual traffic patterns
#   4. Consider enabling API throttling if under attack

# =============================================================================
# Cost Burn Rate Alarm ($3.33/day = $100/month)
# =============================================================================

# Note: AWS Cost Explorer metrics have ~24hr delay
# For real-time cost monitoring, we use proxy metrics

# DynamoDB cost proxy - high read/write = high cost
resource "aws_cloudwatch_metric_alarm" "dynamodb_daily_cost_proxy" {
  alarm_name          = "${var.environment}-dynamodb-daily-cost-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 100000 # ~100K RCU/day = ~$1-2/day

  metric_query {
    id          = "daily_reads"
    expression  = "SUM(METRICS())"
    label       = "Daily DynamoDB Reads"
    return_data = true
  }

  metric_query {
    id = "reads"
    metric {
      metric_name = "ConsumedReadCapacityUnits"
      namespace   = "AWS/DynamoDB"
      period      = 86400 # 24 hours
      stat        = "Sum"
      dimensions = {
        TableName = "${var.environment}-sentiment-items"
      }
    }
  }

  alarm_description  = "DynamoDB daily read units > 100K. Estimated cost impact ~$1-2/day. Review usage patterns."
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "cost-burn-rate"
    CostCenter  = "dynamodb"
  }
}

# Lambda cost proxy - high invocations = higher cost
resource "aws_cloudwatch_metric_alarm" "lambda_daily_invocations" {
  alarm_name          = "${var.environment}-lambda-daily-invocations-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 50000 # 50K invocations/day

  metric_query {
    id          = "total"
    expression  = "dashboard + ingestion + analysis + notification"
    label       = "Total Lambda Invocations"
    return_data = true
  }

  metric_query {
    id = "dashboard"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 86400
      stat        = "Sum"
      dimensions = {
        FunctionName = "${var.environment}-sentiment-dashboard"
      }
    }
  }

  metric_query {
    id = "ingestion"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 86400
      stat        = "Sum"
      dimensions = {
        FunctionName = "${var.environment}-sentiment-ingestion"
      }
    }
  }

  metric_query {
    id = "analysis"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 86400
      stat        = "Sum"
      dimensions = {
        FunctionName = "${var.environment}-sentiment-analysis"
      }
    }
  }

  metric_query {
    id = "notification"
    metric {
      metric_name = "Invocations"
      namespace   = "AWS/Lambda"
      period      = 86400
      stat        = "Sum"
      dimensions = {
        FunctionName = "${var.environment}-sentiment-notification"
      }
    }
  }

  alarm_description  = "Total Lambda invocations > 50K/day. Review for potential abuse or runaway processes."
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "cost-burn-rate"
    CostCenter  = "lambda"
  }
}

# SNS cost proxy - message volume
resource "aws_cloudwatch_metric_alarm" "sns_daily_messages" {
  alarm_name          = "${var.environment}-sns-daily-messages-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "NumberOfMessagesPublished"
  namespace           = "AWS/SNS"
  period              = 86400 # 24 hours
  statistic           = "Sum"
  threshold           = 10000 # 10K messages/day
  alarm_description   = "SNS messages > 10K/day. Review ingestion and notification patterns."
  treat_missing_data  = "notBreaching"

  dimensions = {
    TopicName = "${var.environment}-sentiment-analysis-requests"
  }

  alarm_actions = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "cost-burn-rate"
    CostCenter  = "sns"
  }
}
