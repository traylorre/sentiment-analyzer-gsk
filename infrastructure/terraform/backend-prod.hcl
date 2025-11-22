# Backend configuration for PROD environment
# Usage: terraform init -backend-config=backend-prod.hcl

bucket         = "sentiment-analyzer-terraform-state-218795110243"
key            = "prod/terraform.tfstate"
# region is passed via -backend-config="region=${AWS_REGION}" in CI/CD
encrypt        = true
dynamodb_table = "terraform-state-lock-prod"
