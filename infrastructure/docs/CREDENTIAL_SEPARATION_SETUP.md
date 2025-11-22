# Credential Separation Setup Guide

**Purpose**: Configure isolated credentials for preprod and prod environments to prevent cross-environment access and security breaches.

**Security Principle**: Preprod credentials cannot modify prod resources, and vice versa.

---

## Overview

```
┌────────────────────────────────────────────────────────┐
│ GitHub Environments (scoped secrets)                   │
├────────────────────────────────────────────────────────┤
│ Environment: preprod                                   │
│   PREPROD_AWS_ACCESS_KEY_ID      → preprod-deployer  │
│   PREPROD_AWS_SECRET_ACCESS_KEY  → Limited to preprod │
│   PREPROD_NEWSAPI_SECRET_ARN     → preprod secrets    │
├────────────────────────────────────────────────────────┤
│ Environment: production                                │
│   PROD_AWS_ACCESS_KEY_ID         → prod-deployer     │
│   PROD_AWS_SECRET_ACCESS_KEY     → Limited to prod    │
│   PROD_NEWSAPI_SECRET_ARN        → prod secrets       │
└────────────────────────────────────────────────────────┘
```

---

## Step 1: Create IAM Users

### Preprod Deployer IAM User

```bash
# Create IAM user for preprod deployments
aws iam create-user \
  --user-name sentiment-analyzer-preprod-deployer \
  --tags Key=Environment,Value=preprod \
         Key=Purpose,Value=terraform-deployment \
         Key=ManagedBy,Value=Manual

# Create access key
aws iam create-access-key \
  --user-name sentiment-analyzer-preprod-deployer \
  > preprod-deployer-credentials.json

# IMPORTANT: Save these credentials securely
# You'll add them to GitHub Environments in Step 3
```

### Prod Deployer IAM User

```bash
# Create IAM user for prod deployments
aws iam create-user \
  --user-name sentiment-analyzer-prod-deployer \
  --tags Key=Environment,Value=prod \
         Key=Purpose,Value=terraform-deployment \
         Key=ManagedBy,Value=Manual

# Create access key
aws iam create-access-key \
  --user-name sentiment-analyzer-prod-deployer \
  > prod-deployer-credentials.json

# IMPORTANT: Save these credentials securely
```

---

## Step 2: Apply IAM Policies

### Preprod Deployer Policy

Create file: `preprod-deployer-policy.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PreprodResourcesOnly",
      "Effect": "Allow",
      "Action": [
        "dynamodb:*",
        "lambda:*",
        "s3:*",
        "sns:*",
        "sqs:*",
        "secretsmanager:*",
        "events:*",
        "iam:*",
        "logs:*",
        "cloudwatch:*"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/preprod-*",
        "arn:aws:lambda:*:*:function:preprod-*",
        "arn:aws:s3:::*-preprod-*",
        "arn:aws:s3:::*-preprod-*/*",
        "arn:aws:sns:*:*:preprod-*",
        "arn:aws:sqs:*:*:preprod-*",
        "arn:aws:secretsmanager:*:*:secret:preprod/*",
        "arn:aws:events:*:*:rule/preprod-*",
        "arn:aws:iam::*:role/preprod-*",
        "arn:aws:iam::*:policy/preprod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/preprod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/preprod-*:*",
        "arn:aws:cloudwatch:*:*:alarm:preprod-*"
      ]
    },
    {
      "Sid": "TerraformStateAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sentiment-analyzer-tfstate-*",
        "arn:aws:s3:::sentiment-analyzer-tfstate-*/preprod/*"
      ]
    },
    {
      "Sid": "TerraformLockAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/preprod/terraform.tfstate.tflock"
    },
    {
      "Sid": "DenyProdResources",
      "Effect": "Deny",
      "Action": "*",
      "Resource": [
        "arn:aws:dynamodb:*:*:table/prod-*",
        "arn:aws:lambda:*:*:function:prod-*",
        "arn:aws:s3:::*-prod-*",
        "arn:aws:s3:::*-prod-*/*",
        "arn:aws:secretsmanager:*:*:secret:prod/*",
        "arn:aws:iam::*:role/prod-*"
      ]
    }
  ]
}
```

Apply the policy:

```bash
# Create the policy
aws iam put-user-policy \
  --user-name sentiment-analyzer-preprod-deployer \
  --policy-name PreprodDeploymentPolicy \
  --policy-document file://preprod-deployer-policy.json
```

### Prod Deployer Policy

Create file: `prod-deployer-policy.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ProdResourcesOnly",
      "Effect": "Allow",
      "Action": [
        "dynamodb:*",
        "lambda:*",
        "s3:*",
        "sns:*",
        "sqs:*",
        "secretsmanager:*",
        "events:*",
        "iam:*",
        "logs:*",
        "cloudwatch:*"
      ],
      "Resource": [
        "arn:aws:dynamodb:*:*:table/prod-*",
        "arn:aws:lambda:*:*:function:prod-*",
        "arn:aws:s3:::*-prod-*",
        "arn:aws:s3:::*-prod-*/*",
        "arn:aws:sns:*:*:prod-*",
        "arn:aws:sqs:*:*:prod-*",
        "arn:aws:secretsmanager:*:*:secret:prod/*",
        "arn:aws:events:*:*:rule/prod-*",
        "arn:aws:iam::*:role/prod-*",
        "arn:aws:iam::*:policy/prod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/prod-*",
        "arn:aws:logs:*:*:log-group:/aws/lambda/prod-*:*",
        "arn:aws:cloudwatch:*:*:alarm:prod-*"
      ]
    },
    {
      "Sid": "TerraformStateAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::sentiment-analyzer-tfstate-*",
        "arn:aws:s3:::sentiment-analyzer-tfstate-*/prod/*"
      ]
    },
    {
      "Sid": "TerraformLockAccess",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/prod/terraform.tfstate.tflock"
    },
    {
      "Sid": "DenyPreprodResources",
      "Effect": "Deny",
      "Action": "*",
      "Resource": [
        "arn:aws:dynamodb:*:*:table/preprod-*",
        "arn:aws:lambda:*:*:function:preprod-*",
        "arn:aws:s3:::*-preprod-*",
        "arn:aws:s3:::*-preprod-*/*",
        "arn:aws:secretsmanager:*:*:secret:preprod/*",
        "arn:aws:iam::*:role/preprod-*"
      ]
    }
  ]
}
```

Apply the policy:

```bash
# Create the policy
aws iam put-user-policy \
  --user-name sentiment-analyzer-prod-deployer \
  --policy-name ProdDeploymentPolicy \
  --policy-document file://prod-deployer-policy.json
```

---

## Step 3: Create AWS Secrets Manager Secrets

### Preprod NewsAPI Secret

```bash
# Create preprod NewsAPI secret
aws secretsmanager create-secret \
  --name preprod/sentiment-analyzer/newsapi \
  --description "NewsAPI key for preprod environment (free tier)" \
  --secret-string '{"api_key":"YOUR_PREPROD_NEWSAPI_KEY"}' \
  --region us-east-1 \
  --tags Key=Environment,Value=preprod \
         Key=ManagedBy,Value=Manual \
         Key=Purpose,Value=newsapi-integration

# Get the ARN for GitHub secrets
aws secretsmanager describe-secret \
  --secret-id preprod/sentiment-analyzer/newsapi \
  --query ARN \
  --output text
```

### Prod NewsAPI Secret

```bash
# Create prod NewsAPI secret
aws secretsmanager create-secret \
  --name prod/sentiment-analyzer/newsapi \
  --description "NewsAPI key for production environment (paid tier)" \
  --secret-string '{"api_key":"YOUR_PROD_NEWSAPI_KEY"}' \
  --region us-east-1 \
  --tags Key=Environment,Value=prod \
         Key=ManagedBy,Value=Manual \
         Key=Purpose,Value=newsapi-integration

# Get the ARN for GitHub secrets
aws secretsmanager describe-secret \
  --secret-id prod/sentiment-analyzer/newsapi \
  --query ARN \
  --output text
```

### Preprod Dashboard API Key Secret

```bash
# Generate a secure API key
PREPROD_API_KEY=$(openssl rand -base64 32)

# Create preprod dashboard API key secret
aws secretsmanager create-secret \
  --name preprod/sentiment-analyzer/dashboard-api-key \
  --description "Dashboard API key for preprod environment" \
  --secret-string "{\"api_key\":\"${PREPROD_API_KEY}\"}" \
  --region us-east-1 \
  --tags Key=Environment,Value=preprod \
         Key=ManagedBy,Value=Manual \
         Key=Purpose,Value=dashboard-auth

# Get the ARN
aws secretsmanager describe-secret \
  --secret-id preprod/sentiment-analyzer/dashboard-api-key \
  --query ARN \
  --output text
```

### Prod Dashboard API Key Secret

```bash
# Generate a secure API key
PROD_API_KEY=$(openssl rand -base64 32)

# Create prod dashboard API key secret
aws secretsmanager create-secret \
  --name prod/sentiment-analyzer/dashboard-api-key \
  --description "Dashboard API key for production environment" \
  --secret-string "{\"api_key\":\"${PROD_API_KEY}\"}" \
  --region us-east-1 \
  --tags Key=Environment,Value=prod \
         Key=ManagedBy,Value=Manual \
         Key=Purpose,Value=dashboard-auth

# Get the ARN
aws secretsmanager describe-secret \
  --secret-id prod/sentiment-analyzer/dashboard-api-key \
  --query ARN \
  --output text
```

---

## Step 4: Configure GitHub Environments

### Create GitHub Environments

1. Go to: `https://github.com/traylorre/sentiment-analyzer-gsk/settings/environments`

2. Create environment: **preprod**
   - No required reviewers (automatic deployment)
   - No wait timer
   - Branch restriction: `main` only

3. Create environment: **production**
   - Required reviewers: `@traylorre` (or your GitHub username)
   - No wait timer
   - Branch restriction: `main` only

4. Create environment: **production-auto** (for Dependabot)
   - No required reviewers (Dependabot bypass)
   - No wait timer
   - Branch restriction: `main` only

### Add Secrets to GitHub Environments

#### Preprod Environment Secrets

Navigate to: `Settings → Environments → preprod → Add Secret`

Add the following secrets:

```
PREPROD_AWS_ACCESS_KEY_ID
  → From preprod-deployer-credentials.json: AccessKeyId

PREPROD_AWS_SECRET_ACCESS_KEY
  → From preprod-deployer-credentials.json: SecretAccessKey

PREPROD_NEWSAPI_SECRET_ARN
  → arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:preprod/sentiment-analyzer/newsapi-XXXXXX

PREPROD_DASHBOARD_API_KEY_SECRET_ARN
  → arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:preprod/sentiment-analyzer/dashboard-api-key-XXXXXX

PREPROD_DASHBOARD_API_KEY
  → The generated PREPROD_API_KEY from Step 3
```

#### Production Environment Secrets

Navigate to: `Settings → Environments → production → Add Secret`

Add the following secrets:

```
PROD_AWS_ACCESS_KEY_ID
  → From prod-deployer-credentials.json: AccessKeyId

PROD_AWS_SECRET_ACCESS_KEY
  → From prod-deployer-credentials.json: SecretAccessKey

PROD_NEWSAPI_SECRET_ARN
  → arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod/sentiment-analyzer/newsapi-XXXXXX

PROD_DASHBOARD_API_KEY_SECRET_ARN
  → arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:prod/sentiment-analyzer/dashboard-api-key-XXXXXX

PROD_DASHBOARD_API_KEY
  → The generated PROD_API_KEY from Step 3
```

#### Production-Auto Environment Secrets

Navigate to: `Settings → Environments → production-auto → Add Secret`

**IMPORTANT**: Add the SAME secrets as `production` environment.

This allows Dependabot to use the same prod credentials but bypass the manual approval gate.

---

## Step 5: Validation

### Test Preprod Credentials

```bash
# Configure AWS CLI with preprod credentials
export AWS_ACCESS_KEY_ID="<PREPROD_ACCESS_KEY>"
export AWS_SECRET_ACCESS_KEY="<PREPROD_SECRET_KEY>"
export AWS_DEFAULT_REGION="us-east-1"

# Test: Should succeed (preprod resource)
aws dynamodb describe-table --table-name preprod-sentiment-items 2>&1

# Test: Should fail (prod resource - DENY policy)
aws dynamodb describe-table --table-name prod-sentiment-items 2>&1
# Expected error: "An error occurred (AccessDeniedException)"

# Test: Can read preprod secrets
aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/newsapi

# Test: Cannot read prod secrets (DENY policy)
aws secretsmanager get-secret-value \
  --secret-id prod/sentiment-analyzer/newsapi
# Expected error: "An error occurred (AccessDeniedException)"
```

### Test Prod Credentials

```bash
# Configure AWS CLI with prod credentials
export AWS_ACCESS_KEY_ID="<PROD_ACCESS_KEY>"
export AWS_SECRET_ACCESS_KEY="<PROD_SECRET_KEY>"
export AWS_DEFAULT_REGION="us-east-1"

# Test: Should succeed (prod resource)
aws dynamodb describe-table --table-name prod-sentiment-items 2>&1

# Test: Should fail (preprod resource - DENY policy)
aws dynamodb describe-table --table-name preprod-sentiment-items 2>&1
# Expected error: "An error occurred (AccessDeniedException)"

# Test: Can read prod secrets
aws secretsmanager get-secret-value \
  --secret-id prod/sentiment-analyzer/newsapi

# Test: Cannot read preprod secrets (DENY policy)
aws secretsmanager get-secret-value \
  --secret-id preprod/sentiment-analyzer/newsapi
# Expected error: "An error occurred (AccessDeniedException)"
```

---

## Step 6: Update Workflows to Use Environment Secrets

Workflows will now reference secrets from GitHub Environments:

```yaml
# .github/workflows/deploy-preprod.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    environment: preprod  # ← Uses preprod environment secrets

    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.PREPROD_AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.PREPROD_AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
```

```yaml
# .github/workflows/deploy-prod.yml
jobs:
  deploy:
    runs-on: ubuntu-latest
    # Conditional environment based on PR author
    environment: ${{ github.actor == 'dependabot[bot]' && 'production-auto' || 'production' }}

    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.PROD_AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.PROD_AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
```

---

## Security Benefits

✅ **Defense in Depth**: Compromised preprod credentials cannot modify prod resources

✅ **Blast Radius Containment**: Security incident in preprod doesn't affect prod

✅ **Audit Trail**: Separate IAM users allow CloudTrail to distinguish preprod vs prod actions

✅ **Credential Rotation**: Can rotate preprod keys without affecting prod

✅ **Cost Control**: Preprod IAM policy prevents accidental expensive prod operations

✅ **Compliance**: Meets security requirement for environment isolation

---

## Cost

**IAM Users**: $0 (no charge)

**Secrets Manager**: $0 (no additional charge - same secret count)
- Before: 2 secrets (newsapi, dashboard-api-key) shared across envs
- After: 4 secrets (2 per environment)
- Cost: $0.40/month per secret = $1.60/month total

**Total Additional Cost**: ~$1.60/month

---

## Maintenance

### Rotate Preprod NewsAPI Key

```bash
# Update the secret value
aws secretsmanager update-secret \
  --secret-id preprod/sentiment-analyzer/newsapi \
  --secret-string '{"api_key":"NEW_PREPROD_KEY"}' \
  --region us-east-1

# Trigger Terraform re-run to update Lambda environment variables (if needed)
```

### Rotate IAM Access Keys (Annual)

```bash
# Create new access key for preprod deployer
aws iam create-access-key \
  --user-name sentiment-analyzer-preprod-deployer

# Update GitHub Environment secrets
# Go to: Settings → Environments → preprod → Update secrets

# Delete old access key
aws iam delete-access-key \
  --user-name sentiment-analyzer-preprod-deployer \
  --access-key-id <OLD_KEY_ID>
```

---

## Troubleshooting

### Error: "Access Denied" when deploying preprod

**Cause**: Preprod credentials trying to access prod resources

**Fix**: Verify IAM policies have explicit DENY for prod resources

```bash
aws iam get-user-policy \
  --user-name sentiment-analyzer-preprod-deployer \
  --policy-name PreprodDeploymentPolicy
```

### Error: "Secret not found"

**Cause**: Workflow using wrong secret ARN

**Fix**: Verify GitHub Environment secrets match AWS Secrets Manager ARNs

```bash
# List all secrets
aws secretsmanager list-secrets \
  --query 'SecretList[?starts_with(Name, `preprod/`)].[Name, ARN]' \
  --output table
```

---

## References

- [AWS IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [GitHub Environments Documentation](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
- [AWS Secrets Manager Pricing](https://aws.amazon.com/secrets-manager/pricing/)
