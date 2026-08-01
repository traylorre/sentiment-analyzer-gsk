# Bootstrap Terraform Backend Resources
# Run this ONCE to create the S3 bucket that holds Terraform state.
#
# Usage:
#   cd infrastructure/terraform/bootstrap
#   terraform init
#   terraform apply -var aws_region=<region>
#
# The backend block in ../main.tf is already active. Initialize the main
# configuration with the environment's partial config:
#   terraform init -backend-config=backend-preprod.hcl

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

output "state_bucket_name" {
  value       = aws_s3_bucket.terraform_state.id
  description = "Name of the S3 bucket for Terraform state"
}
