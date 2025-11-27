output "distribution_id" {
  description = "ID of the CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.id
}

output "distribution_arn" {
  description = "ARN of the CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.arn
}

output "distribution_domain_name" {
  description = "Domain name of the CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.domain_name
}

output "distribution_hosted_zone_id" {
  description = "Route 53 hosted zone ID for CloudFront distribution"
  value       = aws_cloudfront_distribution.dashboard.hosted_zone_id
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for dashboard assets"
  value       = aws_s3_bucket.dashboard_assets.id
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for dashboard assets"
  value       = aws_s3_bucket.dashboard_assets.arn
}

output "dashboard_url" {
  description = "URL for accessing the dashboard"
  value       = "https://${aws_cloudfront_distribution.dashboard.domain_name}"
}
