# Terraform Backend Bootstrap

This directory contains Terraform configuration to create the S3 bucket required for remote state management with S3 native locking.

## One-Time Setup

Run these commands **once** to set up the backend infrastructure:

```bash
cd infrastructure/terraform/bootstrap

# Initialize and apply
terraform init
terraform apply

# Note the bucket name from output
terraform output state_bucket_name
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

# Verify state
terraform plan
```

## Resources Created

- **S3 Bucket**: `sentiment-analyzer-tfstate-{ACCOUNT_ID}`
  - Versioning enabled for state history
  - Server-side encryption (AES256)
  - Public access blocked
  - **S3 Native Locking**: Uses `.tflock` files for state locking (no DynamoDB required)
