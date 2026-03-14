# X-Ray Groups and Sampling Rules Module
# =======================================
#
# Creates X-Ray groups for trace filtering and environment-specific
# sampling rules per contracts/xray-groups-sampling.md.
#
# Groups (5): sentiment-errors, live-traces, canary-traces,
#             sentiment-sse, sse-reconn
#
# Sampling: dev/preprod = 100%, prod = graduated (10%/5%/10%)

locals {
  common_tags = merge(var.tags, {
    Module = "xray"
  })

  is_prod = var.environment == "prod"
}

# ===================================================================
# X-Ray Groups (FR-111)
# ===================================================================

resource "aws_xray_group" "errors" {
  group_name        = "${var.environment}-sentiment-errors"
  filter_expression = "fault = true OR error = true"

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.common_tags
}

resource "aws_xray_group" "production_traces" {
  group_name        = "${var.environment}-sentiment-live-traces"
  filter_expression = "!annotation.synthetic"

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.common_tags
}

resource "aws_xray_group" "canary_traces" {
  group_name        = "${var.environment}-sentiment-canary-traces"
  filter_expression = "annotation.synthetic = true"

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.common_tags
}

resource "aws_xray_group" "sse" {
  group_name        = "${var.environment}-sentiment-sse"
  filter_expression = "service(\"sentiment-analyzer-sse\")"

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.common_tags
}

resource "aws_xray_group" "sse_reconnections" {
  group_name        = "${var.environment}-sentiment-sse-reconn"
  filter_expression = "annotation.previous_trace_id BEGINSWITH \"1-\""

  insights_configuration {
    insights_enabled      = true
    notifications_enabled = true
  }

  tags = local.common_tags
}

# ===================================================================
# Sampling Rules (FR-034, FR-161)
# ===================================================================
# Dev/Preprod: 100% sampling (reservoir=1, rate=1.0)
# Prod: Graduated sampling per service

# Dev/Preprod: Single catch-all rule at 100%
resource "aws_xray_sampling_rule" "non_prod" {
  count = local.is_prod ? 0 : 1

  rule_name      = "${var.environment}-sentiment-all"
  priority       = 1000
  reservoir_size = var.reservoir_size
  fixed_rate     = var.fixed_rate
  host           = "*"
  http_method    = "*"
  service_name   = "sentiment-analyzer-*"
  service_type   = "*"
  url_path       = "*"
  version        = 1
  resource_arn   = "*"

  tags = local.common_tags
}

# Prod: API Gateway traces (priority 100, 10% sampling)
resource "aws_xray_sampling_rule" "prod_apigw" {
  count = local.is_prod ? 1 : 0

  rule_name      = "prod-sentiment-apigw"
  priority       = 100
  reservoir_size = var.prod_apigw_reservoir_size
  fixed_rate     = var.prod_apigw_fixed_rate
  host           = "*"
  http_method    = "*"
  service_name   = "sentiment-analyzer-dashboard"
  service_type   = "*"
  url_path       = "*"
  version        = 1
  resource_arn   = "*"

  tags = local.common_tags
}

# Prod: Function URL traces (priority 200, 5% sampling)
resource "aws_xray_sampling_rule" "prod_fnurl" {
  count = local.is_prod ? 1 : 0

  rule_name      = "prod-sentiment-fnurl"
  priority       = 200
  reservoir_size = var.prod_fnurl_reservoir_size
  fixed_rate     = var.prod_fnurl_fixed_rate
  host           = "*"
  http_method    = "*"
  service_name   = "sentiment-analyzer-sse"
  service_type   = "*"
  url_path       = "*"
  version        = 1
  resource_arn   = "*"

  tags = local.common_tags
}

# Prod: Default catch-all (priority 9000, 10% sampling)
resource "aws_xray_sampling_rule" "prod_default" {
  count = local.is_prod ? 1 : 0

  rule_name      = "prod-sentiment-default"
  priority       = 9000
  reservoir_size = var.prod_default_reservoir_size
  fixed_rate     = var.prod_default_fixed_rate
  host           = "*"
  http_method    = "*"
  service_name   = "sentiment-analyzer-*"
  service_type   = "*"
  url_path       = "*"
  version        = 1
  resource_arn   = "*"

  tags = local.common_tags
}
