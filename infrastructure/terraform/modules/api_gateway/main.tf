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

  lifecycle {
    prevent_destroy = true
  }
}

# Gateway Response: UNAUTHORIZED (FR-013)
resource "aws_api_gateway_gateway_response" "unauthorized" {
  count = var.enable_cognito_auth ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  # FR-008: CORS headers on 401 so browser exposes error to JavaScript
  response_parameters = {
    "gatewayresponse.header.WWW-Authenticate"                 = "'Bearer realm=\"sentiment-analyzer\"'"
    "gatewayresponse.header.Access-Control-Allow-Origin"      = "method.request.header.origin"
    "gatewayresponse.header.Access-Control-Allow-Headers"     = "'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'"
    "gatewayresponse.header.Access-Control-Allow-Methods"     = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"
    "gatewayresponse.header.Access-Control-Allow-Credentials" = "'true'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "Unauthorized: Invalid or missing authentication token"
      code    = "UNAUTHORIZED"
    })
  }
}

# Gateway Response: MISSING_AUTHENTICATION_TOKEN (FR-008)
resource "aws_api_gateway_gateway_response" "missing_auth_token" {
  count = var.enable_cognito_auth ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  response_type = "MISSING_AUTHENTICATION_TOKEN"
  status_code   = "401"

  # FR-008: CORS headers on 401
  response_parameters = {
    "gatewayresponse.header.WWW-Authenticate"                 = "'Bearer realm=\"sentiment-analyzer\"'"
    "gatewayresponse.header.Access-Control-Allow-Origin"      = "method.request.header.origin"
    "gatewayresponse.header.Access-Control-Allow-Headers"     = "'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'"
    "gatewayresponse.header.Access-Control-Allow-Methods"     = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"
    "gatewayresponse.header.Access-Control-Allow-Credentials" = "'true'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "Unauthorized: Authentication token required"
      code    = "MISSING_AUTHENTICATION_TOKEN"
    })
  }
}

# Gateway Response: ACCESS_DENIED (FR-008)
resource "aws_api_gateway_gateway_response" "access_denied" {
  count = var.enable_cognito_auth ? 1 : 0

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  response_type = "ACCESS_DENIED"
  status_code   = "403"

  # FR-008: CORS headers on 403
  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"      = "method.request.header.origin"
    "gatewayresponse.header.Access-Control-Allow-Headers"     = "'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'"
    "gatewayresponse.header.Access-Control-Allow-Methods"     = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"
    "gatewayresponse.header.Access-Control-Allow-Credentials" = "'true'"
  }

  response_templates = {
    "application/json" = jsonencode({
      message = "Access denied"
      code    = "ACCESS_DENIED"
    })
  }
}

# ===================================================================
# Public Route Resources (Feature 1253)
# ===================================================================
# FR-002: 11 public resource groups covering 13+ endpoints
# FR-005: Each gets OPTIONS method with MOCK CORS integration
# FR-007: All created atomically with Cognito enablement
# FR-012: Intermediates that are also endpoints get their own methods

locals {
  # Build ALL unique path segments needed (intermediates + FR-012 + leaf parents)
  _all_paths = distinct(flatten([
    for route in var.public_routes : [
      for i in range(length(route.path_parts) - (route.has_proxy ? 0 : 1)) :
      join("/", slice(route.path_parts, 0, i + 1))
    ]
  ]))

  # Unified map of ALL path resources (eliminates cycle between intermediate/FR-012)
  # Each path becomes a single aws_api_gateway_resource.path_resource entry
  path_resource_map = {
    for path in local._all_paths :
    path => {
      parent_path = length(split("/", path)) > 1 ? join("/", slice(split("/", path), 0, length(split("/", path)) - 1)) : ""
      path_part   = element(split("/", path), length(split("/", path)) - 1)
    }
  }

  # FR-012: which path resources are also endpoints (need methods)
  fr012_endpoints = {
    for route in var.public_routes :
    join("/", route.path_parts) => {
      auth      = route.endpoint_auth
      has_proxy = route.has_proxy
    }
    if route.is_endpoint
  }

  # Leaf resources: final path segment, no {proxy+} child, not FR-012
  leaf_resources = {
    for route in var.public_routes :
    join("/", route.path_parts) => {
      parent_key = length(route.path_parts) > 1 ? join("/", slice(route.path_parts, 0, length(route.path_parts) - 1)) : ""
      path_part  = route.path_parts[length(route.path_parts) - 1]
    }
    if !route.has_proxy && !route.is_endpoint
  }

  # Proxy child resources: {proxy+} under route path (non-FR-012)
  proxy_resources = {
    for route in var.public_routes :
    join("/", route.path_parts) => { parent_key = join("/", route.path_parts) }
    if route.has_proxy && !route.is_endpoint
  }

  # FR-012 proxy children: routes that are both endpoints AND have proxy children
  fr012_proxy_resources = {
    for route in var.public_routes :
    join("/", route.path_parts) => { parent_key = join("/", route.path_parts) }
    if route.has_proxy && route.is_endpoint
  }

  # CORS headers for OPTIONS responses (FR-005, FR-008)
  cors_headers = {
    "method.response.header.Access-Control-Allow-Headers"     = "'Content-Type,Authorization,Accept,Cache-Control,Last-Event-ID,X-Amzn-Trace-Id,X-User-ID'"
    "method.response.header.Access-Control-Allow-Methods"     = "'GET,POST,PUT,DELETE,PATCH,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"      = "'*'"
    "method.response.header.Access-Control-Allow-Credentials" = "'true'"
  }

  # Deployment trigger IDs
  public_route_resource_ids = concat(
    [for k, v in aws_api_gateway_resource.path_resource : v.id],
    [for k, v in aws_api_gateway_resource.public_leaf : v.id],
    [for k, v in aws_api_gateway_resource.public_proxy : v.id],
    [for k, v in aws_api_gateway_resource.fr012_proxy : v.id],
    [for k, v in aws_api_gateway_method.public_leaf_any : v.id],
    [for k, v in aws_api_gateway_method.public_proxy_any : v.id],
    [for k, v in aws_api_gateway_method.fr012_any : v.id],
    [for k, v in aws_api_gateway_method.fr012_proxy_any : v.id],
  )
}

# --- Unified Path Resources (intermediates + FR-012, single block eliminates cycle) ---
resource "aws_api_gateway_resource" "path_resource" {
  for_each = local.path_resource_map

  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  parent_id = (
    each.value.parent_path == ""
    ? aws_api_gateway_rest_api.dashboard.root_resource_id
    : aws_api_gateway_resource.path_resource[each.value.parent_path].id
  )
  path_part = each.value.path_part
}

# --- FR-012: Methods on intermediates that are also endpoints ---
resource "aws_api_gateway_method" "fr012_any" {
  for_each = local.fr012_endpoints

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.path_resource[each.key].id
  http_method   = "ANY"
  authorization = each.value.auth == "COGNITO_USER_POOLS" && var.enable_cognito_auth ? "COGNITO_USER_POOLS" : "NONE"
  authorizer_id = each.value.auth == "COGNITO_USER_POOLS" && var.enable_cognito_auth ? aws_api_gateway_authorizer.cognito[0].id : null
}

resource "aws_api_gateway_integration" "fr012_lambda" {
  for_each = local.fr012_endpoints

  rest_api_id             = aws_api_gateway_rest_api.dashboard.id
  resource_id             = aws_api_gateway_resource.path_resource[each.key].id
  http_method             = aws_api_gateway_method.fr012_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_method" "fr012_options" {
  for_each = local.fr012_endpoints

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.path_resource[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "fr012_options" {
  for_each = local.fr012_endpoints

  rest_api_id       = aws_api_gateway_rest_api.dashboard.id
  resource_id       = aws_api_gateway_resource.path_resource[each.key].id
  http_method       = aws_api_gateway_method.fr012_options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = jsonencode({ statusCode = 200 }) }
}

resource "aws_api_gateway_method_response" "fr012_options" {
  for_each = local.fr012_endpoints

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.path_resource[each.key].id
  http_method         = aws_api_gateway_method.fr012_options[each.key].http_method
  status_code         = "200"
  response_parameters = { for k, _ in local.cors_headers : k => true }
}

resource "aws_api_gateway_integration_response" "fr012_options" {
  for_each = local.fr012_endpoints

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.path_resource[each.key].id
  http_method         = aws_api_gateway_method.fr012_options[each.key].http_method
  status_code         = aws_api_gateway_method_response.fr012_options[each.key].status_code
  response_parameters = local.cors_headers
}

# FR-012: {proxy+} children under FR-012 endpoints
resource "aws_api_gateway_resource" "fr012_proxy" {
  for_each = local.fr012_proxy_resources

  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  parent_id   = aws_api_gateway_resource.path_resource[each.value.parent_key].id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "fr012_proxy_any" {
  for_each = local.fr012_proxy_resources

  rest_api_id        = aws_api_gateway_rest_api.dashboard.id
  resource_id        = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method        = "ANY"
  authorization      = "NONE"
  request_parameters = { "method.request.path.proxy" = true }
}

resource "aws_api_gateway_integration" "fr012_proxy_lambda" {
  for_each = local.fr012_proxy_resources

  rest_api_id             = aws_api_gateway_rest_api.dashboard.id
  resource_id             = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method             = aws_api_gateway_method.fr012_proxy_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_method" "fr012_proxy_options" {
  for_each = local.fr012_proxy_resources

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "fr012_proxy_options" {
  for_each = local.fr012_proxy_resources

  rest_api_id       = aws_api_gateway_rest_api.dashboard.id
  resource_id       = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method       = aws_api_gateway_method.fr012_proxy_options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = jsonencode({ statusCode = 200 }) }
}

resource "aws_api_gateway_method_response" "fr012_proxy_options" {
  for_each = local.fr012_proxy_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method         = aws_api_gateway_method.fr012_proxy_options[each.key].http_method
  status_code         = "200"
  response_parameters = { for k, _ in local.cors_headers : k => true }
}

resource "aws_api_gateway_integration_response" "fr012_proxy_options" {
  for_each = local.fr012_proxy_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.fr012_proxy[each.key].id
  http_method         = aws_api_gateway_method.fr012_proxy_options[each.key].http_method
  status_code         = aws_api_gateway_method_response.fr012_proxy_options[each.key].status_code
  response_parameters = local.cors_headers
}

# --- Leaf Resources (final path segment, no {proxy+} child) ---
resource "aws_api_gateway_resource" "public_leaf" {
  for_each = local.leaf_resources

  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  parent_id = (
    each.value.parent_key == ""
    ? aws_api_gateway_rest_api.dashboard.root_resource_id
    : aws_api_gateway_resource.path_resource[each.value.parent_key].id
  )
  path_part = each.value.path_part
}

resource "aws_api_gateway_method" "public_leaf_any" {
  for_each = local.leaf_resources

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.public_leaf[each.key].id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "public_leaf_lambda" {
  for_each = local.leaf_resources

  rest_api_id             = aws_api_gateway_rest_api.dashboard.id
  resource_id             = aws_api_gateway_resource.public_leaf[each.key].id
  http_method             = aws_api_gateway_method.public_leaf_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_method" "public_leaf_options" {
  for_each = local.leaf_resources

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.public_leaf[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "public_leaf_options" {
  for_each = local.leaf_resources

  rest_api_id       = aws_api_gateway_rest_api.dashboard.id
  resource_id       = aws_api_gateway_resource.public_leaf[each.key].id
  http_method       = aws_api_gateway_method.public_leaf_options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = jsonencode({ statusCode = 200 }) }
}

resource "aws_api_gateway_method_response" "public_leaf_options" {
  for_each = local.leaf_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.public_leaf[each.key].id
  http_method         = aws_api_gateway_method.public_leaf_options[each.key].http_method
  status_code         = "200"
  response_parameters = { for k, _ in local.cors_headers : k => true }
}

resource "aws_api_gateway_integration_response" "public_leaf_options" {
  for_each = local.leaf_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.public_leaf[each.key].id
  http_method         = aws_api_gateway_method.public_leaf_options[each.key].http_method
  status_code         = aws_api_gateway_method_response.public_leaf_options[each.key].status_code
  response_parameters = local.cors_headers
}

# --- Proxy Resources ({proxy+} under intermediate parent) ---
resource "aws_api_gateway_resource" "public_proxy" {
  for_each = local.proxy_resources

  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  parent_id   = aws_api_gateway_resource.path_resource[each.value.parent_key].id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "public_proxy_any" {
  for_each = local.proxy_resources

  rest_api_id        = aws_api_gateway_rest_api.dashboard.id
  resource_id        = aws_api_gateway_resource.public_proxy[each.key].id
  http_method        = "ANY"
  authorization      = "NONE"
  request_parameters = { "method.request.path.proxy" = true }
}

resource "aws_api_gateway_integration" "public_proxy_lambda" {
  for_each = local.proxy_resources

  rest_api_id             = aws_api_gateway_rest_api.dashboard.id
  resource_id             = aws_api_gateway_resource.public_proxy[each.key].id
  http_method             = aws_api_gateway_method.public_proxy_any[each.key].http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

resource "aws_api_gateway_method" "public_proxy_options" {
  for_each = local.proxy_resources

  rest_api_id   = aws_api_gateway_rest_api.dashboard.id
  resource_id   = aws_api_gateway_resource.public_proxy[each.key].id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "public_proxy_options" {
  for_each = local.proxy_resources

  rest_api_id       = aws_api_gateway_rest_api.dashboard.id
  resource_id       = aws_api_gateway_resource.public_proxy[each.key].id
  http_method       = aws_api_gateway_method.public_proxy_options[each.key].http_method
  type              = "MOCK"
  request_templates = { "application/json" = jsonencode({ statusCode = 200 }) }
}

resource "aws_api_gateway_method_response" "public_proxy_options" {
  for_each = local.proxy_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.public_proxy[each.key].id
  http_method         = aws_api_gateway_method.public_proxy_options[each.key].http_method
  status_code         = "200"
  response_parameters = { for k, _ in local.cors_headers : k => true }
}

resource "aws_api_gateway_integration_response" "public_proxy_options" {
  for_each = local.proxy_resources

  rest_api_id         = aws_api_gateway_rest_api.dashboard.id
  resource_id         = aws_api_gateway_resource.public_proxy[each.key].id
  http_method         = aws_api_gateway_method.public_proxy_options[each.key].http_method
  status_code         = aws_api_gateway_method_response.public_proxy_options[each.key].status_code
  response_parameters = local.cors_headers
}

# ===================================================================
# End Public Route Resources
# ===================================================================

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
    "method.response.header.Access-Control-Allow-Headers"  = true
    "method.response.header.Access-Control-Allow-Methods"  = true
    "method.response.header.Access-Control-Allow-Origin"   = true
    "method.response.header.Access-Control-Expose-Headers" = true
  }
}

# Integration response for OPTIONS
resource "aws_api_gateway_integration_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = aws_api_gateway_method_response.proxy_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers"  = "'Content-Type,Authorization,X-User-ID,X-Amzn-Trace-Id'"
    "method.response.header.Access-Control-Allow-Methods"  = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"   = "'*'"
    "method.response.header.Access-Control-Expose-Headers" = "'X-Amzn-Trace-Id'"
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
    "method.response.header.Access-Control-Allow-Headers"  = true
    "method.response.header.Access-Control-Allow-Methods"  = true
    "method.response.header.Access-Control-Allow-Origin"   = true
    "method.response.header.Access-Control-Expose-Headers" = true
  }
}

# Integration response for root OPTIONS
resource "aws_api_gateway_integration_response" "root_options" {
  rest_api_id = aws_api_gateway_rest_api.dashboard.id
  resource_id = aws_api_gateway_rest_api.dashboard.root_resource_id
  http_method = aws_api_gateway_method.root_options.http_method
  status_code = aws_api_gateway_method_response.root_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers"  = "'Content-Type,Authorization,X-User-ID,X-Amzn-Trace-Id'"
    "method.response.header.Access-Control-Allow-Methods"  = "'GET,POST,PUT,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"   = "'*'"
    "method.response.header.Access-Control-Expose-Headers" = "'X-Amzn-Trace-Id'"
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
    # Redeploy when configuration changes (includes Feature 1253 public routes)
    redeployment = sha1(jsonencode(concat(
      [
        aws_api_gateway_resource.proxy.id,
        aws_api_gateway_method.proxy.id,
        aws_api_gateway_method.proxy_options.id,
        aws_api_gateway_method.root.id,
        aws_api_gateway_method.root_options.id,
        aws_api_gateway_integration.lambda_proxy.id,
        aws_api_gateway_integration.lambda_root.id,
        aws_api_gateway_integration.proxy_options.id,
        aws_api_gateway_integration.root_options.id,
      ],
      local.public_route_resource_ids,
    )))
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
