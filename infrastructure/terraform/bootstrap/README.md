# Terraform Backend Bootstrap

This directory contains Terraform configuration to create the S3 bucket and DynamoDB table required for remote state management.

## One-Time Setup

Run these commands **once** to set up the backend infrastructure:

```bash
cd infrastructure/terraform/bootstrap

# Initialize and apply
terraform init
terraform apply
```

After successful creation, the main Terraform configuration will use S3 backend automatically.

## Import Existing State

If you have existing resources in AWS that were created before enabling the S3 backend, you need to import them:

```bash
cd infrastructure/terraform

# Re-initialize with new backend (will prompt for state migration)
terraform init -migrate-state

# Import existing secrets (if they exist)
terraform import module.secrets.aws_secretsmanager_secret.tiingo dev/sentiment-analyzer/tiingo
terraform import module.secrets.aws_secretsmanager_secret.finnhub dev/sentiment-analyzer/finnhub
terraform import module.secrets.aws_secretsmanager_secret.dashboard_api_key dev/sentiment-analyzer/dashboard-api-key

# Verify state
terraform plan
```

## Resources Created

- **S3 Bucket**: `sentiment-analyzer-terraform-state`
  - Versioning enabled for state history
  - Server-side encryption (AES256)
  - Public access blocked

- **DynamoDB Table**: `terraform-state-lock`
  - Used for state locking to prevent concurrent modifications
  - Pay-per-request billing
