# GitHub Environments and Secrets Configuration

**Last Updated**: 2025-11-20

This document contains the complete configuration for GitHub Environments and their secrets.

---

## Overview

The promotion pipeline uses three GitHub Environments:
1. **preprod** - Pre-production validation (no approval required)
2. **production** - Production deployment (requires @traylorre approval)
3. **production-auto** - Production deployment for Dependabot (no approval required)

---

## Environment 1: Preprod

**Path**: Settings → Environments → preprod

**Configuration**:
- No required reviewers
- No deployment branch restrictions
- Secrets scoped to preprod resources only

**Secrets**:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `PREPROD_AWS_ACCESS_KEY_ID` | *(see preprod-deployer-credentials.json)* | AWS access key for preprod deployer |
| `PREPROD_AWS_SECRET_ACCESS_KEY` | *(see preprod-deployer-credentials.json)* | AWS secret key for preprod deployer |
| `PREPROD_NEWSAPI_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:preprod/sentiment-analyzer/newsapi-w6FooJ` | ARN of preprod NewsAPI key in Secrets Manager |
| `PREPROD_DASHBOARD_API_KEY_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:preprod/sentiment-analyzer/dashboard-api-key-4TA7vl` | ARN of preprod dashboard API key |
| `PREPROD_DASHBOARD_URL` | *(set after first deploy)* | Dashboard Lambda Function URL |
| `PREPROD_DASHBOARD_API_KEY` | `tp4J/KQOM3H5caSlT5PnEvKA5fBiFAObuNizkmugcGI=` | Dashboard API key (for testing) |

---

## Environment 2: Production

**Path**: Settings → Environments → production

**Configuration**:
- **Required reviewer**: @traylorre (human approval for features)
- Deployment branch: main only
- Secrets scoped to prod resources only

**Secrets**:

| Secret Name | Value | Purpose |
|-------------|-------|---------|
| `PROD_AWS_ACCESS_KEY_ID` | *(see prod-deployer-credentials.json)* | AWS access key for prod deployer |
| `PROD_AWS_SECRET_ACCESS_KEY` | *(see prod-deployer-credentials.json)* | AWS secret key for prod deployer |
| `PROD_NEWSAPI_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:prod/sentiment-analyzer/newsapi-qLnqB9` | ARN of prod NewsAPI key |
| `PROD_DASHBOARD_API_KEY_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:prod/sentiment-analyzer/dashboard-api-key-KOfwcw` | ARN of prod dashboard API key |
| `PROD_DASHBOARD_API_KEY` | `6cjAqd89LBISf+BsuZq7j8Z+V0hHcEAfmFDdAt+xqcs=` | Dashboard API key (for testing) |

---

## Environment 3: Production-Auto

**Path**: Settings → Environments → production-auto

**Configuration**:
- **No required reviewers** (allows Dependabot auto-deploy)
- Deployment branch: main only
- Same secrets as production environment

**Secrets**: *(Copy all secrets from production environment)*

| Secret Name | Value |
|-------------|-------|
| `PROD_AWS_ACCESS_KEY_ID` | *(same as production environment)* |
| `PROD_AWS_SECRET_ACCESS_KEY` | *(same as production environment)* |
| `PROD_NEWSAPI_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:prod/sentiment-analyzer/newsapi-qLnqB9` |
| `PROD_DASHBOARD_API_KEY_SECRET_ARN` | `arn:aws:secretsmanager:us-east-1:218795110243:secret:prod/sentiment-analyzer/dashboard-api-key-KOfwcw` |
| `PROD_DASHBOARD_API_KEY` | `6cjAqd89LBISf+BsuZq7j8Z+V0hHcEAfmFDdAt+xqcs=` |

---

## Security Features

### Credential Isolation

IAM policies enforce strict resource scoping:

**Preprod credentials can:**
- ✅ Access `preprod/*` secrets in Secrets Manager
- ✅ Manage `preprod-*` DynamoDB tables
- ✅ Manage `preprod-*` Lambda functions
- ✅ Access `preprod/terraform.tfstate` in S3

**Preprod credentials CANNOT:**
- ❌ Access any `prod/*` resources (explicit DENY)
- ❌ Read or modify production secrets
- ❌ Touch production infrastructure

**Prod credentials can:**
- ✅ Access `prod/*` secrets in Secrets Manager
- ✅ Manage `prod-*` DynamoDB tables
- ✅ Manage `prod-*` Lambda functions
- ✅ Access `prod/terraform.tfstate` in S3

**Prod credentials CANNOT:**
- ❌ Access any `preprod/*` resources (explicit DENY)
- ❌ Read or modify preprod secrets
- ❌ Touch preprod infrastructure

### Validation Results

Credential isolation tested and verified:
- ✅ Preprod can list preprod secrets
- ✅ Preprod CANNOT access prod secrets (AccessDeniedException with explicit deny)
- ✅ Prod can list prod secrets
- ✅ Prod CANNOT access preprod secrets (AccessDeniedException with explicit deny)

---

## AWS Resources Created

### IAM Users

1. **sentiment-analyzer-preprod-deployer**
   - User ARN: `arn:aws:iam::218795110243:user/sentiment-analyzer-preprod-deployer`
   - Policy: PreprodDeploymentPolicy
   - Access Key: *(see preprod-deployer-credentials.json)*

2. **sentiment-analyzer-prod-deployer**
   - User ARN: `arn:aws:iam::218795110243:user/sentiment-analyzer-prod-deployer`
   - Policy: ProdDeploymentPolicy
   - Access Key: *(see prod-deployer-credentials.json)*

### Secrets Manager

**Preprod Secrets**:
- `preprod/sentiment-analyzer/newsapi` - NewsAPI key for preprod (test key)
- `preprod/sentiment-analyzer/dashboard-api-key` - Dashboard auth (random 32-byte key)

**Prod Secrets**:
- `prod/sentiment-analyzer/newsapi` - NewsAPI key for prod (test key - replace before deploy)
- `prod/sentiment-analyzer/dashboard-api-key` - Dashboard auth (random 32-byte key)

### DynamoDB Lock Tables

- `terraform-state-lock-preprod` - Prevents concurrent preprod Terraform runs
- `terraform-state-lock-prod` - Prevents concurrent prod Terraform runs

### S3 State Bucket

- `sentiment-analyzer-terraform-state-218795110243`
  - Versioning: Enabled
  - Encryption: AES256
  - Keys:
    - `preprod/terraform.tfstate` - Preprod infrastructure state
    - `prod/terraform.tfstate` - Prod infrastructure state

---

## Setup Instructions

### Step 1: Create GitHub Environments

1. Go to repository Settings → Environments
2. Create three environments:
   - `preprod` (no reviewers)
   - `production` (required reviewer: @traylorre)
   - `production-auto` (no reviewers)

### Step 2: Add Secrets

For each environment, add the secrets listed in the tables above:

1. Navigate to Settings → Environments → [environment name]
2. Click "Add secret"
3. Copy secret name and value from tables above
4. Repeat for all secrets in that environment

### Step 3: Configure Branch Protection (Recommended)

Settings → Branches → main → Require pull request reviews:
- Required approving reviews: 1
- Require review from Code Owners: Enabled (if CODEOWNERS file exists)

---

## Verification Checklist

Before first deployment:

- [ ] All three GitHub Environments created
- [ ] Preprod environment has 6 secrets configured
- [ ] Production environment has 5 secrets configured
- [ ] Production environment requires @traylorre approval
- [ ] Production-auto environment has 5 secrets (same as production)
- [ ] Production-auto environment has NO required reviewers
- [ ] Branch protection enabled on main branch
- [ ] Terraform bootstrap complete for preprod
- [ ] Terraform bootstrap complete for prod
- [ ] Credential isolation verified

---

## Testing Before First Deploy

### Test Preprod Workflow Trigger

1. Create a test branch with a small change
2. Create PR to main
3. Merge PR (after dev tests pass)
4. Verify `build-and-promote` workflow triggers automatically
5. Verify preprod deployment uses preprod environment (no approval prompt)

### Test Production Conditional Gating

**For human PR**:
1. Merge a feature PR to main
2. Preprod deploy and tests pass
3. `deploy-prod` workflow triggers automatically
4. Workflow waits for @traylorre approval (production environment)
5. Approve deployment
6. Prod deploys

**For Dependabot PR**:
1. Dependabot creates security update PR
2. PR auto-merges (if tests pass)
3. Preprod deploy and tests pass
4. `deploy-prod` workflow triggers automatically
5. Uses `production-auto` environment (NO approval wait)
6. Prod deploys automatically

---

## Troubleshooting

### "Environment not found"

**Symptom**: Workflow fails with "Environment 'preprod' not found"

**Fix**:
1. Go to Settings → Environments
2. Verify environment name matches workflow EXACTLY (case-sensitive)
3. Create environment if missing

### "Secret not found"

**Symptom**: Workflow fails with "Secret PREPROD_AWS_ACCESS_KEY_ID not found"

**Fix**:
1. Go to Settings → Environments → preprod → Secrets
2. Verify secret name matches EXACTLY (case-sensitive)
3. Add secret if missing

### "Access Denied" during Terraform

**Symptom**: Terraform fails with "AccessDeniedException" when accessing resources

**Fix**:
1. Verify IAM policies are applied: `aws iam get-user-policy --user-name sentiment-analyzer-preprod-deployer --policy-name PreprodDeploymentPolicy`
2. Check resource naming matches policy patterns (e.g., `preprod-*`)
3. Verify credentials are for the correct environment

---

## Maintenance

### Rotating Access Keys

**When**: Every 90 days, or if compromised

**How**:
1. Create new access key: `aws iam create-access-key --user-name sentiment-analyzer-preprod-deployer`
2. Update GitHub Environment secrets with new key
3. Test deployment works
4. Delete old access key: `aws iam delete-access-key --user-name sentiment-analyzer-preprod-deployer --access-key-id <OLD_KEY_ID>`

### Rotating Dashboard API Keys

**When**: Annually, or if exposed

**How**:
1. Generate new random key: `openssl rand -base64 32`
2. Update Secrets Manager: `aws secretsmanager update-secret --secret-id preprod/sentiment-analyzer/dashboard-api-key --secret-string '{"api_key":"<NEW_KEY>"}'`
3. Redeploy Lambda: Workflow will pick up new key automatically

---

## Cost Impact

**Monthly Cost**: ~$2.50

- DynamoDB lock tables (on-demand): ~$1.00/month (minimal requests)
- Secrets Manager secrets (4 total): $1.60/month ($0.40 each)
- S3 bucket storage: ~$0.10/month (<1GB)
- IAM users: $0 (included)

**Total**: ~$2.50/month for complete multi-environment infrastructure

---

## References

- IAM Policies: `infrastructure/iam-policies/`
- Setup Script: `infrastructure/scripts/setup-credentials.sh`
- Test Script: `infrastructure/scripts/test-credential-isolation.sh`
- Workflow Design: `docs/PROMOTION_WORKFLOW_DESIGN.md`
- Master Summary: `docs/PROMOTION_PIPELINE_MASTER_SUMMARY.md`
