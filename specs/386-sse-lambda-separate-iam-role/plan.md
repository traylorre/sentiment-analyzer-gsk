# Plan: Spec 386 - Separate IAM Role for SSE Lambda

## Overview

Create a dedicated IAM role for the SSE Streaming Lambda, following the established pattern from other Lambda roles (ingestion, analysis, dashboard, metrics, notification).

## Implementation Steps

### Step 1: Add SSE Streaming Lambda Role to IAM Module

**File**: `infrastructure/terraform/modules/iam/main.tf`

Add new role definition following the established pattern:
1. Create `aws_iam_role.sse_streaming_lambda` with Lambda trust policy
2. Create `aws_iam_role_policy.sse_streaming_dynamodb` with:
   - `dynamodb:Scan` (metrics polling every 5s)
   - `dynamodb:Query` (config lookup)
   - `dynamodb:GetItem` (config validation)
   - Resource: sentiment-items table + indexes
3. Attach `AWSLambdaBasicExecutionRole` managed policy for CloudWatch Logs
4. Create `aws_iam_role_policy.sse_streaming_metrics` for CloudWatch:PutMetricData
5. Attach `AWSXRayDaemonWriteAccess` managed policy for X-Ray tracing

### Step 2: Export Role ARN from IAM Module

**File**: `infrastructure/terraform/modules/iam/outputs.tf`

Add outputs:
- `sse_streaming_lambda_role_arn`
- `sse_streaming_lambda_role_name`

### Step 3: Update SSE Lambda to Use New Role

**File**: `infrastructure/terraform/main.tf`

Change line 621 from:
```hcl
iam_role_arn = module.iam.dashboard_lambda_role_arn # Reuse dashboard role
```
To:
```hcl
iam_role_arn = module.iam.sse_streaming_lambda_role_arn
```

### Step 4: Validate with Terraform Plan

Run `terraform plan` to verify:
- New IAM role resource will be created
- New IAM policies will be attached
- SSE Lambda configuration will be updated
- No unexpected changes to other resources

## Architectural Decision

**Why separate roles instead of adding permissions to existing role?**

1. **Least Privilege**: SSE Lambda only needs Scan access; Dashboard needs complex Feature 006 permissions, Secrets Manager, chaos testing, etc.

2. **Blast Radius**: If SSE Lambda is compromised, attacker cannot access:
   - Secrets Manager (API keys)
   - Feature 006 users table (PII)
   - S3 ticker cache
   - FIS chaos testing

3. **Auditability**: CloudTrail logs clearly identify which Lambda performed which action.

4. **Existing Pattern**: Every other Lambda (ingestion, analysis, dashboard, metrics, notification) has its own role.

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| New role creation fails | Terraform will rollback on apply failure |
| SSE Lambda fails with new role | Rollback by changing IAM ARN back to dashboard role |
| Missing permission discovered later | Role is isolated, can add permission without affecting other Lambdas |

## Rollback Plan

If deployment fails:
```hcl
# Revert main.tf line 621 to:
iam_role_arn = module.iam.dashboard_lambda_role_arn
```

Run `terraform apply` - SSE Lambda returns to using Dashboard role.

## Acceptance Validation

After deployment:
1. Check CloudWatch logs for SSE Lambda - no AccessDeniedException
2. Test `/api/v2/stream` endpoint - receives sentiment data
3. Verify Dashboard Lambda still works - no regression
