# API Gateway Module Outputs

output "api_id" {
  description = "ID of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.dashboard.id
}

output "api_arn" {
  description = "ARN of the API Gateway REST API"
  value       = aws_api_gateway_rest_api.dashboard.arn
}

output "api_endpoint" {
  description = "Invoke URL for the API Gateway stage"
  value       = aws_api_gateway_stage.dashboard.invoke_url
}

output "stage_name" {
  description = "Name of the API Gateway stage"
  value       = aws_api_gateway_stage.dashboard.stage_name
}

output "usage_plan_id" {
  description = "ID of the API Gateway usage plan"
  value       = aws_api_gateway_usage_plan.dashboard.id
}

output "execution_arn" {
  description = "Execution ARN of the API Gateway (for Lambda permissions)"
  value       = aws_api_gateway_rest_api.dashboard.execution_arn
}
