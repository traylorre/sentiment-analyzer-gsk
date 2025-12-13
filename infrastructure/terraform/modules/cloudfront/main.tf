# CloudFront Distribution for Feature 006: Financial News Sentiment Dashboard
#
# Architecture:
# 1. S3 bucket for static dashboard assets (React build)
# 2. CloudFront distribution with OAC (Origin Access Control)
# 3. Custom error responses for SPA routing
# 4. Security headers via response headers policy

# ===================================================================
# S3 Bucket for Dashboard Static Assets
# ===================================================================

resource "aws_s3_bucket" "dashboard_assets" {
  bucket = "${var.environment}-sentiment-dashboard-${var.account_suffix}"

  tags = {
    Name        = "${var.environment}-sentiment-dashboard-assets"
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "cdn-origin"
  }
}

resource "aws_s3_bucket_versioning" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ===================================================================
# CloudFront Origin Access Control
# ===================================================================

resource "aws_cloudfront_origin_access_control" "dashboard" {
  name                              = "${var.environment}-sentiment-dashboard-oac"
  description                       = "OAC for sentiment dashboard S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ===================================================================
# S3 Bucket Policy for CloudFront
# ===================================================================

resource "aws_s3_bucket_policy" "dashboard_assets" {
  bucket = aws_s3_bucket.dashboard_assets.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontServicePrincipal"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.dashboard_assets.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.dashboard.arn
          }
        }
      }
    ]
  })
}

# ===================================================================
# CloudFront Response Headers Policy (Security Headers)
# ===================================================================

resource "aws_cloudfront_response_headers_policy" "security" {
  name    = "${var.environment}-sentiment-security-headers"
  comment = "Security headers for sentiment dashboard"

  security_headers_config {
    content_type_options {
      override = true
    }
    frame_options {
      frame_option = "DENY"
      override     = true
    }
    referrer_policy {
      referrer_policy = "strict-origin-when-cross-origin"
      override        = true
    }
    strict_transport_security {
      access_control_max_age_sec = 31536000
      include_subdomains         = true
      preload                    = true
      override                   = true
    }
    xss_protection {
      mode_block = true
      protection = true
      override   = true
    }
    content_security_policy {
      content_security_policy = var.content_security_policy
      override                = true
    }
  }

  custom_headers_config {
    items {
      header   = "Permissions-Policy"
      value    = "geolocation=(), microphone=(), camera=()"
      override = true
    }
  }
}

# ===================================================================
# CloudFront Response Headers Policy (CORS for API)
# ===================================================================
# Enables cross-origin requests from the Interview Dashboard (GitHub Pages)
# to the API Gateway backend. Required because:
# 1. CloudFront forwards requests to API Gateway
# 2. API Gateway REST API doesn't handle OPTIONS preflight natively
# 3. Lambda CORS headers may not reach the browser before CloudFront times out

resource "aws_cloudfront_response_headers_policy" "cors_api" {
  count = length(var.cors_allowed_origins) > 0 ? 1 : 0

  name    = "${var.environment}-sentiment-cors-api"
  comment = "CORS headers for API routes"

  cors_config {
    access_control_allow_credentials = false
    access_control_max_age_sec       = 86400

    access_control_allow_headers {
      items = ["Authorization", "Content-Type", "X-User-ID", "Accept", "Origin"]
    }

    access_control_allow_methods {
      items = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    }

    access_control_allow_origins {
      items = var.cors_allowed_origins
    }

    access_control_expose_headers {
      items = ["X-Request-ID"]
    }

    origin_override = true
  }
}

# ===================================================================
# CloudFront Distribution
# ===================================================================

resource "aws_cloudfront_distribution" "dashboard" {
  enabled             = true
  is_ipv6_enabled     = true
  comment             = "${var.environment} sentiment dashboard"
  default_root_object = "index.html"
  # COST CONTROL (FR-023): Default to PriceClass_100 (US/Canada/Europe only)
  # Override with price_class_override variable if global distribution needed
  price_class  = var.price_class_override != "" ? var.price_class_override : "PriceClass_100"
  http_version = "http2and3"

  # S3 origin for static assets
  origin {
    domain_name              = aws_s3_bucket.dashboard_assets.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.dashboard.id
    origin_id                = "s3-dashboard"
  }

  # API Gateway origin for backend API (optional)
  dynamic "origin" {
    for_each = var.api_gateway_domain != "" ? [1] : []
    content {
      domain_name = var.api_gateway_domain
      origin_id   = "api-gateway"
      origin_path = var.api_gateway_stage_path
      custom_origin_config {
        http_port              = 80
        https_port             = 443
        origin_protocol_policy = "https-only"
        origin_ssl_protocols   = ["TLSv1.2"]
      }
    }
  }

  # Default behavior for static assets
  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-dashboard"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy     = "redirect-to-https"
    min_ttl                    = 0
    default_ttl                = 86400    # 1 day
    max_ttl                    = 31536000 # 1 year
    compress                   = true
    response_headers_policy_id = aws_cloudfront_response_headers_policy.security.id
  }

  # Cache behavior for API routes (if API Gateway origin is configured)
  dynamic "ordered_cache_behavior" {
    for_each = var.api_gateway_domain != "" ? [1] : []
    content {
      path_pattern     = "/api/*"
      allowed_methods  = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
      cached_methods   = ["GET", "HEAD"]
      target_origin_id = "api-gateway"

      forwarded_values {
        query_string = true
        headers      = ["Authorization", "Origin", "Accept", "X-User-ID"]
        cookies {
          forward = "all"
        }
      }

      viewer_protocol_policy = "https-only"
      min_ttl                = 0
      default_ttl            = 0
      max_ttl                = 0
      compress               = true
      # Attach CORS policy for cross-origin API requests
      response_headers_policy_id = length(var.cors_allowed_origins) > 0 ? aws_cloudfront_response_headers_policy.cors_api[0].id : null
    }
  }

  # Cache behavior for static assets with long cache
  ordered_cache_behavior {
    path_pattern     = "/static/*"
    allowed_methods  = ["GET", "HEAD"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "s3-dashboard"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 86400    # 1 day
    default_ttl            = 604800   # 7 days
    max_ttl                = 31536000 # 1 year
    compress               = true
  }

  # SPA routing - return index.html for 404s
  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  # Custom domain (optional)
  aliases = var.custom_domain != "" ? [var.custom_domain] : []

  # SSL certificate
  viewer_certificate {
    cloudfront_default_certificate = var.custom_domain == "" ? true : false
    acm_certificate_arn            = var.custom_domain != "" ? var.acm_certificate_arn : null
    ssl_support_method             = var.custom_domain != "" ? "sni-only" : null
    minimum_protocol_version       = "TLSv1.2_2021"
  }

  # Geo restrictions (none for now)
  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # Logging (optional)
  dynamic "logging_config" {
    for_each = var.enable_logging ? [1] : []
    content {
      include_cookies = false
      bucket          = var.logging_bucket
      prefix          = "cloudfront/${var.environment}/"
    }
  }

  tags = {
    Name        = "${var.environment}-sentiment-dashboard"
    Environment = var.environment
    Feature     = "006-user-config-dashboard"
    Component   = "cdn"
  }
}
