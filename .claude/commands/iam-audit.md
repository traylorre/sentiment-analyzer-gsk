---
description: Comprehensive IAM permissions audit for CI/CD pipeline. Identifies missing permissions, verifies policy attachment, and provides executable fixes.
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty). The user may provide:
- A specific error message or failed pipeline URL to investigate
- A specific AWS service to focus on
- Instructions to apply fixes automatically

## Goal

Perform a comprehensive IAM permissions audit that not only IDENTIFIES missing permissions but also VERIFIES policies are actually attached to the correct IAM users and PROVIDES executable fixes.

## Operating Constraints

**READ-THEN-FIX**: This command reads infrastructure files and optionally applies fixes. If fixes are needed:
1. Present findings first
2. Ask user for approval before making changes
3. Provide manual AWS CLI commands as alternative

**Scope**: Focus on CI/CD deployer users that run Terraform in GitHub Actions pipelines.

## Execution Steps

### 1. Identify Pipeline Context

Search for and analyze:
- `.github/workflows/deploy.yml` or similar deploy workflows
- Environment variables for AWS credentials (find IAM user references)
- Terraform backend configuration (state bucket access)

Extract:
- **IAM User Names**: The actual usernames used in each environment (dev, preprod, prod)
- **AWS Region**: Default region for resources
- **Environments**: List of deployment environments

### 2. Identify All IAM Users

Cross-reference these sources to find ALL deployer users:

**From Workflows:**
```bash
grep -r "AWS_ACCESS_KEY" .github/workflows/
grep -r "deployer\|ci-user\|ci_user" .github/workflows/
```

**From Terraform:**
```bash
grep -r "user-name\|user_name\|iam_user" infrastructure/terraform/
```

**From Policy Files:**
```bash
find . -name "*policy*" -o -name "*iam*" | xargs grep -l "user"
```

Create a table of all IAM users:
| Environment | IAM User Name | Source File | Policy Attachment Method |
|-------------|---------------|-------------|--------------------------|

Flag any naming inconsistencies (e.g., `dev-deployer` vs `preprod-ci`).

### 3. Catalog All Terraform Resources

Scan all `.tf` files in `infrastructure/terraform/` and subdirectories:

```bash
grep -rh "^resource\s" infrastructure/terraform/ | sort | uniq
```

Group resources by AWS service:
- **Lambda**: `aws_lambda_function`, `aws_lambda_alias`, `aws_lambda_layer_version`, `aws_lambda_event_source_mapping`, `aws_lambda_function_url`, `aws_lambda_permission`
- **DynamoDB**: `aws_dynamodb_table`
- **S3**: `aws_s3_bucket`, `aws_s3_bucket_*`, `aws_s3_object`
- **SNS**: `aws_sns_topic`, `aws_sns_topic_subscription`
- **SQS**: `aws_sqs_queue`
- **CloudWatch**: `aws_cloudwatch_log_group`, `aws_cloudwatch_metric_alarm`, `aws_cloudwatch_dashboard`
- **Cognito**: `aws_cognito_user_pool`, `aws_cognito_user_pool_client`, `aws_cognito_user_pool_domain`, `aws_cognito_identity_pool`, `aws_cognito_identity_provider`
- **CloudFront**: `aws_cloudfront_distribution`, `aws_cloudfront_origin_access_control`, `aws_cloudfront_cache_policy`
- **EventBridge**: `aws_cloudwatch_event_rule`, `aws_cloudwatch_event_target`
- **Secrets Manager**: `aws_secretsmanager_secret`, `aws_secretsmanager_secret_version`
- **IAM**: `aws_iam_role`, `aws_iam_policy`, `aws_iam_role_policy_attachment`, `aws_iam_user_policy_attachment`, `aws_iam_user_policy`
- **ACM**: `aws_acm_certificate`
- **RUM**: `aws_rum_app_monitor`
- **Budgets**: `aws_budgets_budget`
- **Backup**: `aws_backup_vault`, `aws_backup_plan`, `aws_backup_selection`
- **FIS**: `aws_fis_experiment_template`

### 4. Map Resources to Required IAM Actions

For each resource type found, document the required IAM actions:

#### Lambda
```
lambda:CreateFunction, lambda:UpdateFunctionCode, lambda:UpdateFunctionConfiguration,
lambda:DeleteFunction, lambda:GetFunction, lambda:GetFunctionConfiguration,
lambda:ListFunctions, lambda:ListVersionsByFunction, lambda:PublishVersion,
lambda:CreateAlias, lambda:UpdateAlias, lambda:DeleteAlias, lambda:GetAlias,
lambda:AddPermission, lambda:RemovePermission, lambda:GetPolicy,
lambda:CreateFunctionUrlConfig, lambda:UpdateFunctionUrlConfig,
lambda:DeleteFunctionUrlConfig, lambda:GetFunctionUrlConfig,
lambda:CreateEventSourceMapping, lambda:UpdateEventSourceMapping,
lambda:DeleteEventSourceMapping, lambda:GetEventSourceMapping,
lambda:PublishLayerVersion, lambda:DeleteLayerVersion, lambda:GetLayerVersion,
lambda:TagResource, lambda:UntagResource, lambda:ListTags
```

#### DynamoDB
```
dynamodb:CreateTable, dynamodb:UpdateTable, dynamodb:DeleteTable,
dynamodb:DescribeTable, dynamodb:ListTables,
dynamodb:DescribeTimeToLive, dynamodb:UpdateTimeToLive,
dynamodb:DescribeContinuousBackups, dynamodb:UpdateContinuousBackups,
dynamodb:TagResource, dynamodb:UntagResource, dynamodb:ListTagsOfResource
```

#### S3
```
s3:CreateBucket, s3:DeleteBucket, s3:GetBucketLocation,
s3:GetBucketVersioning, s3:PutBucketVersioning,
s3:GetBucketPublicAccessBlock, s3:PutBucketPublicAccessBlock,
s3:GetBucketTagging, s3:PutBucketTagging,
s3:GetBucketPolicy, s3:PutBucketPolicy, s3:DeleteBucketPolicy,
s3:GetEncryptionConfiguration, s3:PutEncryptionConfiguration,
s3:GetBucketCORS, s3:PutBucketCORS, s3:DeleteBucketCORS,
s3:GetBucketWebsite, s3:PutBucketWebsite, s3:DeleteBucketWebsite,
s3:GetLifecycleConfiguration, s3:PutLifecycleConfiguration,
s3:GetBucketAcl, s3:PutBucketAcl,
s3:PutObject, s3:GetObject, s3:DeleteObject, s3:ListBucket,
s3:GetObjectAcl, s3:PutObjectAcl
```

#### Cognito User Pools
```
cognito-idp:CreateUserPool, cognito-idp:UpdateUserPool, cognito-idp:DeleteUserPool,
cognito-idp:DescribeUserPool, cognito-idp:ListUserPools,
cognito-idp:GetUserPoolMfaConfig, cognito-idp:SetUserPoolMfaConfig,
cognito-idp:CreateUserPoolClient, cognito-idp:UpdateUserPoolClient,
cognito-idp:DeleteUserPoolClient, cognito-idp:DescribeUserPoolClient,
cognito-idp:CreateUserPoolDomain, cognito-idp:UpdateUserPoolDomain,
cognito-idp:DeleteUserPoolDomain, cognito-idp:DescribeUserPoolDomain,
cognito-idp:CreateResourceServer, cognito-idp:UpdateResourceServer,
cognito-idp:DeleteResourceServer, cognito-idp:DescribeResourceServer,
cognito-idp:CreateIdentityProvider, cognito-idp:UpdateIdentityProvider,
cognito-idp:DeleteIdentityProvider, cognito-idp:DescribeIdentityProvider,
cognito-idp:TagResource, cognito-idp:UntagResource, cognito-idp:ListTagsForResource
```

#### Cognito Identity Pools
```
cognito-identity:CreateIdentityPool, cognito-identity:UpdateIdentityPool,
cognito-identity:DeleteIdentityPool, cognito-identity:DescribeIdentityPool,
cognito-identity:ListIdentityPools,
cognito-identity:GetIdentityPoolRoles, cognito-identity:SetIdentityPoolRoles,
cognito-identity:TagResource, cognito-identity:UntagResource
```

#### CloudWatch
```
cloudwatch:PutMetricAlarm, cloudwatch:DeleteAlarms, cloudwatch:DescribeAlarms,
cloudwatch:PutDashboard, cloudwatch:DeleteDashboards, cloudwatch:GetDashboard,
cloudwatch:ListDashboards, cloudwatch:ListMetrics, cloudwatch:GetMetricStatistics,
cloudwatch:TagResource, cloudwatch:UntagResource
logs:CreateLogGroup, logs:DeleteLogGroup, logs:DescribeLogGroups,
logs:PutRetentionPolicy, logs:DeleteRetentionPolicy,
logs:PutMetricFilter, logs:DeleteMetricFilter, logs:DescribeMetricFilters,
logs:TagLogGroup, logs:UntagLogGroup
```

#### CloudFront
```
cloudfront:CreateDistribution, cloudfront:UpdateDistribution, cloudfront:DeleteDistribution,
cloudfront:GetDistribution, cloudfront:GetDistributionConfig, cloudfront:ListDistributions,
cloudfront:CreateOriginAccessControl, cloudfront:UpdateOriginAccessControl,
cloudfront:DeleteOriginAccessControl, cloudfront:GetOriginAccessControl,
cloudfront:CreateCachePolicy, cloudfront:UpdateCachePolicy, cloudfront:DeleteCachePolicy,
cloudfront:GetCachePolicy, cloudfront:ListCachePolicies,
cloudfront:TagResource, cloudfront:UntagResource
```

#### SNS
```
sns:CreateTopic, sns:DeleteTopic, sns:GetTopicAttributes, sns:SetTopicAttributes,
sns:Subscribe, sns:Unsubscribe, sns:ListSubscriptionsByTopic,
sns:TagResource, sns:UntagResource
```

#### SQS
```
sqs:CreateQueue, sqs:DeleteQueue, sqs:GetQueueAttributes, sqs:SetQueueAttributes,
sqs:GetQueueUrl, sqs:ListQueues, sqs:TagQueue, sqs:UntagQueue
```

#### EventBridge
```
events:PutRule, events:DeleteRule, events:DescribeRule,
events:EnableRule, events:DisableRule,
events:PutTargets, events:RemoveTargets, events:ListTargetsByRule,
events:TagResource, events:UntagResource
```

#### Secrets Manager
```
secretsmanager:CreateSecret, secretsmanager:DeleteSecret, secretsmanager:DescribeSecret,
secretsmanager:UpdateSecret, secretsmanager:PutSecretValue,
secretsmanager:TagResource, secretsmanager:UntagResource
```

#### IAM (scoped to service roles and CI deployer users)
```
# Role management
iam:CreateRole, iam:DeleteRole, iam:GetRole, iam:UpdateRole,
iam:AttachRolePolicy, iam:DetachRolePolicy,
iam:PutRolePolicy, iam:DeleteRolePolicy, iam:GetRolePolicy,
iam:ListRolePolicies, iam:ListAttachedRolePolicies,
iam:TagRole, iam:UntagRole

# Policy management
iam:CreatePolicy, iam:DeletePolicy, iam:GetPolicy, iam:GetPolicyVersion,
iam:ListPolicyVersions, iam:CreatePolicyVersion, iam:DeletePolicyVersion,
iam:PassRole (with conditions for specific services)

# User policy attachments (for aws_iam_user_policy_attachment resources)
iam:ListAttachedUserPolicies, iam:AttachUserPolicy, iam:DetachUserPolicy

# Inline user policies (for aws_iam_user_policy resources)
iam:ListUserPolicies, iam:GetUserPolicy, iam:PutUserPolicy, iam:DeleteUserPolicy
```

**IMPORTANT**: If your Terraform manages `aws_iam_user_policy_attachment` resources (attaching managed policies to users), the CI user needs `iam:ListAttachedUserPolicies` on the target user resources, otherwise `terraform plan` will fail with AccessDenied.

#### RUM
```
rum:CreateAppMonitor, rum:UpdateAppMonitor, rum:DeleteAppMonitor,
rum:GetAppMonitor, rum:ListAppMonitors,
rum:TagResource, rum:UntagResource
```

#### Budgets
```
budgets:CreateBudget, budgets:ModifyBudget, budgets:DeleteBudget,
budgets:ViewBudget, budgets:DescribeBudgets
```

#### Backup
```
backup:CreateBackupVault, backup:DeleteBackupVault, backup:DescribeBackupVault,
backup:CreateBackupPlan, backup:UpdateBackupPlan, backup:DeleteBackupPlan,
backup:GetBackupPlan, backup:CreateBackupSelection, backup:DeleteBackupSelection,
backup:GetBackupSelection, backup:TagResource, backup:UntagResource
```

#### FIS
```
fis:CreateExperimentTemplate, fis:GetExperimentTemplate, fis:UpdateExperimentTemplate,
fis:DeleteExperimentTemplate, fis:ListExperimentTemplates,
fis:StartExperiment, fis:StopExperiment, fis:GetExperiment,
fis:TagResource, fis:UntagResource
```

#### General
```
sts:GetCallerIdentity
ec2:DescribeAvailabilityZones, ec2:DescribeVpcs, ec2:DescribeSubnets, ec2:DescribeSecurityGroups
```

### 5. Analyze Current Policy

Read the current CI policy file (typically `infrastructure/terraform/ci-user-policy.tf` or similar):

1. Extract all `actions` from each `statement`
2. Compare against required actions from Step 4
3. Create a gap analysis table:

| Service | Required Action | In Policy? | Statement SID |
|---------|-----------------|------------|---------------|

### 6. Verify Policy Attachment Mechanism

**CRITICAL CHECK**: A policy document is useless if not attached.

Check for:
1. `aws_iam_user_policy` resources that attach inline policies
2. `aws_iam_user_policy_attachment` resources that attach managed policies
3. Manual attachment instructions in comments or documentation
4. GitHub Actions steps that apply policies

If the policy is a `data` source only (like `data "aws_iam_policy_document"`), flag this as **CRITICAL** - the policy exists but is never applied.

### 6a. Check for Self-Referential IAM Resources

**COMMON ISSUE**: When Terraform manages `aws_iam_user_policy_attachment` resources for CI deployer users, those users need permission to read their own attached policies.

Run this check:
```bash
# Find aws_iam_user_policy_attachment resources
grep -rn "aws_iam_user_policy_attachment" infrastructure/terraform/

# Check if the CI user has permission to list user policies
grep -A20 "iam:ListAttachedUserPolicies" infrastructure/terraform/
```

**If `aws_iam_user_policy_attachment` exists but `iam:ListAttachedUserPolicies` is NOT in the policy:**
This is a **CRITICAL** gap. Terraform will fail with:
```
AccessDenied: User is not authorized to perform: iam:ListAttachedUserPolicies
```

**Required permissions for managing user policy attachments:**
```hcl
statement {
  sid    = "IAMUserPolicyAttachments"
  effect = "Allow"
  actions = [
    "iam:ListAttachedUserPolicies",
    "iam:AttachUserPolicy",
    "iam:DetachUserPolicy"
  ]
  resources = [
    "arn:aws:iam::*:user/<your-ci-user-pattern>*"
  ]
}
```

### 7. Generate Findings Report

Output a structured report:

```markdown
## IAM Permissions Audit Report

### IAM Users Inventory
| Environment | User Name | Policy Attached? | Attachment Method |
|-------------|-----------|------------------|-------------------|

### Missing Permissions
| Priority | Service | Missing Action | Required By Resource |
|----------|---------|----------------|---------------------|

### Policy Attachment Status
- [ ] Policy document exists: YES/NO
- [ ] Policy attached via Terraform: YES/NO
- [ ] Policy attached manually: UNKNOWN (requires AWS API check)
- [ ] User names match across all files: YES/NO

### Critical Issues
1. [CRITICAL] Policy not attached - document exists but never applied
2. [CRITICAL] User name mismatch - `dev-deployer` vs `preprod-ci`
...

### Coverage Summary
- Total Terraform resource types: X
- Required IAM actions: Y
- Actions in current policy: Z
- Missing actions: Y - Z
- Coverage: Z/Y (%)
```

### 8. Provide Executable Fixes

Based on findings, provide ONE of these fix options:

#### Option A: Terraform Auto-Attachment (Recommended)

Add `aws_iam_user_policy` resources to automatically attach the policy:

```hcl
resource "aws_iam_user_policy" "ci_deploy_dev" {
  name   = "TerraformDeployPolicy"
  user   = "sentiment-analyzer-dev-deployer"
  policy = data.aws_iam_policy_document.ci_deploy.json
}
```

#### Option B: AWS CLI Commands (Manual)

Provide exact commands for each user:

```bash
# For dev environment
aws iam put-user-policy \
  --user-name sentiment-analyzer-dev-deployer \
  --policy-name TerraformDeployPolicy \
  --policy-document file://ci-policy.json

# Verify attachment
aws iam get-user-policy \
  --user-name sentiment-analyzer-dev-deployer \
  --policy-name TerraformDeployPolicy
```

#### Option C: GitHub Actions Step

Add a step to the deploy workflow to ensure policy is current:

```yaml
- name: Update CI Policy
  run: |
    terraform output -raw ci_deploy_policy_json > /tmp/policy.json
    aws iam put-user-policy \
      --user-name ${{ secrets.AWS_IAM_USER }} \
      --policy-name TerraformDeployPolicy \
      --policy-document file:///tmp/policy.json
```

### 9. Validate Fix

After applying the fix, provide verification commands:

```bash
# List attached policies
aws iam list-user-policies --user-name <USER_NAME>

# Get policy content
aws iam get-user-policy --user-name <USER_NAME> --policy-name TerraformDeployPolicy

# Simulate specific action
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::<ACCOUNT>:user/<USER_NAME> \
  --action-names cognito-idp:CreateUserPool cloudwatch:PutDashboard
```

### 10. Apply Fix (With Approval)

If the user approves, apply the fix:

1. If Option A: Add Terraform resources and commit
2. If Option B: Output commands for user to run manually
3. If Option C: Update workflow file and commit

## Output Format

Always output:
1. **Summary**: One-paragraph assessment of current state
2. **Findings Table**: Structured list of issues
3. **Recommended Fix**: The best option for this codebase
4. **Commands/Changes**: Exact code or commands to apply
5. **Verification**: How to confirm the fix worked

## Context

$ARGUMENTS
