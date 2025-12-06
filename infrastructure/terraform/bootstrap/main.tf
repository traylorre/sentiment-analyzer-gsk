# Bootstrap Terraform Backend Resources
# Run this ONCE to create the S3 bucket and DynamoDB table for state management
#
# Usage:
#   cd infrastructure/terraform/bootstrap
#   terraform init
#   terraform apply
#
# After this completes, uncomment the backend config in ../main.tf
# Then run: terraform init -migrate-state

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "aws_region" {
  description = "AWS region for Terraform state resources"
  type        = string
  # No default - region must be explicitly provided
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "sentiment-analyzer"
      Purpose   = "terraform-state"
      ManagedBy = "Terraform"
    }
  }
}

# Get AWS account ID for unique bucket name
data "aws_caller_identity" "current" {}

# S3 bucket for Terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "sentiment-analyzer-terraform-state-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }

  tags = {
    Name = "Terraform State Bucket"
  }
}

# Enable versioning for state history
resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Enable server-side encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access
resource "aws_s3_bucket_public_access_block" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# NOTE: DynamoDB tables for state locking are NO LONGER USED
# Terraform now uses S3 native locking (use_lockfile=true in backend config)
# Lock files are stored as .tflock files directly in S3 bucket
#
# Previous DynamoDB tables (terraform-state-lock-dev, terraform-state-lock-prod)
# can be deleted after confirming S3 native locking works in all environments

output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.id
  description = "Name of the S3 bucket for Terraform state"
}

output "state_locking_info" {
  value       = "S3 native locking enabled. Lock files stored as: <key>.tflock"
  description = "State locking mechanism"
}

output "backend_config_instructions" {
  value       = <<-EOT
    Initialize with environment-specific backend:

    DEV:  terraform init -backend-config=backend-dev.hcl
    PROD: terraform init -backend-config=backend-prod.hcl

    State files: dev/terraform.tfstate, prod/terraform.tfstate
  EOT
  description = "Backend configuration instructions"
}
