# IAM and Terraform Deployment Troubleshooting

Last Updated: 2025-11-21

## Overview

This document captures lessons learned and troubleshooting procedures for IAM permissions and Terraform deployment issues in the promotion pipeline.

## Table of Contents

- [Common IAM Permission Errors](#common-iam-permission-errors)
- [Terraform State Management](#terraform-state-management)
- [Resource Already Exists Errors](#resource-already-exists-errors)
- [CI User IAM Policy Design](#ci-user-iam-policy-design)
- [Lessons Learned](#lessons-learned)

---

## Common IAM Permission Errors

### Error: "User is not authorized to perform X action"

**Symptoms:**
```
Error: User: arn:aws:iam::ACCOUNT:user/sentiment-analyzer-preprod-ci is not authorized
to perform: SERVICE:ACTION on resource: RESOURCE_ARN because no identity-based policy
allows the SERVICE:ACTION action
```

**Root Cause:**
The CI user's IAM policy is missing required permissions for Terraform to manage infrastructure.

**Resolution:**

1. **Identify the missing permission** from the error message (e.g., `cloudwatch:ListTagsForResource`)

2. **Check current policies** attached to the user:
   ```bash
   # List managed policies
   aws iam list-attached-user-policies --user-name sentiment-analyzer-preprod-ci

   # List inline policies
   aws iam list-user-policies --user-name sentiment-analyzer-preprod-ci

   # Get policy content
   aws iam get-user-policy --user-name sentiment-analyzer-preprod-ci --policy-name POLICY_NAME
   ```

3. **Update the managed policy** to include missing permission:
   ```bash
   # Get current policy version
   aws iam get-policy-version \
     --policy-arn arn:aws:iam::ACCOUNT:policy/PreprodCIDeploymentPolicy \
     --version-id v1

   # Create new version with updated permissions
   aws iam create-policy-version \
     --policy-arn arn:aws:iam::ACCOUNT:policy/PreprodCIDeploymentPolicy \
     --policy-document file://updated-policy.json \
     --set-as-default
   ```

### Inline Policy Size Limit (2048 bytes)

**Error:**
```
Maximum policy size of 2048 bytes exceeded for user sentiment-analyzer-preprod-ci
```

**Resolution:**
Convert inline policy to managed policy:

```bash
# 1. Create managed policy
aws iam create-policy \
  --policy-name PreprodCIDeploymentPolicy \
  --policy-document file://preprod-policy.json \
  --description "Full deployment permissions for preprod CI"

# 2. Attach to user
aws iam attach-user-policy \
  --user-name sentiment-analyzer-preprod-ci \
  --policy-arn arn:aws:iam::ACCOUNT:policy/PreprodCIDeploymentPolicy

# 3. Delete old inline policy
aws iam delete-user-policy \
  --user-name sentiment-analyzer-preprod-ci \
  --policy-name OldPolicyName
```

**Why managed policies are better:**
- No 2048-byte size limit (max 6144 bytes)
- Can be versioned and rolled back
- Can be attached to multiple users/roles
- Easier to audit and manage

### Missing CloudWatch Tag Permissions

**Error:**
```
Error: listing tags for CloudWatch Metric Alarm: User is not authorized to perform:
cloudwatch:ListTagsForResource
```

**Missing Permissions:**
- `cloudwatch:ListTagsForResource`
- `cloudwatch:TagResource`
- `cloudwatch:UntagResource`

**Fix:**
```json
{
  "Sid": "CloudWatchLogsAndMetrics",
  "Effect": "Allow",
  "Action": [
    "logs:*",
    "cloudwatch:PutMetricAlarm",
    "cloudwatch:DeleteAlarms",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:PutMetricData",
    "cloudwatch:ListTagsForResource",
    "cloudwatch:TagResource",
    "cloudwatch:UntagResource"
  ],
  "Resource": [
    "arn:aws:logs:us-east-1:ACCOUNT:log-group:/aws/lambda/preprod-*",
    "arn:aws:logs:us-east-1:ACCOUNT:log-group:/aws/lambda/preprod-*:*",
    "arn:aws:cloudwatch:us-east-1:ACCOUNT:alarm:preprod-*"
  ]
}
```

### Backup Vault Requires KMS Permissions

**Error:**
```
Error: creating Backup Vault: Insufficient privileges to create a backup vault.
Creating a backup vault requires backup-storage and KMS permissions.
```

**Missing Permissions:**
```json
{
  "Sid": "KMSForBackup",
  "Effect": "Allow",
  "Action": [
    "kms:CreateKey",
    "kms:DescribeKey",
    "kms:CreateAlias",
    "kms:DeleteAlias",
    "kms:GetKeyPolicy",
    "kms:PutKeyPolicy",
    "kms:EnableKeyRotation",
    "kms:TagResource",
    "kms:UntagResource"
  ],
  "Resource": "*"
}
```

---

## Terraform State Management

### State Locked by Crashed Workflow

**Symptoms:**
- Terraform plan/apply hangs at "Acquiring state lock"
- Previous workflow was canceled or timed out

**Check Lock Status:**
```bash
aws dynamodb scan \
  --table-name preprod/terraform.tfstate.tflock \
  --projection-expression "LockID, Info"
```

**Resolution:**

1. **Verify no active deployment:**
   ```bash
   gh run list --workflow build-and-promote.yml --status in_progress
   ```

2. **Force unlock (if safe):**
   ```bash
   cd infrastructure/terraform
   terraform init -backend-config=backend-preprod.hcl
   terraform force-unlock <LOCK_ID>
   ```

3. **Or use workflow force-unlock parameter** (safer):
   - Go to Actions → Build and Promote → Run workflow
   - Set `force_unlock=true`
   - Run workflow

**Prevention:**
- Never cancel running deployments
- Let workflows complete or fail naturally
- Workflows automatically clean up stale locks (>1 hour old)

### State Drift: Resource Exists in AWS but Not in State

**Symptoms:**
```
Error: creating X: ResourceAlreadyExistsException
```

**Example:**
```
Error: creating S3 Bucket (preprod-sentiment-lambda-deployments): BucketAlreadyExists
```

**Resolution - Option 1: Import into State**
```bash
# 1. Find the Terraform resource address
cd infrastructure/terraform
terraform state list

# 2. Import the resource
terraform import aws_s3_bucket.lambda_deployments preprod-sentiment-lambda-deployments

# 3. Verify import
terraform plan -var-file=preprod.tfvars
```

**Resolution - Option 2: Remove from Terraform (if manually managed)**
```hcl
# Comment out or remove the resource from main.tf
# resource "aws_s3_bucket" "lambda_deployments" {
#   bucket = "${var.environment}-sentiment-lambda-deployments"
#   ...
# }
```

**Resolution - Option 3: Delete and Recreate**
```bash
# Only if resource can be safely deleted
aws s3 rb s3://preprod-sentiment-lambda-deployments --force
```

---

## Resource Already Exists Errors

### S3 Bucket Already Exists

**Error:**
```
Error: creating S3 Bucket (preprod-sentiment-lambda-deployments): BucketAlreadyExists
```

**Diagnosis:**
```bash
# Check if bucket exists
aws s3 ls | grep preprod-sentiment

# Check bucket ownership
aws s3api get-bucket-location --bucket preprod-sentiment-lambda-deployments

# Check Terraform state
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform state show aws_s3_bucket.lambda_deployments
```

**Resolution:**
See [State Drift](#state-drift-resource-exists-in-aws-but-not-in-state) above.

### IAM Role Already Exists

**Error:**
```
Error: creating IAM Role (preprod-ingestion-lambda-role): EntityAlreadyExists
```

**Import into Terraform:**
```bash
terraform import \
  module.iam.aws_iam_role.ingestion_lambda \
  preprod-ingestion-lambda-role
```

---

## CI User IAM Policy Design

### Current Architecture

**Users:**
- `sentiment-analyzer-preprod-ci` - Deploys to preprod environment
- `sentiment-analyzer-prod-ci` - Deploys to production environment

**Policies:**
- Managed policy: `PreprodCIDeploymentPolicy` (attached to preprod-ci user)
- Managed policy: `ProdCIDeploymentPolicy` (attached to prod-ci user)

### Policy Structure

Each policy grants full access to environment-scoped resources:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "LambdaFullAccess",
      "Effect": "Allow",
      "Action": "lambda:*",
      "Resource": [
        "arn:aws:lambda:REGION:ACCOUNT:function:preprod-*",
        "arn:aws:lambda:REGION:ACCOUNT:layer:preprod-*"
      ]
    },
    {
      "Sid": "IAMRoleManagement",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:GetRole",
        "iam:DeleteRole",
        "iam:PassRole",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PutRolePolicy",
        "iam:GetRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:TagRole",
        "iam:UntagRole",
        "iam:ListRolePolicies",
        "iam:ListAttachedRolePolicies"
      ],
      "Resource": "arn:aws:iam::ACCOUNT:role/preprod-*"
    }
    // ... other service permissions
  ]
}
```

### Key Design Principles

1. **Environment Isolation via Resource Scoping**
   - Preprod user can only manage `preprod-*` resources
   - Prod user can only manage `prod-*` resources
   - No cross-environment access

2. **Service-Based Statements**
   - Each AWS service has its own statement (Sid)
   - Makes auditing and updates easier
   - Clear separation of concerns

3. **Wildcard Actions for Terraform Flexibility**
   - Use `service:*` for services where Terraform needs full control
   - Example: `lambda:*` allows Terraform to manage all Lambda operations
   - Alternative: Explicitly list actions (more secure but requires more maintenance)

4. **Shared Infrastructure Access**
   - Both users can access Terraform state bucket
   - Both users can access their respective state lock tables

### Required Permissions by Service

| Service | Required Actions | Resource Pattern |
|---------|-----------------|------------------|
| Lambda | `lambda:*` | `function:ENV-*`, `layer:ENV-*` |
| S3 | `s3:*` | `ENV-*`, `terraform-state-*` |
| DynamoDB | `dynamodb:*` | `table/ENV-*`, `table/terraform-state-lock-ENV` |
| IAM | CreateRole, GetRole, PassRole, etc. | `role/ENV-*` |
| CloudWatch | PutMetricAlarm, ListTagsForResource, etc. | `alarm:ENV-*` |
| SNS | `sns:*` | `ENV-*` |
| SQS | `sqs:*` | `ENV-*` |
| Secrets Manager | CreateSecret, GetSecretValue, etc. | `secret:ENV/*` |
| Backup | CreateBackupVault, etc. | `backup-vault:ENV-*` |
| KMS | CreateKey, PutKeyPolicy, etc. | `*` (required for Backup) |
| Budgets | CreateBudget, ModifyBudget, etc. | `budget/ENV-*` |
| EventBridge | PutRule, PutTargets, etc. | `rule/ENV-*` |

### Auditing Current Permissions

```bash
# List all permissions for preprod CI user
aws iam get-policy-version \
  --policy-arn arn:aws:iam::ACCOUNT:policy/PreprodCIDeploymentPolicy \
  --version-id v1 \
  | jq '.PolicyVersion.Document'

# Check what policies are attached
aws iam list-attached-user-policies --user-name sentiment-analyzer-preprod-ci

# Check for inline policies (should be none)
aws iam list-user-policies --user-name sentiment-analyzer-preprod-ci
```

---

## Lessons Learned

### 1. Start with Managed Policies, Not Inline

**Problem:**
- Started with inline policies
- Hit 2048-byte size limit immediately
- Had to migrate mid-deployment

**Solution:**
- Always use managed policies for CI users
- Only use inline policies for very small, user-specific overrides

**Reference:** Commit 306ae45

### 2. Terraform Variable Validation Must Match Workflow Reality

**Problem:**
- Terraform validation only allowed `["dev", "prod"]` environments
- Promotion pipeline introduced `preprod` environment
- All deployments failed with validation error

**Solution:**
- Updated validation in `modules/dynamodb/variables.tf` to include `preprod`
- Updated `variables.tf` model_version validation to accept git SHAs

**Code:**
```hcl
variable "environment" {
  validation {
    condition     = contains(["dev", "preprod", "prod"], var.environment)
    error_message = "Environment must be one of: dev, preprod, prod."
  }
}

variable "model_version" {
  validation {
    # Accept semantic versioning OR git SHA
    condition     = can(regex("^v\\d+\\.\\d+\\.\\d+$", var.model_version)) ||
                    can(regex("^[0-9a-f]{7}$", var.model_version))
    error_message = "Model version must be semantic versioning (e.g., v1.0.0) or git SHA (e.g., a1b2c3d)."
  }
}
```

**Reference:** PR #23

### 3. IAM Permissions Evolve - Document As You Go

**Problem:**
- Initial IAM policies were too restrictive
- Each Terraform run revealed new missing permissions
- No central documentation of required permissions

**Solution:**
- Created this document to track all required permissions
- Documented each error encountered and its resolution
- Grouped permissions by service for clarity

**Best Practice:**
- When adding new Terraform resources, proactively grant required IAM permissions
- Test in preprod first to catch permission errors before prod

### 4. Resource Import vs. Manual Cleanup

**Problem:**
- S3 buckets were created manually for testing
- Terraform couldn't create them (already existed)
- Unclear whether to import or delete

**Decision Matrix:**
| Scenario | Action | Reason |
|----------|--------|--------|
| Empty test bucket | Delete and recreate via Terraform | Clean state |
| Bucket with data | Import into Terraform state | Preserve data |
| Resource not in Terraform | Leave as-is, don't manage in TF | Intentionally manual |

**Reference:** Workflow run 19560704595

### 5. Concurrency Controls Are Essential

**Problem:**
- Initial pipeline had no concurrency controls
- Risk of race conditions between Dependabot and manual deploys
- Terraform state corruption risk

**Solution:**
- Added GitHub Actions `concurrency` groups to all deployment workflows
- Each environment has its own group
- Production and production-auto share a group (prevents races)

**Documentation:** See `docs/DEPLOYMENT_CONCURRENCY.md`

**Reference:** PR #22

### 6. Terraform Working Directory Affects Artifact Paths

**Problem:**
- Artifacts downloaded to workspace root
- Terraform runs in `infrastructure/terraform/` subdirectory
- Relative path `../packages/` was incorrect (should be `../../packages/`)

**Solution:**
- Always account for `defaults.run.working-directory` when constructing paths
- Use absolute paths when possible
- Test artifact upload/download locally before CI

**Reference:** PR #21

### 7. Lambda Deployment Bucket is Bootstrap Infrastructure

**Problem:**
- Workflow uploads Lambda packages to S3 before Terraform runs
- Error: `NoSuchBucket: The specified bucket does not exist`
- Chicken-egg problem: Can't upload packages without bucket, can't run Terraform without packages

**Root Cause:**
The promotion pipeline workflow (`.github/workflows/build-and-promote.yml`) has this order:
1. Upload Lambda packages to S3 (line 192-213)
2. Run Terraform (line 215-244)

This design assumes the S3 bucket already exists as **bootstrap infrastructure**.

**Solution:**
Pre-create the Lambda deployment buckets manually (one-time setup):

```bash
# Create buckets
aws s3api create-bucket \
  --bucket preprod-sentiment-lambda-deployments \
  --region us-east-1

aws s3api create-bucket \
  --bucket prod-sentiment-lambda-deployments \
  --region us-east-1

# Enable versioning
aws s3api put-bucket-versioning \
  --bucket preprod-sentiment-lambda-deployments \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-versioning \
  --bucket prod-sentiment-lambda-deployments \
  --versioning-configuration Status=Enabled

# Add tags
aws s3api put-bucket-tagging \
  --bucket preprod-sentiment-lambda-deployments \
  --tagging 'TagSet=[{Key=Environment,Value=preprod},{Key=ManagedBy,Value=terraform},{Key=Project,Value=sentiment-analyzer}]'

aws s3api put-bucket-tagging \
  --bucket prod-sentiment-lambda-deployments \
  --tagging 'TagSet=[{Key=Environment,Value=prod},{Key=ManagedBy,Value=terraform},{Key=Project,Value=sentiment-analyzer}]'
```

**Why This Design?**
- Lambda packages must exist in S3 before Terraform can reference them
- Terraform creates Lambda functions that point to `s3://BUCKET/FUNCTION/lambda.zip`
- Workflow uploads packages first, then Terraform deploys infrastructure
- Similar to Terraform state bucket - it's bootstrap infrastructure

**Alternative Design (Future Improvement):**
Refactor workflow to:
1. Run Terraform with minimal config (just create S3 bucket)
2. Upload Lambda packages
3. Run Terraform again with full config (create Lambda functions)

This would be more complex but eliminate manual bucket creation.

**Reference:** Workflow run 19561400519

### 8. AWS Backup Vault Permissions - "backup-storage" Mystery

**Problem:**
- Error: `Insufficient privileges to create a backup vault. Creating a backup vault requires backup-storage and KMS permissions`
- Persists despite adding extensive KMS permissions (CreateKey, CreateGrant, Encrypt, Decrypt, GenerateDataKey, etc.)
- Added 10+ policy versions trying different permission combinations

**Root Cause (Resolved via Workaround):**
The error message mentions "backup-storage" which may be:
1. A separate AWS service/API namespace we haven't granted
2. A permission on the KMS key itself (resource-based policy)
3. A requirement for the Backup service-linked role to have additional permissions
4. A permission that needs to be granted via `iam:PassRole` to the backup service

**Attempted Solutions:**
- ✅ Added KMS permissions: CreateKey, DescribeKey, CreateAlias, DeleteAlias, GetKeyPolicy, PutKeyPolicy, EnableKeyRotation, TagResource, UntagResource, ListAliases, ListKeys
- ✅ Added KMS grant permissions via ViaService condition: CreateGrant, ListGrants with `kms:ViaService` for backup.amazonaws.com
- ✅ Added backup-storage:* wildcard permission based on AWS managed policies
- ✅ Added service-linked role creation: `iam:CreateServiceLinkedRole` with condition for `backup.amazonaws.com`
- ✅ Added comprehensive Backup permissions: CreateBackupVault, DeleteBackupVault, DescribeBackupVault, PutBackupVaultAccessPolicy, etc.
- ❌ Still failing with same error through policy v10

**Pragmatic Solution (Implemented):**
Made AWS Backup optional for preprod environment via `enable_backup` variable:

```hcl
# modules/dynamodb/variables.tf
variable "enable_backup" {
  description = "Enable AWS Backup for DynamoDB table (disable for environments with IAM limitations)"
  type        = bool
  default     = true
}

# infrastructure/terraform/main.tf
module "dynamodb" {
  source = "./modules/dynamodb"

  environment   = var.environment
  aws_region    = var.aws_region
  enable_backup = var.environment == "preprod" ? false : true
}
```

All backup resources use conditional creation with `count = var.enable_backup ? 1 : 0`.

**Why AWS Backup Matters:**
- **Critical for disaster recovery**: DynamoDB table stores all sentiment analysis results
- **30-day retention**: Configured for daily backups with point-in-time recovery
- **Production requirement**: Essential for data durability and compliance
- **Preprod trade-off**: Backups disabled to unblock deployment (testing environment, acceptable risk)

**Future Work:**
- Re-investigate IAM permissions once preprod is stable
- Re-enable backups for preprod after resolving permission mystery
- Consider using AWS-managed default encryption keys instead of custom KMS keys

**Reference:** Workflow runs 19560934089 through 19566434595, PR #25

### 9. Secrets Manager Recovery Window Issue

**Problem:**
- Secrets created and destroyed multiple times during debugging
- Error: `You can't create this secret because a secret with this name is already scheduled for deletion`
- Secrets Manager enforces minimum 7-day recovery window by default

**Root Cause:**
When Terraform destroys a secret, it's scheduled for deletion but not immediately removed. The secret name is locked for the recovery period.

**Solution:**
Either wait 7 days or force-delete without recovery (loses ability to recover):
```bash
aws secretsmanager delete-secret \
  --secret-id preprod/sentiment-analyzer/newsapi \
  --force-delete-without-recovery
```

**Prevention:**
- Avoid destroying secrets during iterative debugging
- Use `terraform import` to bring existing secrets into state instead of recreating
- Set `recovery_window_in_days = 0` in Terraform for dev/test environments (not recommended for prod)

**Reference:** Workflow run 19563207981

---

## Quick Reference: Common Commands

### Check IAM Permissions
```bash
# Get attached policies
aws iam list-attached-user-policies --user-name sentiment-analyzer-preprod-ci

# Get policy content
aws iam get-policy-version \
  --policy-arn arn:aws:iam::218795110243:policy/PreprodCIDeploymentPolicy \
  --version-id v1
```

### Check Terraform State
```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform state list
terraform state show aws_s3_bucket.lambda_deployments
```

### Check Workflow Status
```bash
# List recent runs
gh run list --workflow build-and-promote.yml --limit 5

# View specific run
gh run view 19560934089 --log-failed

# Watch running workflow
gh run watch 19560934089 --interval 10
```

### Force Unlock Terraform State
```bash
# Check for locks
aws s3api head-object --bucket sentiment-analyzer-terraform-state-218795110243 --key/terraform.tfstate.tflock

# Force unlock
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl
terraform force-unlock <LOCK_ID>
```

---

## On-Call Runbook

### Deployment Fails: "User not authorized"

1. **Identify the missing permission** from error message
2. **Check if it's a known issue** (search this doc)
3. **Update the managed policy** with required permission
4. **Trigger workflow again** - changes take effect immediately
5. **Document the new permission** in this file

### Deployment Fails: "Resource already exists"

1. **Determine if resource should be managed by Terraform**
   - Yes → Import into state
   - No → Remove from Terraform config
2. **If importing:**
   ```bash
   terraform import RESOURCE_ADDRESS RESOURCE_ID
   ```
3. **Verify import:**
   ```bash
   terraform plan -var-file=ENV.tfvars
   ```

### Deployment Stuck: State Lock

1. **Check for active workflows:**
   ```bash
   gh run list --workflow build-and-promote.yml --status in_progress
   ```
2. **If none active, force unlock:**
   ```bash
   terraform force-unlock <LOCK_ID>
   ```
3. **Retry deployment**

---

## Related Documentation

- [Deployment Concurrency](../deployment/DEPLOYMENT_CONCURRENCY.md) - Race condition prevention
- [Failure Recovery Runbook](../operations/FAILURE_RECOVERY_RUNBOOK.md) - General deployment failures
- [GitHub Secrets Setup](../deployment/GITHUB_SECRETS_SETUP.md) - Credential setup
- [GitHub Environments Setup](../deployment/GITHUB_ENVIRONMENTS_SETUP.md) - Environment protection rules
