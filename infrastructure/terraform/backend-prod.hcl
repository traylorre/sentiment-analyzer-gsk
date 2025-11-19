# Backend configuration for PROD environment
# Usage: terraform init -backend-config=backend-prod.hcl

bucket         = "sentiment-analyzer-tfstate-218795110243"
key            = "prod/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock-prod"
