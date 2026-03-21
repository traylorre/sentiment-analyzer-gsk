# CloudWatch Alarms Module -- Phase 1
# ====================================
#
# ~18 high-signal alarms ($1.80/mo) per contracts/cloudwatch-alarms.md.
# Phase 2 (T111) adds ~20 more post-dual-emit.
#
# Categories:
# 1. Lambda Errors (6)
# 2. Lambda Latency P95 (6)
# 3. Lambda Throttles (6) -- chaos-readiness
# 4. Silent Failure composite (1)
# 5. Canary heartbeat + completeness (2)
# 6. API Gateway + Function URL (3)
# 7. SSE Connection Count (1) -- chaos-readiness
# 8. Composite (1)
#
# Total Phase 1: ~26 alarms

locals {
  common_tags = merge(var.tags, {
    Module = "cloudwatch-alarms"
  })

  lambda_services = ["ingestion", "analysis", "dashboard", "notification", "metrics", "sse"]

  lambda_function_name_map = {
    ingestion    = var.lambda_function_names.ingestion
    analysis     = var.lambda_function_names.analysis
    dashboard    = var.lambda_function_names.dashboard
    notification = var.lambda_function_names.notification
    metrics      = var.lambda_function_names.metrics
    sse          = var.lambda_function_names.sse
  }

  latency_threshold_map = {
    ingestion    = var.latency_thresholds.ingestion
    analysis     = var.latency_thresholds.analysis
    dashboard    = var.latency_thresholds.dashboard
    notification = var.latency_thresholds.notification
    metrics      = var.latency_thresholds.metrics
    sse          = var.latency_thresholds.sse
  }

  # Silent failure paths per FR-142
  silent_failure_paths = [
    "circuit_breaker_load",
    "circuit_breaker_save",
    "audit_trail",
    "notification_delivery",
    "self_healing_fetch",
    "fanout_partial_write",
    "parallel_fetcher_aggregate",
  ]
}

# ===================================================================
# Category 1: Lambda Error Alarms (FR-040, FR-162)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  for_each = toset(local.lambda_services)

  alarm_name          = "${var.environment}-${each.key}-lambda-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_threshold
  alarm_description   = "${each.key} Lambda error rate exceeded threshold"
  treat_missing_data  = "missing"

  dimensions = {
    FunctionName = local.lambda_function_name_map[each.key]
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 2: Lambda Latency P95 Alarms (FR-041, FR-128)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_latency" {
  for_each = toset(local.lambda_services)

  alarm_name          = "${var.environment}-${each.key}-lambda-latency-p95"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "Duration"
  namespace           = "AWS/Lambda"
  period              = 300
  extended_statistic  = "p95"
  threshold           = local.latency_threshold_map[each.key]
  alarm_description   = "${each.key} Lambda P95 latency exceeded ${local.latency_threshold_map[each.key]}ms"
  treat_missing_data  = "missing"

  dimensions = {
    FunctionName = local.lambda_function_name_map[each.key]
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 3: Lambda Throttle Alarms (chaos-readiness)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "lambda_throttles" {
  for_each = toset(local.lambda_services)

  alarm_name          = "${var.environment}-${each.key}-lambda-throttles"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "Throttles"
  namespace           = "AWS/Lambda"
  period              = 60
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda ${each.key} is being throttled (reserved concurrency exceeded)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = local.lambda_function_name_map[each.key]
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 4: Silent Failure Composite Alarm (FR-134)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "silent_failure_composite" {
  alarm_name          = "${var.environment}-silent-failure-any"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "SilentFailure/Count"
  namespace           = "SentimentAnalyzer/Reliability"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Any silent failure path triggered (FR-134)"
  treat_missing_data  = "missing"

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 7: Canary Alarms (FR-121)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "canary_heartbeat" {
  count = var.canary_function_name != "" ? 1 : 0

  alarm_name          = "${var.environment}-canary-heartbeat"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CanaryHealth"
  namespace           = "SentimentAnalyzer/Canary"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "X-Ray canary heartbeat missing -- treat_missing_data=breaching (FR-121)"
  treat_missing_data  = "breaching"

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "canary_completeness" {
  count = var.canary_function_name != "" ? 1 : 0

  alarm_name          = "${var.environment}-canary-completeness"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "completeness_ratio"
  namespace           = "SentimentAnalyzer/Canary"
  period              = 300
  statistic           = "Average"
  threshold           = var.canary_completeness_threshold
  alarm_description   = "Canary trace completeness below ${var.canary_completeness_threshold}"
  treat_missing_data  = "breaching"

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 8: API Gateway + Function URL (FR-138)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "apigw_integration_latency" {
  count = var.api_gateway_name != "" ? 1 : 0

  alarm_name          = "${var.environment}-apigw-integration-latency-p99"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "IntegrationLatency"
  namespace           = "AWS/ApiGateway"
  period              = 300
  extended_statistic  = "p99"
  threshold           = var.api_gateway_latency_threshold
  alarm_description   = "API Gateway IntegrationLatency P99 exceeded threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = var.api_gateway_name
    Stage   = var.api_gateway_stage
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "apigw_5xx" {
  count = var.api_gateway_name != "" ? 1 : 0

  alarm_name          = "${var.environment}-apigw-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "API Gateway 5XX errors detected"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = var.api_gateway_name
    Stage   = var.api_gateway_stage
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "fnurl_5xx" {
  alarm_name          = "${var.environment}-fnurl-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Url5xxError"
  namespace           = "AWS/Lambda"
  period              = 300
  statistic           = "Sum"
  threshold           = 0
  alarm_description   = "Lambda Function URL 5XX errors detected"
  treat_missing_data  = "notBreaching"

  dimensions = {
    FunctionName = local.lambda_function_name_map["sse"]
  }

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Category 9: SSE Connection Count Alarm (chaos-readiness)
# ===================================================================

resource "aws_cloudwatch_metric_alarm" "sse_connection_count" {
  alarm_name          = "${var.environment}-sse-high-connection-count"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ActiveConnections"
  namespace           = "SentimentAnalyzer/SSE"
  period              = 60
  statistic           = "Maximum"
  threshold           = var.sse_max_connections * 0.8
  alarm_description   = "SSE active connections exceeded 80% of ${var.sse_max_connections} max"
  treat_missing_data  = "notBreaching"

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}

# ===================================================================
# Composite Alarm -- All Critical Tier (FR-129)
# ===================================================================

resource "aws_cloudwatch_composite_alarm" "critical" {
  alarm_name        = "${var.environment}-critical-composite"
  alarm_description = "Composite: any Critical-tier alarm firing (FR-129)"

  alarm_rule = join(" OR ", concat(
    [for svc in local.lambda_services :
      "ALARM(${aws_cloudwatch_metric_alarm.lambda_errors[svc].alarm_name})"
    ],
    [for svc in local.lambda_services :
      "ALARM(${aws_cloudwatch_metric_alarm.lambda_throttles[svc].alarm_name})"
    ],
    [
      "ALARM(${aws_cloudwatch_metric_alarm.silent_failure_composite.alarm_name})",
      "ALARM(${aws_cloudwatch_metric_alarm.fnurl_5xx.alarm_name})",
    ],
    var.canary_function_name != "" ? [
      "ALARM(${aws_cloudwatch_metric_alarm.canary_heartbeat[0].alarm_name})",
    ] : [],
    var.api_gateway_name != "" ? [
      "ALARM(${aws_cloudwatch_metric_alarm.apigw_5xx[0].alarm_name})",
    ] : [],
  ))

  alarm_actions = var.alarm_actions
  ok_actions    = var.ok_actions

  tags = local.common_tags
}
