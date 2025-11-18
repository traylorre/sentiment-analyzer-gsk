output "topic_arn" {
  description = "ARN of the SNS topic"
  value       = aws_sns_topic.analysis_requests.arn
}

output "topic_name" {
  description = "Name of the SNS topic"
  value       = aws_sns_topic.analysis_requests.name
}

output "dlq_arn" {
  description = "ARN of the dead letter queue"
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_url" {
  description = "URL of the dead letter queue"
  value       = aws_sqs_queue.dlq.url
}
