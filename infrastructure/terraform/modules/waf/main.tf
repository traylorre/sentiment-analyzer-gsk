# WAF v2 Module — Feature 1254
# ==============================
# Per-IP rate limiting, SQL injection, XSS, and bot detection.
# Reusable for API Gateway (REGIONAL) and CloudFront (CLOUDFRONT) via FR-009.
#
# Rule evaluation order (FR-008):
#   Priority 0: OPTIONS ALLOW (bypass rate counter — FR-010)
#   Priority 1: AWSManagedRulesCommonRuleSet (SQLi, XSS — FR-003, FR-004)
#   Priority 2: AWSManagedRulesKnownBadInputsRuleSet (Log4j, CVEs)
#   Priority 3: AWSManagedRulesBotControlRuleSet (COUNT → BLOCK — FR-005)
#   Priority 4: Per-IP rate-based (2000/5min — FR-002)
#   Default: ALLOW

# Custom response body for BLOCK actions (FR-006: CORS headers on WAF 403)
resource "aws_wafv2_web_acl" "main" {
  name        = "${var.environment}-sentiment-waf"
  description = "WAF for sentiment analyzer — rate limiting, SQLi, XSS, bots (Feature 1254)"
  scope       = var.scope

  default_action {
    allow {}
  }

  # FR-006: Custom response body with CORS headers for BLOCK actions
  custom_response_body {
    key          = "waf-blocked"
    content      = jsonencode({ message = "Request blocked by WAF", code = "WAF_BLOCKED" })
    content_type = "APPLICATION_JSON"
  }

  # ===================================================================
  # Rule 0 (Priority 0): OPTIONS ALLOW — FR-010
  # ===================================================================
  # Allows OPTIONS preflight requests to bypass rate counting.
  # CORS preflight is browser-generated, not user-initiated.
  rule {
    name     = "allow-options-preflight"
    priority = 0

    action {
      allow {}
    }

    statement {
      byte_match_statement {
        search_string         = "OPTIONS"
        positional_constraint = "EXACTLY"
        field_to_match {
          method {}
        }
        text_transformation {
          priority = 0
          type     = "NONE"
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.environment}-waf-options-allowed"
      sampled_requests_enabled   = false
    }
  }

  # ===================================================================
  # Rule 1 (Priority 1): AWS Managed Common Rules — FR-003, FR-004
  # ===================================================================
  # Includes SQL injection, XSS, size constraints, and known bad patterns.
  rule {
    name     = "aws-managed-common-rules"
    priority = 1

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.environment}-waf-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ===================================================================
  # Rule 2 (Priority 2): AWS Known Bad Inputs
  # ===================================================================
  # Log4j, Java deserialization, known CVE patterns.
  rule {
    name     = "aws-managed-known-bad-inputs"
    priority = 2

    override_action {
      none {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.environment}-waf-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # ===================================================================
  # Rule 3 (Priority 3): AWS Bot Control — FR-005
  # ===================================================================
  # Starts in COUNT mode for monitoring. Switch to BLOCK after verification.
  dynamic "rule" {
    for_each = var.enable_bot_control ? [1] : []
    content {
      name     = "aws-managed-bot-control"
      priority = 3

      override_action {
        dynamic "none" {
          for_each = var.bot_control_action == "BLOCK" ? [1] : []
          content {}
        }
        dynamic "count" {
          for_each = var.bot_control_action == "COUNT" ? [1] : []
          content {}
        }
      }

      statement {
        managed_rule_group_statement {
          name        = "AWSManagedRulesBotControlRuleSet"
          vendor_name = "AWS"

          managed_rule_group_configs {
            aws_managed_rules_bot_control_rule_set {
              inspection_level = "COMMON"
            }
          }
        }
      }

      visibility_config {
        cloudwatch_metrics_enabled = true
        metric_name                = "${var.environment}-waf-bot-control"
        sampled_requests_enabled   = true
      }
    }
  }

  # ===================================================================
  # Rule 4 (Priority 4): Per-IP Rate Limiting — FR-002
  # ===================================================================
  # Blocks IPs exceeding threshold in 5-minute sliding window.
  rule {
    name     = "per-ip-rate-limit"
    priority = 4

    action {
      block {
        custom_response {
          response_code            = 429
          custom_response_body_key = "waf-blocked"
          response_header {
            name  = "Access-Control-Allow-Origin"
            value = "*"
          }
          response_header {
            name  = "Access-Control-Allow-Methods"
            value = "GET,POST,PUT,DELETE,PATCH,OPTIONS"
          }
          response_header {
            name  = "Access-Control-Allow-Headers"
            value = "Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID"
          }
          response_header {
            name  = "Access-Control-Allow-Credentials"
            value = "true"
          }
        }
      }
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.environment}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.environment}-waf-acl"
    sampled_requests_enabled   = false
  }

  tags = merge(var.tags, {
    Name      = "${var.environment}-sentiment-waf"
    Component = "waf"
    Feature   = "1254"
  })
}

# ===================================================================
# WAF Association (FR-001, FR-011)
# ===================================================================
# Associates WebACL with the target resource.
# NOTE: For CLOUDFRONT scope, the association is done via web_acl_id on the
# CloudFront distribution resource itself, not via aws_wafv2_web_acl_association.
# This association resource is only created for REGIONAL scope (API Gateway).
resource "aws_wafv2_web_acl_association" "main" {
  count        = var.scope == "REGIONAL" && var.resource_arn != "" ? 1 : 0
  resource_arn = var.resource_arn
  web_acl_arn  = aws_wafv2_web_acl.main.arn
}

# ===================================================================
# CloudWatch Alarm — FR-007
# ===================================================================
# Alerts when blocked requests exceed threshold in 5 minutes.
resource "aws_cloudwatch_metric_alarm" "waf_blocked" {
  count = length(var.alarm_actions) > 0 ? 1 : 0

  alarm_name          = "${var.environment}-waf-blocked-requests"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "BlockedRequests"
  namespace           = "AWS/WAFV2"
  period              = 300
  statistic           = "Sum"
  threshold           = var.blocked_requests_threshold
  alarm_description   = "WAF blocked requests exceeded ${var.blocked_requests_threshold} in 5 minutes — possible attack"
  treat_missing_data  = "notBreaching"

  dimensions = {
    WebACL = aws_wafv2_web_acl.main.name
    Region = data.aws_region.current.name
    Rule   = "ALL"
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

data "aws_region" "current" {}
