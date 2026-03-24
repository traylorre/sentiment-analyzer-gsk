# CloudFront SSE Module Outputs

output "distribution_url" {
  description = "CloudFront distribution URL (https://xxx.cloudfront.net)"
  value       = "https://${aws_cloudfront_distribution.sse.domain_name}"
}

output "distribution_arn" {
  description = "CloudFront distribution ARN (for WAF association)"
  value       = aws_cloudfront_distribution.sse.arn
}

output "distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.sse.id
}

output "domain_name" {
  description = "CloudFront domain name (xxx.cloudfront.net)"
  value       = aws_cloudfront_distribution.sse.domain_name
}
