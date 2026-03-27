# WAF v2 Module Outputs

output "web_acl_arn" {
  description = "ARN of the WAF v2 WebACL"
  value       = aws_wafv2_web_acl.main.arn
}

output "web_acl_id" {
  description = "ID of the WAF v2 WebACL"
  value       = aws_wafv2_web_acl.main.id
}

output "web_acl_name" {
  description = "Name of the WAF v2 WebACL"
  value       = aws_wafv2_web_acl.main.name
}
