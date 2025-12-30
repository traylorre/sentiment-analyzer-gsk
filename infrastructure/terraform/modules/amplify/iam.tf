# IAM Role for AWS Amplify
# Feature 1105: Next.js Frontend Migration via AWS Amplify SSR

# ===================================================================
# Amplify Service Role
# ===================================================================

resource "aws_iam_role" "amplify_service" {
  name = "${var.environment}-amplify-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "amplify.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Environment = var.environment
    Feature     = "1105-nextjs-migration"
    Component   = "amplify"
  }
}

# ===================================================================
# Amplify Service Policy
# ===================================================================

# Use AWS managed policy for Amplify
resource "aws_iam_role_policy_attachment" "amplify_admin" {
  role       = aws_iam_role.amplify_service.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess-Amplify"
}

# Additional policy for CloudWatch Logs (required for SSR)
resource "aws_iam_role_policy" "amplify_logs" {
  name = "${var.environment}-amplify-logs-policy"
  role = aws_iam_role.amplify_service.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:log-group:/aws/amplify/*"
      }
    ]
  })
}
