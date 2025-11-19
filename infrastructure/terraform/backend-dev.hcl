# Backend configuration for DEV environment
# Usage: terraform init -backend-config=backend-dev.hcl

bucket         = "sentiment-analyzer-tfstate-218795110243"
key            = "dev/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
dynamodb_table = "terraform-state-lock-dev"
