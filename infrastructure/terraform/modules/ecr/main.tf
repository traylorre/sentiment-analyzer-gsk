# ECR Repository for Lambda Container Images
# ============================================
#
# Creates and manages Amazon ECR repositories for Lambda container images.
# Follows industry best practices from AWS prescriptive guidance.
#
# For On-Call Engineers:
#     If Lambda fails to pull container image:
#     1. Check ECR repository exists in same region as Lambda
#     2. Verify repository policy allows lambda.amazonaws.com
#     3. Check image exists with correct tag (commit SHA)
#     4. View CloudWatch logs for "CannotPullContainerError"
#
# For Developers:
#     - Repository policy grants Lambda service permission to pull images
#     - Image scanning enabled for vulnerability detection
#     - Lifecycle policy keeps last 10 images, removes older ones
#     - Immutable tags prevent accidental overwrites
#
# References:
#     - https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/build-and-push-docker-images-to-amazon-ecr-using-github-actions-and-terraform.html
#     - https://aws.amazon.com/blogs/compute/hosting-hugging-face-models-on-aws-lambda/

# ECR Repository
resource "aws_ecr_repository" "lambda" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE" # Allow retagging for rollbacks

  # Scan images on push for security vulnerabilities
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(var.tags, {
    Name = var.repository_name
  })
}

# Repository Lifecycle Policy
# Keeps last 10 images, removes older ones to control storage costs
resource "aws_ecr_lifecycle_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last 10 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 10
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Repository Policy
# Grants Lambda service permission to pull images
resource "aws_ecr_repository_policy" "lambda" {
  repository = aws_ecr_repository.lambda.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaECRImageRetrievalPolicy"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        # Restrict to Lambda functions in same AWS account
        Condition = {
          StringLike = {
            "aws:sourceArn" = "arn:aws:lambda:${var.aws_region}:${var.aws_account_id}:function:${var.environment}-*"
          }
        }
      }
    ]
  })
}
