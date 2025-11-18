# IAM Module Outputs

output "ingestion_lambda_role_arn" {
  description = "ARN of the Ingestion Lambda IAM role"
  value       = aws_iam_role.ingestion_lambda.arn
}

output "ingestion_lambda_role_name" {
  description = "Name of the Ingestion Lambda IAM role"
  value       = aws_iam_role.ingestion_lambda.name
}

output "analysis_lambda_role_arn" {
  description = "ARN of the Analysis Lambda IAM role"
  value       = aws_iam_role.analysis_lambda.arn
}

output "analysis_lambda_role_name" {
  description = "Name of the Analysis Lambda IAM role"
  value       = aws_iam_role.analysis_lambda.name
}

output "dashboard_lambda_role_arn" {
  description = "ARN of the Dashboard Lambda IAM role"
  value       = aws_iam_role.dashboard_lambda.arn
}

output "dashboard_lambda_role_name" {
  description = "Name of the Dashboard Lambda IAM role"
  value       = aws_iam_role.dashboard_lambda.name
}

output "metrics_lambda_role_arn" {
  description = "ARN of the Metrics Lambda IAM role"
  value       = aws_iam_role.metrics_lambda.arn
}

output "metrics_lambda_role_name" {
  description = "Name of the Metrics Lambda IAM role"
  value       = aws_iam_role.metrics_lambda.name
}
