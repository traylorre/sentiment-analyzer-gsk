# Quickstart: Pipeline Blockers Resolution

**Feature**: 041-pipeline-blockers
**Date**: 2025-12-06

## Prerequisites

- AWS CLI configured with `sentiment-analyzer-dev` credentials
- Terraform 1.5+ installed
- Access to S3 state bucket `sentiment-analyzer-terraform-state-218795110243`

## Step 1: ECR Repository Import (One-Time Bootstrap)

```bash
# Navigate to terraform directory
cd infrastructure/terraform

# Initialize with preprod backend
terraform init -backend-config=backend-preprod.hcl -backend-config="region=us-east-1" -reconfigure

# Verify identity (should be sentiment-analyzer-dev)
aws sts get-caller-identity

# Import the orphan ECR repository
terraform import aws_ecr_repository.sse_streaming preprod-sse-streaming-lambda

# Verify import - should show no changes to ECR
terraform plan
```

## Step 2: KMS Key Policy Fix (Code Change)

Edit `infrastructure/terraform/modules/kms/main.tf`:

Add after the existing statements in the policy:

```hcl
# CI Deployer Key Administration
{
  Sid       = "CIDeployerKeyAdmin"
  Effect    = "Allow"
  Principal = {
    AWS = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-preprod-deployer",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:user/sentiment-analyzer-prod-deployer"
    ]
  }
  Action = [
    "kms:Create*",
    "kms:Describe*",
    "kms:Enable*",
    "kms:List*",
    "kms:Put*",
    "kms:Update*",
    "kms:Revoke*",
    "kms:Disable*",
    "kms:Get*",
    "kms:Delete*",
    "kms:TagResource",
    "kms:UntagResource",
    "kms:ScheduleKeyDeletion",
    "kms:CancelKeyDeletion"
  ]
  Resource = "*"
}
```

## Step 3: Commit and Push

```bash
git checkout -b 041-pipeline-blockers
git add infrastructure/terraform/modules/kms/main.tf
git commit -S -m "fix(kms): Add CI deployer admin permissions to key policy"
git push -u origin 041-pipeline-blockers
```

## Step 4: Pipeline Verification

1. Create PR targeting `main`
2. Monitor pipeline: `gh run watch`
3. Verify no `RepositoryAlreadyExistsException` errors
4. Verify no `MalformedPolicyDocumentException` errors
5. Confirm "Terraform Apply (Preprod)" job succeeds

## Troubleshooting

### ECR Import Fails

```bash
# Check if repository exists
aws ecr describe-repositories --repository-names preprod-sse-streaming-lambda

# If different name, use correct name in import command
```

### KMS Key Already Exists

```bash
# Check existing key
aws kms describe-key --key-id alias/sentiment-analyzer-preprod

# If in PendingDeletion state
aws kms cancel-key-deletion --key-id <key-id>

# Then import
terraform import module.kms.aws_kms_key.main <key-id>
```

### Permission Denied During Import

Ensure using `sentiment-analyzer-dev` credentials, not `preprod-deployer`.
