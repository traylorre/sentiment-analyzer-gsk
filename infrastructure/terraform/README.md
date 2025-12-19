# Terraform Infrastructure: Sentiment Analyzer

**Architecture**: Regional Multi-AZ (region configured via aws_region variable)
**Feature**: `001-interactive-dashboard-demo`

## Overview

This Terraform configuration deploys the infrastructure for the sentiment analysis demo with production-grade reliability and security:

- ✅ Single DynamoDB table (`sentiment-items`) with 3 GSIs
- ✅ Multi-AZ replication (automatic, AWS-managed)
- ✅ Point-in-time recovery (35-day retention)
- ✅ Daily backups (7-day retention)
- ✅ Secrets Manager for API keys
- ✅ IAM roles with least-privilege permissions
- ✅ CloudWatch alarms for monitoring
- ✅ SNS topic for Lambda triggers
- ✅ EventBridge schedules for periodic execution

## Prerequisites

1. **AWS CLI** configured with credentials
2. **Terraform** >= 1.0 installed
3. **AWS Account** with permissions to create:
   - DynamoDB tables
   - IAM roles/policies
   - Secrets Manager secrets
   - SNS topics
   - EventBridge rules
   - CloudWatch alarms
   - AWS Backup vaults

## Directory Structure

```
infrastructure/terraform/
├── main.tf                    # Main Terraform configuration
├── variables.tf               # Variable definitions
├── .gitignore                 # Terraform-specific gitignore
├── environments/
│   ├── dev.tfvars            # Development environment variables
│   └── prod.tfvars           # Production environment variables
└── modules/
    ├── dynamodb/             # DynamoDB table + backups + alarms
    ├── iam/                  # Lambda IAM roles
    ├── secrets/              # Secrets Manager
    ├── sns/                  # SNS topics
    └── eventbridge/          # EventBridge schedules
```

## Deployment Sequence

**IMPORTANT**: Infrastructure must be deployed in stages because some resources depend on Lambda functions that are deployed separately via CI/CD.

### Stage 1: Core Infrastructure (DynamoDB + Secrets)

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Plan deployment (dev environment)
terraform plan -var-file=dev.tfvars

# Apply deployment
terraform apply -var-file=dev.tfvars
```

**What gets deployed**:
- DynamoDB table: `dev-sentiment-items`
- Secrets Manager:
  - `dev/sentiment-analyzer/tiingo`
  - `dev/sentiment-analyzer/finnhub`
  - `dev/sentiment-analyzer/dashboard-api-key`
- AWS Backup vault and plan
- CloudWatch alarms

**After Stage 1**:
1. Set secret values using AWS CLI (see "Setting Secrets" section below)
2. Deploy Lambda functions via CI/CD pipeline
3. Proceed to Stage 2

---

### Stage 2: Lambda-Dependent Resources (IAM + SNS + EventBridge)

After Lambda functions are deployed, uncomment the following sections in `main.tf`:

1. Lambda data sources (`data "aws_lambda_function"` blocks)
2. SNS module
3. IAM module
4. EventBridge module

Then re-run Terraform:

```bash
terraform plan -var-file=dev.tfvars
terraform apply -var-file=dev.tfvars
```

**What gets deployed**:
- IAM roles for all 4 Lambda functions
- SNS topic with Lambda subscription
- EventBridge schedules (ingestion every 5 min, metrics every 1 min)

---

## Setting Secrets

Secrets are created but NOT populated by Terraform (security best practice). Set them manually:

### Tiingo Secret

```bash
aws secretsmanager put-secret-value \
  --secret-id dev/sentiment-analyzer/tiingo \
  --secret-string '{"api_key":"YOUR_TIINGO_KEY_HERE"}'
```

**Get Tiingo key**: https://www.tiingo.com/account/api/token

### Finnhub Secret

```bash
aws secretsmanager put-secret-value \
  --secret-id dev/sentiment-analyzer/finnhub \
  --secret-string '{"api_key":"YOUR_FINNHUB_KEY_HERE"}'
```

**Get Finnhub key**: https://finnhub.io/dashboard

### Dashboard API Key

```bash
# Generate a random API key
API_KEY=$(openssl rand -hex 32)

aws secretsmanager put-secret-value \
  --secret-id dev/sentiment-analyzer/dashboard-api-key \
  --secret-string "{\"api_key\":\"$API_KEY\"}"

# Save the API key for dashboard access
echo "Dashboard API Key: $API_KEY"
```

---

## Environment Variables

### Development (`dev.tfvars`)

```hcl
environment   = "dev"
aws_region    = "us-east-1"
watch_tags    = "AI,climate,economy,health,sports"
model_version = "v1.0.0"
```

### Production (`prod.tfvars`)

```hcl
environment   = "prod"
aws_region    = "us-east-1"
watch_tags    = "AI,climate,economy,health,sports"
model_version = "v1.0.0"
```

---

## Outputs

After successful deployment, Terraform outputs:

```
dynamodb_table_name           = "dev-sentiment-items"
dynamodb_table_arn            = "arn:aws:dynamodb:us-east-1:..."
tiingo_secret_arn             = "arn:aws:secretsmanager:us-east-1:..."
finnhub_secret_arn            = "arn:aws:secretsmanager:us-east-1:..."
dashboard_api_key_secret_arn  = "arn:aws:secretsmanager:us-east-1:..."
gsi_by_sentiment              = "by_sentiment"
gsi_by_tag                    = "by_tag"
gsi_by_status                 = "by_status"
```

(After Stage 2, additional outputs for SNS, IAM roles, EventBridge schedules)

---

## Monitoring

### CloudWatch Alarms

The following alarms are automatically created:

1. **DynamoDB User Errors** (`dev-dynamodb-user-errors`)
   - Triggers when user errors > 10 in 5 minutes
   - Indicates validation failures in application code

2. **DynamoDB System Errors** (`dev-dynamodb-system-errors`)
   - Triggers when system errors > 5 in 5 minutes
   - Indicates throttling or AWS service issues

3. **DynamoDB Write Throttles** (`dev-dynamodb-write-throttles`)
   - Triggers when write capacity > 1000 WCUs in 1 minute
   - Indicates unexpected traffic spike

### Viewing Alarms

```bash
aws cloudwatch describe-alarms \
  --alarm-name-prefix dev-dynamodb
```

---

## Cost Estimates

### Development Environment

- **DynamoDB**: ~$1.05/month (on-demand, 100 items/hour)
- **Secrets Manager**: $0.80/month (2 secrets)
- **Lambda**: $0.02/month (minimal invocations)
- **CloudWatch**: $0.50/month (logs)
- **AWS Backup**: $0.10/month (small backup size)
- **Total**: ~$2.47/month

### Production Environment

- **DynamoDB**: ~$19/month (on-demand, 10,000 items/hour)
- **Secrets Manager**: $0.80/month
- **Lambda**: $5/month (increased traffic)
- **CloudWatch**: $2/month
- **AWS Backup**: $1/month
- **Total**: ~$28/month

---

## Cleanup

To destroy all resources:

```bash
# Destroy dev environment
terraform destroy -var-file=dev.tfvars

# Destroy prod environment
terraform destroy -var-file=prod.tfvars
```

**WARNING**: This will permanently delete:
- DynamoDB table and all data
- All backups (after 7-day recovery period)
- Secrets (after 7-day recovery period)
- IAM roles
- CloudWatch alarms

---

## Troubleshooting

### Issue: "Lambda function not found"

**Cause**: Trying to deploy Stage 2 before Lambda functions exist

**Solution**: Deploy Lambda functions first, or keep Stage 2 resources commented out

### Issue: "Secret already exists"

**Cause**: Re-running Terraform after secret was manually deleted

**Solution**: Wait 7 days for recovery window, or use AWS CLI to force delete:

```bash
aws secretsmanager delete-secret \
  --secret-id dev/sentiment-analyzer/tiingo \
  --force-delete-without-recovery
```

### Issue: "DynamoDB table already exists"

**Cause**: State file out of sync with actual infrastructure

**Solution**: Import existing table into Terraform state:

```bash
terraform import module.dynamodb.aws_dynamodb_table.sentiment_items dev-sentiment-items
```

---

## Security

### IAM Least-Privilege

Each Lambda has minimal required permissions:
- **Ingestion**: `dynamodb:PutItem` only
- **Analysis**: `dynamodb:UpdateItem`, `dynamodb:GetItem` only
- **Dashboard**: `dynamodb:Query`, `dynamodb:GetItem` (read-only)
- **Metrics**: `dynamodb:Query` on `by_status` GSI only

### Encryption

- **DynamoDB**: Encryption at rest (AWS-managed keys)
- **Secrets Manager**: Encryption at rest (AWS-managed keys)
- **SNS**: Encryption at rest (AWS-managed keys)
- **TLS**: All data in transit uses TLS 1.2+

### Secret Rotation

Secrets Manager supports 90-day rotation (Phase 2):
- Uncomment rotation configuration in `modules/secrets/main.tf`
- Deploy rotation Lambda (separate process)

---

## References

- **Architecture**: See `/specs/001-interactive-dashboard-demo/plan.md`
- **Data Model**: See `/specs/001-interactive-dashboard-demo/data-model.md`
- **Security Review**: See `/specs/001-interactive-dashboard-demo/SECURITY_REVIEW.md`
- **Lambda Contracts**: See `/specs/001-interactive-dashboard-demo/contracts/*.md`

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
