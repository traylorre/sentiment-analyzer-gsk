# ECR Module Outputs

output "repository_url" {
  description = "Full URL of the ECR repository (for docker push)"
  value       = aws_ecr_repository.lambda.repository_url
}

output "repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.lambda.arn
}

output "repository_name" {
  description = "Name of the ECR repository"
  value       = aws_ecr_repository.lambda.name
}

output "registry_id" {
  description = "Registry ID (AWS account ID) of the ECR repository"
  value       = aws_ecr_repository.lambda.registry_id
}
