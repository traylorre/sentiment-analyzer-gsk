# AWS Amplify Module Outputs
# Feature 1105: Next.js Frontend Migration via AWS Amplify SSR

output "app_id" {
  description = "Amplify App ID"
  value       = aws_amplify_app.frontend.id
}

output "app_arn" {
  description = "Amplify App ARN"
  value       = aws_amplify_app.frontend.arn
}

output "default_domain" {
  description = "Default domain for Amplify app (*.amplifyapp.com)"
  value       = aws_amplify_app.frontend.default_domain
}

output "branch_name" {
  description = "Deployed branch name"
  value       = aws_amplify_branch.main.branch_name
}

output "production_url" {
  description = "Production URL for the deployed frontend"
  value       = "https://${aws_amplify_branch.main.branch_name}.${aws_amplify_app.frontend.default_domain}"
}

output "console_url" {
  description = "AWS Console URL for Amplify app management"
  value       = "https://${data.aws_region.current.name}.console.aws.amazon.com/amplify/home?region=${data.aws_region.current.name}#/${aws_amplify_app.frontend.id}"
}

output "service_role_arn" {
  description = "ARN of the Amplify service role"
  value       = aws_iam_role.amplify_service.arn
}

# Data source for current region
data "aws_region" "current" {}
