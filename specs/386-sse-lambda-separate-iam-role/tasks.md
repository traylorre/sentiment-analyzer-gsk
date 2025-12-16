# Tasks: Spec 386 - Separate IAM Role for SSE Lambda

## Pre-Implementation

- [x] Create spec.md with problem statement and solution
- [x] Create plan.md with implementation steps
- [x] Create tasks.md (this file)

## Implementation Tasks

### Task 1: Add SSE Streaming Lambda IAM Role

**File**: `infrastructure/terraform/modules/iam/main.tf`

- [x] Add `aws_iam_role.sse_streaming_lambda` resource
- [x] Add `aws_iam_role_policy.sse_streaming_dynamodb` with Scan/Query/GetItem
- [x] Attach `AWSLambdaBasicExecutionRole` managed policy
- [x] Add `aws_iam_role_policy.sse_streaming_metrics` for CloudWatch
- [x] Attach `AWSXRayDaemonWriteAccess` managed policy

### Task 2: Export Role from IAM Module

**File**: `infrastructure/terraform/modules/iam/outputs.tf`

- [x] Add `sse_streaming_lambda_role_arn` output
- [x] Add `sse_streaming_lambda_role_name` output

### Task 3: Update SSE Lambda Configuration

**File**: `infrastructure/terraform/main.tf`

- [x] Change `iam_role_arn` from `module.iam.dashboard_lambda_role_arn` to `module.iam.sse_streaming_lambda_role_arn`
- [x] Update comment to reflect dedicated role

### Task 4: Validation

- [x] Run `terraform fmt` to format changes
- [x] Run `terraform validate` to check syntax
- [ ] Run `terraform plan` to verify expected changes (CI will do this)

## Post-Implementation

- [ ] Commit changes with descriptive message
- [ ] Create PR for review
- [ ] Monitor preprod deployment for IAM errors
