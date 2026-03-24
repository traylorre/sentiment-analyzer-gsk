# CloudFront Distribution for SSE Streaming — Feature 1255
# =========================================================
# Routes SSE traffic through CloudFront edge with WAF + Shield Standard.
# No caching (SSE is real-time). 180s origin timeout for streaming.
#
# FR-001: CloudFront with Lambda Function URL origin
# FR-002: CachingDisabled for all paths
# FR-003: 180s origin read timeout
# FR-004: Forward auth + trace headers
# FR-005: WAF WebACL association
# FR-009: PriceClass_100
# FR-010: Shield Standard automatic

locals {
  # Extract domain from Lambda Function URL (remove https:// prefix)
  origin_domain = replace(replace(var.origin_url, "https://", ""), "/", "")
  origin_id     = "${var.environment}-sse-lambda-origin"
}

# ===================================================================
# Origin Request Policy (FR-004)
# ===================================================================
# Forward auth and trace headers to Lambda origin.
# SSE connections need Authorization, Last-Event-ID (reconnection),
# and trace headers for observability.
resource "aws_cloudfront_origin_request_policy" "sse_headers" {
  name    = "${var.environment}-sse-origin-request-policy"
  comment = "Forward auth and trace headers for SSE streaming (Feature 1255)"

  cookies_config {
    cookie_behavior = "all" # Forward all cookies (refresh token in httpOnly cookie)
  }

  headers_config {
    header_behavior = "whitelist"
    headers {
      items = [
        "Authorization",
        "Origin",
        "Last-Event-ID",
        "X-User-ID",
        "X-Amzn-Trace-Id",
        "Accept",
      ]
    }
  }

  query_strings_config {
    query_string_behavior = "all" # Forward all query strings (filter params)
  }
}

# ===================================================================
# Origin Access Control for Lambda (Feature 1256 — FR-003, FR-004)
# ===================================================================
# Signs requests to Lambda Function URL with SigV4.
# Required when Lambda Function URL has authorization_type = AWS_IAM.
resource "aws_cloudfront_origin_access_control" "lambda_oac" {
  name                              = "${var.environment}-sse-lambda-oac"
  description                       = "OAC for SSE Lambda Function URL (Feature 1256)"
  origin_access_control_origin_type = "lambda"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ===================================================================
# CloudFront Distribution (FR-001, FR-002, FR-003, FR-009)
# ===================================================================
resource "aws_cloudfront_distribution" "sse" {
  comment             = "${var.environment} SSE streaming via CloudFront (Feature 1255)"
  enabled             = true
  is_ipv6_enabled     = true
  http_version        = "http2and3"
  price_class         = var.price_class
  wait_for_deployment = false # Don't block terraform apply on propagation

  # FR-005: WAF WebACL association (CLOUDFRONT scope)
  web_acl_id = var.waf_web_acl_arn != "" ? var.waf_web_acl_arn : null

  # SSE Lambda Function URL origin with OAC (Feature 1256)
  # OAC signs requests with SigV4 for authorization_type=AWS_IAM
  origin {
    domain_name              = local.origin_domain
    origin_id                = local.origin_id
    origin_access_control_id = aws_cloudfront_origin_access_control.lambda_oac.id

    custom_origin_config {
      http_port                = 80
      https_port               = 443
      origin_protocol_policy   = "https-only"
      origin_ssl_protocols     = ["TLSv1.2"]
      origin_read_timeout      = var.origin_read_timeout      # FR-003: 180s for streaming
      origin_keepalive_timeout = var.origin_keepalive_timeout # 60s default
    }
  }

  # Default cache behavior — NO caching for SSE (FR-002)
  default_cache_behavior {
    target_origin_id       = local.origin_id
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    compress               = false # Don't compress SSE streams

    # CachingDisabled managed policy — no caching whatsoever
    cache_policy_id = "4135ea2d-6df8-44a3-9df3-4b5a84be39ad" # AWS Managed CachingDisabled

    # Custom origin request policy — forward auth headers (FR-004)
    origin_request_policy_id = aws_cloudfront_origin_request_policy.sse_headers.id
  }

  # No custom error pages — let Lambda handle errors
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Default CloudFront certificate (*.cloudfront.net)
  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(var.tags, {
    Name      = "${var.environment}-sse-cloudfront"
    Component = "cloudfront-sse"
    Feature   = "1255"
  })
}

# ===================================================================
# Lambda Permission for CloudFront OAC (Feature 1256 — FR-004)
# ===================================================================
# Allows CloudFront to invoke SSE Lambda via Function URL using OAC SigV4.
resource "aws_lambda_permission" "cloudfront_oac" {
  count = var.lambda_function_arn != "" ? 1 : 0

  statement_id  = "AllowCloudFrontOACInvoke"
  action        = "lambda:InvokeFunctionUrl"
  function_name = var.lambda_function_arn
  principal     = "cloudfront.amazonaws.com"
  source_arn    = aws_cloudfront_distribution.sse.arn

  function_url_auth_type = "AWS_IAM"
}
