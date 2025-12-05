# CloudWatch Alarms for External API Health (Feature 006 - T171)
#
# For On-Call Engineers:
#   These alarms monitor Tiingo and Finnhub API error rates.
#   >5% error rate indicates potential API issues that need investigation.
#
# Runbook:
#   1. Check circuit breaker status in logs
#   2. Verify API credentials in Secrets Manager
#   3. Check API provider status pages
#   4. Consider temporary fallback to single source

# =============================================================================
# Tiingo API Error Rate Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "tiingo_error_rate" {
  alarm_name          = "${var.environment}-sentiment-tiingo-error-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5 # 5% error rate

  metric_query {
    id          = "error_rate"
    expression  = "(errors / calls) * 100"
    label       = "Tiingo Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "TiingoApiErrors"
      namespace   = "SentimentAnalyzer/Ingestion"
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "calls"
    metric {
      metric_name = "TiingoApiCalls"
      namespace   = "SentimentAnalyzer/Ingestion"
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_description  = "Tiingo API error rate > 5% for 15 minutes. Check circuit breaker and API credentials."
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Service     = "tiingo"
    Scenario    = "api-error-rate"
  }
}

# =============================================================================
# Finnhub API Error Rate Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "finnhub_error_rate" {
  alarm_name          = "${var.environment}-sentiment-finnhub-error-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  threshold           = 5 # 5% error rate

  metric_query {
    id          = "error_rate"
    expression  = "(errors / calls) * 100"
    label       = "Finnhub Error Rate %"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      metric_name = "FinnhubApiErrors"
      namespace   = "SentimentAnalyzer/Ingestion"
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "calls"
    metric {
      metric_name = "FinnhubApiCalls"
      namespace   = "SentimentAnalyzer/Ingestion"
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_description  = "Finnhub API error rate > 5% for 15 minutes. Check circuit breaker and API credentials."
  treat_missing_data = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Service     = "finnhub"
    Scenario    = "api-error-rate"
  }
}

# =============================================================================
# Circuit Breaker Open Alarm
# =============================================================================

resource "aws_cloudwatch_metric_alarm" "circuit_breaker_open" {
  alarm_name          = "${var.environment}-sentiment-circuit-breaker-open"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "CircuitBreakerOpen"
  namespace           = "SentimentAnalyzer/Ingestion"
  period              = 300
  statistic           = "Sum"
  threshold           = 0 # Any circuit breaker open event
  alarm_description   = "Circuit breaker opened for external API. Service degraded to single source."
  treat_missing_data  = "notBreaching"

  alarm_actions = [aws_sns_topic.alarms.arn]
  ok_actions    = [aws_sns_topic.alarms.arn]

  tags = {
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Scenario    = "circuit-breaker"
  }
}
