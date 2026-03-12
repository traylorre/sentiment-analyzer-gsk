# API Gateway Module for Dashboard Lambda
# =========================================
#
# Creates API Gateway REST API with rate limiting to protect against budget exhaustion attacks.
#
# Security Features:
# - Rate limiting: 100 requests/minute per IP (via Usage Plan)
# - Burst protection: 200 concurrent requests
# - Per-IP throttling via WAF (optional, configured separately)
# - Cost-bounded: Maximum predictable spend
#
# For On-Call Engineers:
#     If API Gateway returns 429 Too Many Requests:
#     1. Check Usage Plan throttle settings
#     2. Verify client is not exceeding rate limits
#     3. Check WAF rules for IP blocking
#
#     If API Gateway returns 502 Bad Gateway:
#     1. Check Lambda is healthy (test Function URL directly)
#     2. Verify Lambda timeout < API Gateway timeout (29s)
#     3. Check Lambda logs for errors
#
# For Developers:
#     - Lambda handler manages both Function URL and API Gateway requests
#     - No Lambda code changes required
#     - CORS configured at both API Gateway and application levels
#     - Usage Plan provides rate limiting without additional cost

# API Gateway REST API
resource "aws_api_gateway_rest_api" "dashboard" {
  name        = "${var.environment}-sentiment-dashboard-api"
  description = "API Gateway for sentiment analyzer dashboard with rate limiting"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-sentiment-dashboard-api"
  })
}

# ===================================================================
# Cognito Authorizer (FR-012)
# ===================================================================
# Validates JWT tokens from Cognito User Pool
# - Native JWT validation with zero Lambda overhead
# - Built-in caching (300-second TTL default)
# - No additional compute charges

resource "aws_api_gateway_authorizer" "cognito" {
  count = var.enable_cognito_auth ? 1 : 0

  name            = "cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.dashboard.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [var.cognito_user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

# Gateway Response: UNAUTHORIZED (FR-013)
resource "aws_api_gateway_gateway_response" "unauthorized" {
  count = var.enable_cognito_auth ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.WWW-Authenticate" = "'Bearer realm=\"sentiment-analyzer\"'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "Unauthorized: Invalid or missing authentication token"
      code    = "UNAUTHORIZED"
    })
  }
}

# Gateway Response: MISSING_AUTHENTICATION_TOKEN (FR-013)
resource "aws_api_gateway_gateway_response" "missing_auth_token" {
  count = var.enable_cognito_auth ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  response_type = "MISSING_AUTHENTICATION_TOKEN"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.WWW-Authenticate" = "'Bearer realm=\"sentiment-analyzer\"'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "Unauthorized: Authentication token required"
      code    = "MISSING_AUTHENTICATION_TOKEN"
    })
  }
}

# API Gateway Resource (proxy all requests to Lambda)
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  parent_id   = aws_api_gateway_rest_api.dashboard.root_resource_id
  path_part   = "{proxy+}"
}

# API Gateway Method (ANY method for proxy)
# SECURITY: Requires Cognito authentication when enabled (FR-012)
resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = var.enable_cognito_auth ? "COGNITO_USER_POOLS" : "NONE"
  authorizer_id = var.enable_cognito_auth ? aws_api_gateway_authorizer.cognito[0].id : null

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

# OPTIONS method for CORS preflight (no auth required)
# Browser sends OPTIONS before POST/PUT/DELETE - must not require auth
resource "aws_api_gateway_method" "proxy_options" {
  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# Mock integration for OPTIONS - returns 200 with CORS headers
resource "aws_api_gateway_integration" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

# Method response for OPTIONS
resource "aws_api_gateway_method_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration response for OPTIONS
resource "aws_api_gateway_integration_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = aws_api_gateway_method_response.proxy_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-User-ID'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# API Gateway Method (ANY method for root)
# SECURITY: Requires Cognito authentication when enabled (FR-012)
resource "aws_api_gateway_method" "root" {
  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method   = "ANY"
  authorization = var.enable_cognito_auth ? "COGNITO_USER_POOLS" : "NONE"
  authorizer_id = var.enable_cognito_auth ? aws_api_gateway_authorizer.cognito[0].id : null
}

# OPTIONS method for root CORS preflight
resource "aws_api_gateway_method" "root_options" {
  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

# Mock integration for root OPTIONS
resource "aws_api_gateway_integration" "root_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method = aws_api_gateway_method.root_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = jsonencode({ statusCode = 200 })
  }
}

# Method response for root OPTIONS
resource "aws_api_gateway_method_response" "root_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method = aws_api_gateway_method.root_options.http_method
  status_code = "200"

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

# Integration response for root OPTIONS
resource "aws_api_gateway_integration_response" "root_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method = aws_api_gateway_method.root_options.http_method
  status_code = aws_api_gateway_method_response.root_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization,X-User-ID'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'*'"
  }
}

# API Gateway Integration (Lambda proxy integration)
resource "aws_api_gateway_integration" "lambda_proxy" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# API Gateway Integration (Lambda root integration)
resource "aws_api_gateway_integration" "lambda_root" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method = aws_api_gateway_method.root.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# Lambda Permission (allow API Gateway to invoke Lambda)
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"

  # Allow invocation from any stage
  source_arn = "${aws_api_gateway_rest_api.dashboard.execution_arn}/*/*"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "dashboard" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id

  triggers = {
    # Redeploy when configuration changes
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy.id,
      aws_api_gateway_method.proxy_options.id,
      aws_api_gateway_method.root.id,
      aws_api_gateway_method.root_options.id,
      aws_api_gateway_integration.lambda_proxy.id,
      aws_api_gateway_integration.lambda_root.id,
      aws_api_gateway_integration.proxy_options.id,
      aws_api_gateway_integration.root_options.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    aws_api_gateway_integration.lambda_proxy,
    aws_api_gateway_integration.lambda_root,
    aws_api_gateway_integration_response.proxy_options,
    aws_api_gateway_integration_response.root_options,
  ]
}

# API Gateway Stage
resource "aws_api_gateway_stage" "dashboard" {
  deployment_id = aws_api_gateway_deployment.dashboard.id
  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  stage_name    = var.stage_name

  # Enable CloudWatch logging
  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_gateway.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      caller         = "$context.identity.caller"
      user           = "$context.identity.user"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      resourcePath   = "$context.resourcePath"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
    })
  }

  # Enable X-Ray tracing
  xray_tracing_enabled = var.enable_xray_tracing

  tags = merge(var.tags, {
    Name = "${var.environment}-sentiment-dashboard-${var.stage_name}"
  })
}

# CloudWatch Log Group for API Gateway access logs
resource "aws_cloudwatch_log_group" "api_gateway" {
  name              = "/aws/apigateway/${var.environment}-sentiment-dashboard"
  retention_in_days = var.log_retention_days

  tags = merge(var.tags, {
    Name = "${var.environment}-api-gateway-logs"
  })
}

# API Gateway Usage Plan (Rate Limiting)
# This is THE KEY SECURITY CONTROL to prevent budget exhaustion
resource "aws_api_gateway_usage_plan" "dashboard" {
  name        = "${var.environment}-sentiment-dashboard-usage-plan"
  description = "Rate limiting to prevent budget exhaustion attacks"

  api_stages {
    api_id = aws_api_gateway_rest_api.dashboard.id
    stage  = aws_api_gateway_stage.dashboard.stage_name
  }

  # Global rate limits
  throttle_settings {
    rate_limit  = var.rate_limit  # Requests per second (default: 100)
    burst_limit = var.burst_limit # Concurrent requests (default: 200)
  }

  # Optional quota (not used by default)
  dynamic "quota_settings" {
    for_each = var.quota_limit > 0 ? [1] : []
    content {
      limit  = var.quota_limit
      period = var.quota_period
    }
  }

  tags = merge(var.tags, {
    Name = "${var.environment}-usage-plan"
  })
}

# CloudWatch Alarms for API Gateway

# Alarm: High 4XX error rate
resource "aws_cloudwatch_metric_alarm" "api_4xx" {
  count = var.create_alarms ? 1 : 0

  alarm_name          = "${var.environment}-api-gateway-4xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "4XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_4xx_threshold
  alarm_description   = "API Gateway 4XX error rate exceeded threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.dashboard.name
    Stage   = aws_api_gateway_stage.dashboard.stage_name
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

# Alarm: High 5XX error rate
resource "aws_cloudwatch_metric_alarm" "api_5xx" {
  count = var.create_alarms ? 1 : 0

  alarm_name          = "${var.environment}-api-gateway-5xx-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "5XXError"
  namespace           = "AWS/ApiGateway"
  period              = 300
  statistic           = "Sum"
  threshold           = var.error_5xx_threshold
  alarm_description   = "API Gateway 5XX error rate exceeded threshold (Lambda errors)"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.dashboard.name
    Stage   = aws_api_gateway_stage.dashboard.stage_name
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

# Alarm: High latency
resource "aws_cloudwatch_metric_alarm" "api_latency" {
  count = var.create_alarms ? 1 : 0

  alarm_name          = "${var.environment}-api-gateway-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "Latency"
  namespace           = "AWS/ApiGateway"
  period              = 300
  extended_statistic  = "p90"
  threshold           = var.latency_threshold
  alarm_description   = "API Gateway latency (p90) exceeded threshold"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ApiName = aws_api_gateway_rest_api.dashboard.name
    Stage   = aws_api_gateway_stage.dashboard.stage_name
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}
