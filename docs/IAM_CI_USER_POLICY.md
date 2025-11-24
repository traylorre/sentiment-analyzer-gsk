# CI User IAM Policy Management

## Overview

The GitHub Actions Deploy Pipeline uses IAM users for deploying infrastructure via Terraform:
- `sentiment-analyzer-preprod-ci` - Preprod environment CI user
- `sentiment-analyzer-prod-ci` - Prod environment CI user

These users have a managed IAM policy attached: `PreprodCIDeploymentPolicy` / `ProdCIDeploymentPolicy`

## Recent Updates

### 2025-11-24: Added AWS FIS Permissions

**Issue**: Deploy Pipeline failing with:
```
Error: creating FIS Experiment Template: AccessDeniedException: User is not authorized to perform: fis:CreateExperimentTemplate
Error: creating CloudWatch Logs Log Group: AccessDeniedException: User is not authorized to perform: logs:CreateLogGroup
```

**Root Cause**: CI user policy lacked permissions for:
- AWS Fault Injection Service (FIS) for chaos testing infrastructure
- CloudWatch Logs for FIS experiment logs

**Fix**: Updated `PreprodCIDeploymentPolicy` to v19 with comprehensive FIS permissions:

**New Statements Added**:
1. **FISFullAccess** - All FIS actions (create/update/delete templates, start/stop experiments, etc.)
2. **CloudWatchLogsFIS** - CloudWatch Logs management for `/aws/fis/*` log groups

**Permissions Added**:
- `fis:CreateExperimentTemplate`
- `fis:GetExperimentTemplate`
- `fis:UpdateExperimentTemplate`
- `fis:DeleteExperimentTemplate`
- `fis:ListExperimentTemplates`
- `fis:StartExperiment`
- `fis:StopExperiment`
- `fis:GetExperiment`
- `fis:ListExperiments`
- `fis:GetAction`
- `fis:ListActions`
- `fis:GetTargetResourceType`
- `fis:ListTargetResourceTypes`
- `fis:TagResource`
- `fis:UntagResource`
- `fis:ListTagsForResource`
- `logs:CreateLogGroup` (for `/aws/fis/*`)
- `logs:DeleteLogGroup` (for `/aws/fis/*`)
- `logs:DescribeLogGroups` (for `/aws/fis/*`)
- `logs:PutRetentionPolicy` (for `/aws/fis/*`)
- `logs:TagLogGroup` (for `/aws/fis/*`)
- `logs:UntagLogGroup` (for `/aws/fis/*`)

## Policy Update Procedure

AWS IAM managed policies have a limit of 5 versions. When updating:

1. **List existing versions**:
   ```bash
   aws iam list-policy-versions --policy-arn arn:aws:iam::218795110243:policy/PreprodCIDeploymentPolicy
   ```

2. **Delete oldest non-default version** (if at limit):
   ```bash
   aws iam delete-policy-version \
     --policy-arn arn:aws:iam::218795110243:policy/PreprodCIDeploymentPolicy \
     --version-id v17
   ```

3. **Create new version**:
   ```bash
   aws iam create-policy-version \
     --policy-arn arn:aws:iam::218795110243:policy/PreprodCIDeploymentPolicy \
     --policy-document file://updated-policy.json \
     --set-as-default
   ```

## Current Policy Structure (v19)

The policy grants permissions for:

### AWS Services
- **FIS (Fault Injection Service)**: Full access for chaos testing
- **Lambda**: Full access to preprod functions and layers
- **DynamoDB**: Full access to preprod tables
- **S3**: Full access to preprod buckets + Terraform state bucket
- **SNS**: Full access to preprod topics
- **SQS**: Full access to preprod queues
- **Secrets Manager**: Full access to preprod secrets
- **IAM**: Role/policy management for preprod roles
- **CloudWatch**: Logs, alarms, and metrics
- **EventBridge**: Rule management
- **API Gateway**: Full REST API management
- **Backup**: Backup vault and plan management
- **Budgets**: Budget management

### Resource Scoping
Most permissions are scoped to `preprod-*` resources to prevent cross-environment access.

**Notable Exceptions** (intentionally broad):
- **FIS**: `*` - Required for chaos testing across all target resources
- **CloudWatch Describe Operations**: `*` - Read-only discovery
- **S3 Terraform State**: Specific bucket ARN

## Troubleshooting

### Deploy Pipeline Permission Errors

If Terraform fails with `AccessDeniedException`:

1. **Identify missing action** from error message
2. **Check if action should be in policy**:
   - Infrastructure management actions → Should be included
   - Production-only actions → Should NOT be in preprod policy
3. **Add to appropriate statement** in policy document
4. **Update policy version** (see procedure above)
5. **Retry failed GitHub Actions run**

### Version Limit Reached

Error: `LimitExceeded: Cannot exceed quota for PolicyVersionsPerPolicy: 5`

**Solution**: Delete an old non-default version first (see step 2 above)

### Policy Too Large

Error: `PolicyNotAttachable: Maximum policy size of 10240 bytes exceeded`

**Solutions**:
1. **Use wildcards** for similar actions (e.g., `lambda:*` instead of listing all)
2. **Split into multiple policies** and attach all to user
3. **Create managed policy** instead of inline policy

## References

- [AWS Service Authorization Reference for FIS](https://docs.aws.amazon.com/service-authorization/latest/reference/list_awsfaultinjectionservice.html)
- [AWS FIS IAM Policy Examples](https://docs.aws.amazon.com/fis/latest/userguide/security_iam_id-based-policy-examples.html)
- [AWS Managed Policies for FIS](https://docs.aws.amazon.com/fis/latest/userguide/security-iam-awsmanpol.html)
- [IAM Policy Versions](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_managed-versioning.html)
