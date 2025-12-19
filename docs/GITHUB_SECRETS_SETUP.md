# GitHub Environment Secrets Setup Guide

Complete guide for setting up GitHub environment secrets for the sentiment-analyzer-gsk deployment pipeline.

**Last Updated**: 2025-11-24

---

## Overview

This guide walks through creating all required GitHub environment secrets for the three deployment environments: **dev**, **preprod**, and **production**.

**Total Secrets**: 12 (4 per environment × 3 environments)

**Consistent IAM Naming Pattern**: All environments use `sentiment-analyzer-{env}-deployer` IAM users.

---

## Prerequisites: Create dev-deployer IAM User and Policy

### Step 1: Create the IAM User

First, create the missing `sentiment-analyzer-dev-deployer` user for naming consistency:

```bash
# Create dev-deployer user
aws iam create-user --user-name sentiment-analyzer-dev-deployer
```

### Step 2: Create and Attach the IAM Policy

Create a scoped policy that restricts the dev-deployer to only dev-* resources:

```bash
# Create the IAM policy from the policy document
aws iam create-policy \
  --policy-name SentimentAnalyzerDevDeployerPolicy \
  --policy-document file://docs/iam-policies/dev-deployer-policy.json \
  --description "Dev environment deployer policy - restricts access to dev-* resources only"

# Attach the policy to the dev-deployer user
aws iam attach-user-policy \
  --user-name sentiment-analyzer-dev-deployer \
  --policy-arn arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/SentimentAnalyzerDevDeployerPolicy
```

**Verify the policy is attached:**
```bash
aws iam list-attached-user-policies --user-name sentiment-analyzer-dev-deployer
```

**Expected output:**
```json
{
    "AttachedPolicies": [
        {
            "PolicyName": "SentimentAnalyzerDevDeployerPolicy",
            "PolicyArn": "arn:aws:iam::123456789012:policy/SentimentAnalyzerDevDeployerPolicy"
        }
    ]
}
```

**Policy Features:**
- ✅ Full access to dev-* prefixed resources (Lambda, DynamoDB, S3, SNS, SQS, Secrets Manager, etc.)
- ✅ Terraform state access for dev workspace
- ✅ Terraform lock table access (terraform-state-lock-dev)
- ✅ Global read permissions for AWS discovery
- ❌ **Explicit DENY** for preprod-* resources
- ❌ **Explicit DENY** for prod-* resources

This ensures dev-deployer can never accidentally touch preprod or prod resources.

---

## Create Access Keys for All Deployer Users

Check if access keys exist and create them if needed:

```bash
# Check dev-deployer
aws iam list-access-keys --user-name sentiment-analyzer-dev-deployer

# Check preprod-deployer
aws iam list-access-keys --user-name sentiment-analyzer-preprod-deployer

# Check prod-deployer
aws iam list-access-keys --user-name sentiment-analyzer-prod-deployer
```

Create access keys for any user missing them:

```bash
# Create access key for dev-deployer
aws iam create-access-key --user-name sentiment-analyzer-dev-deployer

# Create access key for preprod-deployer (if needed)
aws iam create-access-key --user-name sentiment-analyzer-preprod-deployer

# Create access key for prod-deployer (if needed)
aws iam create-access-key --user-name sentiment-analyzer-prod-deployer
```

**IMPORTANT**: Save the `AccessKeyId` and `SecretAccessKey` from each create-access-key output. You'll need them below.

---

## DEV Environment (4 secrets)

**IAM User**: `sentiment-analyzer-dev-deployer`

### DEV Secret 1 of 4: AWS_ACCESS_KEY_ID
```bash
# Replace PASTE_DEV_DEPLOYER_ACCESS_KEY with the AccessKeyId from sentiment-analyzer-dev-deployer
echo -n "PASTE_DEV_DEPLOYER_ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --env dev
```

### DEV Secret 2 of 4: AWS_SECRET_ACCESS_KEY
```bash
# Replace PASTE_DEV_DEPLOYER_SECRET_KEY with the SecretAccessKey from sentiment-analyzer-dev-deployer
echo -n "PASTE_DEV_DEPLOYER_SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --env dev
```

### DEV Secret 3 of 4: DASHBOARD_API_KEY (auto-generated)
```bash
# This generates a random 64-character hex string
openssl rand -hex 32 | gh secret set DASHBOARD_API_KEY --env dev
```

### DEV Secret 4 of 4: TIINGO_SECRET_ARN (auto-filled from AWS)
```bash
# This fetches the ARN from AWS Secrets Manager
aws secretsmanager describe-secret --secret-id dev/sentiment-analyzer/tiingo --query ARN --output text | gh secret set TIINGO_SECRET_ARN --env dev
```

---

## PREPROD Environment (4 secrets)

**IAM User**: `sentiment-analyzer-preprod-deployer`

### PREPROD Secret 1 of 4: AWS_ACCESS_KEY_ID
```bash
# Replace PASTE_PREPROD_DEPLOYER_ACCESS_KEY with the AccessKeyId from sentiment-analyzer-preprod-deployer
echo -n "PASTE_PREPROD_DEPLOYER_ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --env preprod
```

### PREPROD Secret 2 of 4: AWS_SECRET_ACCESS_KEY
```bash
# Replace PASTE_PREPROD_DEPLOYER_SECRET_KEY with the SecretAccessKey from sentiment-analyzer-preprod-deployer
echo -n "PASTE_PREPROD_DEPLOYER_SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --env preprod
```

### PREPROD Secret 3 of 4: DASHBOARD_API_KEY (auto-filled from AWS)
```bash
# This fetches the existing dashboard API key from AWS Secrets Manager
aws secretsmanager get-secret-value --secret-id preprod/sentiment-analyzer/dashboard-api-key --query SecretString --output text | gh secret set DASHBOARD_API_KEY --env preprod
```

### PREPROD Secret 4 of 4: TIINGO_SECRET_ARN (auto-filled from AWS)
```bash
# This fetches the ARN from AWS Secrets Manager
aws secretsmanager describe-secret --secret-id preprod/sentiment-analyzer/tiingo --query ARN --output text | gh secret set TIINGO_SECRET_ARN --env preprod
```

---

## PRODUCTION Environment (4 secrets)

**IAM User**: `sentiment-analyzer-prod-deployer`

### PRODUCTION Secret 1 of 4: AWS_ACCESS_KEY_ID
```bash
# Replace PASTE_PROD_DEPLOYER_ACCESS_KEY with the AccessKeyId from sentiment-analyzer-prod-deployer
echo -n "PASTE_PROD_DEPLOYER_ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --env production
```

### PRODUCTION Secret 2 of 4: AWS_SECRET_ACCESS_KEY
```bash
# Replace PASTE_PROD_DEPLOYER_SECRET_KEY with the SecretAccessKey from sentiment-analyzer-prod-deployer
echo -n "PASTE_PROD_DEPLOYER_SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --env production
```

### PRODUCTION Secret 3 of 4: DASHBOARD_API_KEY (auto-generated)
```bash
# This generates a random 64-character hex string
openssl rand -hex 32 | gh secret set DASHBOARD_API_KEY --env production
```

### PRODUCTION Secret 4 of 4: TIINGO_SECRET_ARN (auto-filled from AWS)
```bash
# This fetches the ARN from AWS Secrets Manager
aws secretsmanager describe-secret --secret-id prod/sentiment-analyzer/tiingo --query ARN --output text | gh secret set TIINGO_SECRET_ARN --env production
```

---

## Verification

After running all commands, verify all secrets are set:

```bash
# Check dev secrets
gh secret list --env dev

# Check preprod secrets
gh secret list --env preprod

# Check production secrets
gh secret list --env production
```

**Expected Output**: Each environment should show 4 secrets:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `DASHBOARD_API_KEY`
- `TIINGO_SECRET_ARN`

---

## Summary

### IAM User Naming Pattern (Consistent Across All Environments)

| Environment | IAM User | Status |
|-------------|----------|--------|
| **DEV** | `sentiment-analyzer-dev-deployer` | Created via this guide |
| **PREPROD** | `sentiment-analyzer-preprod-deployer` | Already exists |
| **PROD** | `sentiment-analyzer-prod-deployer` | Already exists |

### Secret Breakdown

**Manual steps (copy-paste access keys)**: 6 secrets
- DEV: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- PREPROD: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
- PROD: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

**Automatic (run command as-is)**: 6 secrets
- DEV: DASHBOARD_API_KEY (generated), TIINGO_SECRET_ARN (from AWS)
- PREPROD: DASHBOARD_API_KEY (from AWS), TIINGO_SECRET_ARN (from AWS)
- PROD: DASHBOARD_API_KEY (generated), TIINGO_SECRET_ARN (from AWS)

---

## Benefits of Consistent Naming

**For on-call operations:**
- ✅ Predictable naming: `sentiment-analyzer-{ENV}-deployer`
- ✅ Easy to find during key rotation
- ✅ No confusion about which user is for which environment
- ✅ Consistent pattern for troubleshooting
- ✅ Eliminates "is the key deleted or just named something idiotic?" confusion

---

## Key Rotation

When rotating access keys for a deployer user:

```bash
# Example: Rotate dev-deployer key
# 1. Create new access key
NEW_KEY=$(aws iam create-access-key --user-name sentiment-analyzer-dev-deployer)

# 2. Extract values
ACCESS_KEY=$(echo $NEW_KEY | jq -r '.AccessKey.AccessKeyId')
SECRET_KEY=$(echo $NEW_KEY | jq -r '.AccessKey.SecretAccessKey')

# 3. Update GitHub secret
echo -n "$ACCESS_KEY" | gh secret set AWS_ACCESS_KEY_ID --env dev
echo -n "$SECRET_KEY" | gh secret set AWS_SECRET_ACCESS_KEY --env dev

# 4. Test deployment works

# 5. Delete old access key
aws iam delete-access-key --user-name sentiment-analyzer-dev-deployer --access-key-id OLD_ACCESS_KEY_ID
```

---

## Troubleshooting

### Issue: Secret command fails with "not found"

**Symptom**: `aws secretsmanager describe-secret` returns `ResourceNotFoundException`

**Solution**: Verify the secret exists in AWS Secrets Manager:
```bash
aws secretsmanager list-secrets --query 'SecretList[?contains(Name, `sentiment-analyzer`)].Name'
```

### Issue: gh CLI not authenticated

**Symptom**: `gh secret set` fails with authentication error

**Solution**: Authenticate with GitHub CLI:
```bash
gh auth login
```

### Issue: Missing IAM permissions

**Symptom**: `aws iam create-access-key` fails with `AccessDenied`

**Solution**: Ensure your AWS credentials have IAM user management permissions:
```bash
aws sts get-caller-identity  # Verify who you're authenticated as
```

---

## Related Documentation

- [GitHub Actions Workflow Documentation](.github/WORKFLOW_DOCUMENTATION.md)
- [Deployment Guide](DEPLOYMENT.md)
- [IAM CI User Policy](IAM_CI_USER_POLICY.md)
