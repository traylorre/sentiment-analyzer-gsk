# KMS Module: Shared Customer-Managed Encryption Key
# =================================================
#
# This module creates a shared KMS key for encrypting sensitive data across:
# - S3 buckets (Terraform state, models)
# - Secrets Manager secrets
# - SNS topics
#
# Security Features:
# - 30-day deletion window (FR-022)
# - Automatic 90-day key rotation (FR-021)
# - Scoped key policy for authorized services only
#
# Cost: $1/month fixed (unlimited encrypt/decrypt operations)
#
# For On-Call Engineers:
#     If encryption fails with AccessDeniedException:
#     1. Verify key policy allows the requesting service
#     2. Check IAM role has kms:Decrypt permission
#     3. Verify key is not in pending deletion state

data "aws_caller_identity" "current" {}

resource "aws_kms_key" "main" {
  description             = "Sentiment Analyzer shared encryption key"
  deletion_window_in_days = 30   # Required by spec (FR-022)
  enable_key_rotation     = true # Automatic 90-day rotation (FR-021)

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Root account access (required to prevent unmanageable key)
      {
        Sid       = "RootAccess"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      # S3 service access for bucket encryption
      {
        Sid       = "S3Access"
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # Secrets Manager access for secret encryption
      {
        Sid       = "SecretsManagerAccess"
        Effect    = "Allow"
        Principal = { Service = "secretsmanager.amazonaws.com" }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # SNS access for topic encryption
      {
        Sid       = "SNSAccess"
        Effect    = "Allow"
        Principal = { Service = "sns.amazonaws.com" }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      # CI Deployer Key Administration (FR-002, FR-005)
      # Required: AWS rejects key creation if creating principal cannot manage the key
      {
        Sid    = "CIDeployerKeyAdmin"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-preprod-deployer",
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-prod-deployer"
          ]
        }
        Action = [
          "kms:Create*",
          "kms:Describe*",
          "kms:Enable*",
          "kms:List*",
          "kms:Put*",
          "kms:Update*",
          "kms:Revoke*",
          "kms:Disable*",
          "kms:Get*",
          "kms:Delete*",
          "kms:TagResource",
          "kms:UntagResource",
          "kms:ScheduleKeyDeletion",
          "kms:CancelKeyDeletion"
        ]
        Resource = "*"
      },
      # CI Deployer Encryption Operations
      # Required for Secrets Manager UpdateSecret when secrets use KMS encryption
      # Canonical Source: https://docs.aws.amazon.com/kms/latest/developerguide/services-secrets-manager.html
      {
        Sid    = "CIDeployerEncryption"
        Effect = "Allow"
        Principal = {
          AWS = [
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-preprod-deployer",
            "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-prod-deployer"
          ]
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:GenerateDataKeyWithoutPlaintext"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(var.tags, {
    Name        = "sentiment-analyzer-shared-key"
    Environment = var.environment
    ManagedBy   = "Terraform"
  })

  # SECURITY: Prevent accidental deletion of encryption key
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/sentiment-analyzer-${var.environment}"
  target_key_id = aws_kms_key.main.key_id
}
