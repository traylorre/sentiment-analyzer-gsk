# Feature 604: CloudWatch IAM Permissions for E2E Observability Tests

## Problem Statement

E2E observability tests fail intermittently because the CI/CD deployer roles lack permissions to:
1. Query CloudWatch Logs Insights (verify Lambda log output)
2. Read/write CloudWatch Metrics (verify Lambda custom metrics)
3. Query X-Ray traces (verify Lambda tracing)

## Root Cause

The `cloudwatch-iam-validate` validator detected 9 MEDIUM severity findings across 3 deployer policy files:
- `docs/iam-policies/dev-deployer-policy.json`
- `infrastructure/iam-policies/preprod-deployer-policy.json`
- `infrastructure/iam-policies/prod-deployer-policy.json`

## Requirements

### FR-001: Add CloudWatch Logs Insights Permissions
Add to each deployer policy:
- `logs:StartQuery`
- `logs:GetQueryResults`
- `logs:StopQuery`

Resource scope: Same as existing CloudWatchLogsDevResources statement

### FR-002: Add CloudWatch Metrics Permissions
Add to each deployer policy:
- `cloudwatch:GetMetricData`
- `cloudwatch:PutMetricData`

Resource scope: Lambda function metrics only

### FR-003: Add X-Ray Permissions
Add to each deployer policy:
- `xray:BatchGetTraces`
- `xray:GetTraceSummaries`

Resource scope: Traces for environment-specific Lambda functions

## Implementation

### Files to Modify
1. `docs/iam-policies/dev-deployer-policy.json`
2. `infrastructure/iam-policies/preprod-deployer-policy.json`
3. `infrastructure/iam-policies/prod-deployer-policy.json`

### Implementation Approach
Add new statement blocks for each permission set, scoped to environment-specific resources.

## Verification

Re-run `cloudwatch-iam-validate` and confirm 0 findings.

## Non-Goals
- Changing existing permissions
- Adding permissions beyond what validators flagged
