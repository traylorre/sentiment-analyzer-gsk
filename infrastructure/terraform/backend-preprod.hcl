# Preprod Backend Configuration
# =============================
#
# Preprod environment is a production mirror for final validation before prod deploy.
#
# Purpose:
# - Run integration tests against REAL AWS resources
# - Validate Terraform changes before production
# - Identical infrastructure to prod (smaller scale)
#
# State Management:
# - S3 bucket: sentiment-analyzer-terraform-state (shared with dev/prod)
# - State key: preprod/terraform.tfstate (separate from dev and prod)
# - DynamoDB lock: terraform-state-lock-preprod (prevents concurrent applies)
#
# When to Use:
# - Manual validation before production deploy
# - Weekly automated integration test runs
# - Troubleshooting production issues in safe environment

bucket         = "sentiment-analyzer-terraform-state-218795110243"
key            = "preprod/terraform.tfstate"
# region is passed via -backend-config="region=${AWS_REGION}" in CI/CD
encrypt        = true
dynamodb_table = "terraform-state-lock-preprod"
