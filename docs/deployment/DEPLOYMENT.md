# Deployment Guide

Deployment procedures for the Sentiment Analyzer application.

## Table of Contents

- [Prerequisites](#prerequisites)
- [GitHub Actions CI/CD](#github-actions-cicd)
- [Deployment Process](#deployment-process)
- [Zero-Downtime Deployment](#zero-downtime-deployment)
- [Rollback Procedures](#rollback-procedures)
- [Secret Rotation](#secret-rotation)
- [Environment Configuration](#environment-configuration)

---

## Prerequisites

Before deploying, ensure the following:

### 1. AWS Configuration

```bash
# Verify AWS credentials
aws sts get-caller-identity

# Required permissions:
# - Lambda: CreateFunction, UpdateFunctionCode, PublishVersion
# - S3: PutObject, GetObject
# - DynamoDB: CreateTable, UpdateTable
# - SNS: CreateTopic, Subscribe
# - SecretsManager: GetSecretValue
# - CloudWatch: PutMetricAlarm
# - IAM: CreateRole, AttachRolePolicy
```

### 2. Secrets in Secrets Manager

Create the required secrets before first deployment:

```bash
# Tiingo API key
aws secretsmanager create-secret \
  --name "dev/sentiment-analyzer/tiingo" \
  --secret-string '{"api_key": "your-tiingo-api-key"}'

# Finnhub API key (secondary provider)
aws secretsmanager create-secret \
  --name "dev/sentiment-analyzer/finnhub" \
  --secret-string '{"api_key": "your-finnhub-api-key"}'

# Dashboard API key
aws secretsmanager create-secret \
  --name "dev/sentiment-analyzer/dashboard-api-key" \
  --secret-string '{"api_key": "your-dashboard-api-key"}'
```

### 3. Terraform Initialized

```bash
cd infrastructure/terraform
terraform init
terraform workspace new dev  # or prod
```

### 4. Run Pre-Deploy Checklist

```bash
./infrastructure/scripts/pre-deploy-checklist.sh dev
```

---

## GitHub Actions CI/CD

The project uses GitHub Actions for continuous integration and deployment. Three workflows run automatically on push to main:

- **Lint** (`lint.yml`): Black formatting and ruff linting
- **Tests** (`test.yml`): pytest with 80% coverage requirement
- **Deploy Dev** (`deploy-dev.yml`): Automatic deployment to dev environment

### Setting Up GitHub Secrets

For the Deploy Dev workflow to function, you must configure AWS credentials as GitHub repository secrets.

#### Step 1: Create IAM User for CI/CD

```bash
# Create IAM user
aws iam create-user --user-name sentiment-analyzer-github-actions

# Attach deployment policy (create this policy first with required permissions)
aws iam attach-user-policy \
  --user-name sentiment-analyzer-github-actions \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess  # Use least-privilege in production
```

#### Step 2: Create Access Keys

```bash
# Generate access keys
aws iam create-access-key --user-name sentiment-analyzer-github-actions

# Output includes AccessKeyId and SecretAccessKey - save these securely
```

#### Step 3: Add Secrets to GitHub

1. Navigate to your GitHub repository
2. Go to **Settings** > **Secrets and variables** > **Actions**
3. Click **New repository secret**
4. Add the following secrets:

| Secret Name | Value |
|-------------|-------|
| `AWS_ACCESS_KEY_ID` | Access key from Step 2 |
| `AWS_SECRET_ACCESS_KEY` | Secret key from Step 2 |
| `AWS_REGION` | Your AWS region (e.g., `us-east-1`) |

#### Verification

After adding secrets, push a commit to main and verify:

```bash
# Check workflow runs
gh run list --limit 3

# View specific workflow status
gh run view <run-id>
```

The Deploy Dev workflow should now have access to AWS credentials.

### Troubleshooting CI Failures

1. **Lint fails on black**: Install CI version locally: `pip3 install black==23.11.0`
2. **Lint fails on ruff**: Install CI version locally: `pip3 install ruff==0.1.6`
3. **Tests fail**: Ensure `requirements-dev.txt` is installed: `pip3 install -r requirements-dev.txt`
4. **Deploy fails on credentials**: Verify all three secrets are configured correctly

---

## Deployment Process

### Standard Deployment

```bash
# 1. Run pre-deploy checks
./infrastructure/scripts/pre-deploy-checklist.sh dev

# 2. Deploy
./infrastructure/scripts/deploy.sh dev

# 3. Validate deployment
./infrastructure/scripts/demo-validate.sh dev
```

### Manual Deployment Steps

If you need more control, deploy manually:

```bash
# 1. Build Lambda packages
cd /path/to/project
mkdir -p build

# Package each Lambda
for lambda in ingestion analysis dashboard; do
    zip -r "build/${lambda}.zip" "src/lambdas/${lambda}" "src/lambdas/shared" "src/lib"
done

# 2. Upload to S3
aws s3 cp build/ingestion.zip s3://dev-sentiment-lambda-deployments/ingestion/lambda.zip
aws s3 cp build/analysis.zip s3://dev-sentiment-lambda-deployments/analysis/lambda.zip
aws s3 cp build/dashboard.zip s3://dev-sentiment-lambda-deployments/dashboard/lambda.zip

# 3. Apply Terraform
cd infrastructure/terraform
terraform workspace select dev
terraform plan -var="environment=dev" -out=tfplan
terraform apply tfplan
```

---

## Zero-Downtime Deployment

The Sentiment Analyzer uses several strategies for zero-downtime deployment:

### Lambda Versioning

Each deployment creates a new Lambda version:

```bash
# View available versions
aws lambda list-versions-by-function \
  --function-name dev-sentiment-ingestion

# Update to specific version (if using aliases)
aws lambda update-alias \
  --function-name dev-sentiment-ingestion \
  --name live \
  --function-version 5
```

### DynamoDB Schema Evolution

The application handles schema changes gracefully:

1. **New fields**: Default values in code
2. **GSI changes**: Add new GSI, migrate queries, remove old GSI
3. **Field removal**: Stop writing first, then clean up

Example - adding a new field:

```python
# In handler code
model_version = item.get('model_version', 'v1.0.0')  # Default for old items
```

### Deployment Order

For changes affecting multiple components:

1. Deploy DynamoDB changes first (schema is additive)
2. Deploy Lambda functions (handles old and new schema)
3. Update EventBridge schedules last

---

## Rollback Procedures

### Quick Rollback

Use the rollback script:

```bash
# View available versions
./infrastructure/scripts/rollback.sh dev ingestion

# Roll back to specific version
./infrastructure/scripts/rollback.sh dev ingestion 3
```

### Manual Rollback

```bash
# 1. List Lambda versions
aws lambda list-versions-by-function \
  --function-name dev-sentiment-ingestion

# 2. Update function to previous code
aws lambda update-function-code \
  --function-name dev-sentiment-ingestion \
  --s3-bucket dev-sentiment-lambda-deployments \
  --s3-key ingestion/lambda.zip \
  --publish

# 3. Monitor CloudWatch logs
aws logs tail /aws/lambda/dev-sentiment-ingestion --follow
```

### Terraform Rollback

```bash
# View state history (if using S3 backend)
aws s3api list-object-versions \
  --bucket sentiment-analyzer-terraform-state \
  --prefix sentiment-analyzer/terraform.tfstate

# Restore previous state
aws s3api get-object \
  --bucket sentiment-analyzer-terraform-state \
  --key sentiment-analyzer/terraform.tfstate \
  --version-id <previous-version-id> \
  terraform.tfstate.backup

terraform apply
```

---

## Secret Rotation

### Manual Rotation

```bash
# 1. Create new secret version
aws secretsmanager put-secret-value \
  --secret-id "dev/sentiment-analyzer/tiingo" \
  --secret-string '{"api_key": "new-api-key"}'

# 2. Lambda functions will pick up new value on next cold start
# To force immediate update, redeploy the Lambda

# 3. Verify new secret is working
aws lambda invoke \
  --function-name dev-sentiment-ingestion \
  --payload '{"test": true}' \
  response.json
```

### Automated Rotation

For production, configure automatic rotation:

```bash
aws secretsmanager rotate-secret \
  --secret-id "prod/sentiment-analyzer/tiingo" \
  --rotation-lambda-arn arn:aws:lambda:us-east-1:123456789012:function:rotation-lambda
```

---

## Environment Configuration

### Dev Environment

```hcl
# terraform.tfvars
environment         = "dev"
watch_tickers       = "AAPL,TSLA,GOOGL,MSFT,AMZN"
model_version       = "v1.0.0"
alarm_email         = "dev-alerts@example.com"
monthly_budget_limit = 50
```

### Prod Environment

```hcl
# terraform.tfvars
environment         = "prod"
watch_tickers       = "AAPL,TSLA,GOOGL"
model_version       = "v1.0.0"
alarm_email         = "oncall@example.com"
monthly_budget_limit = 100
```

### Environment Variables

| Lambda | Variable | Description |
|--------|----------|-------------|
| All | `ENVIRONMENT` | dev or prod |
| All | `DYNAMODB_TABLE` | Table name |
| Ingestion | `WATCH_TICKERS` | Comma-separated tickers |
| Ingestion | `SNS_TOPIC_ARN` | Analysis topic |
| Ingestion | `TIINGO_SECRET_ARN` | Tiingo API secret ARN |
| Ingestion | `FINNHUB_SECRET_ARN` | Finnhub API secret ARN |
| Analysis | `MODEL_PATH` | /opt/model |
| Analysis | `MODEL_VERSION` | v1.0.0 |
| Dashboard | `DASHBOARD_API_KEY_SECRET_ARN` | Secret ARN |
| Dashboard | `SSE_POLL_INTERVAL` | 5 (seconds) |

---

## Troubleshooting

### Common Issues

1. **Lambda timeout**: Increase timeout in Terraform
2. **DynamoDB throttling**: Check provisioned capacity
3. **Secret not found**: Verify secret name and region
4. **SNS delivery failure**: Check DLQ for failed messages

### Monitoring Commands

```bash
# View Lambda logs
aws logs tail /aws/lambda/dev-sentiment-ingestion --follow

# Check alarms
aws cloudwatch describe-alarms \
  --alarm-name-prefix dev-sentiment \
  --state-value ALARM

# Check DynamoDB metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name ConsumedReadCapacityUnits \
  --dimensions Name=TableName,Value=dev-sentiment-items \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%SZ) \
  --period 300 \
  --statistics Sum
```

---

## References

- [TROUBLESHOOTING.md](../operations/TROUBLESHOOTING.md) - Development environment issues
- [FAILURE_RECOVERY_RUNBOOK.md](../operations/FAILURE_RECOVERY_RUNBOOK.md) - Incident response procedures

---

*Last updated: 2025-11-18*
