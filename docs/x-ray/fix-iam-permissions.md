# Task 1: Fix IAM Permissions for X-Ray

**Priority:** P0
**Spec FRs:** FR-017
**Status:** TODO
**Depends on:** Nothing (foundational)
**Blocks:** All other tasks

---

## Problem

Only 2 of 6 Lambda execution roles have explicit X-Ray write permissions:

| Lambda | Has `AWSXRayDaemonWriteAccess`? | Location |
|--------|-------------------------------|----------|
| Ingestion | NO | — |
| Analysis | NO | — |
| Dashboard | NO | — |
| Metrics | NO | — |
| Notification | YES | `modules/iam/main.tf:755` |
| SSE Streaming | YES | `modules/iam/main.tf:869` |

All 6 have `tracing_mode = "Active"` in Terraform, but Active tracing at the Lambda level only means the Lambda runtime creates a segment. The SDK needs `xray:PutTraceSegments` and `xray:PutTelemetryRecords` permissions to emit subsegments.

Currently, the 4 missing Lambdas work because auto-patched boto3 calls piggyback on the Lambda runtime's segment. But explicit subsegments (tasks 2, 4, 5) will fail without permissions.

---

## Files to Modify

| File | Change |
|------|--------|
| `infrastructure/terraform/modules/iam/main.tf` | Add X-Ray policy attachment for Ingestion, Analysis, Dashboard, Metrics Lambda roles |

---

## What to Change

Add the same `aws_iam_role_policy_attachment` resource pattern used for Notification (line 755) and SSE Streaming (line 869) to the 4 missing Lambda roles.

---

## Success Criteria

- [ ] All 6 Lambda roles have explicit X-Ray write permissions
- [ ] `terraform plan` shows 4 new `aws_iam_role_policy_attachment` resources
- [ ] No changes to existing Notification or SSE Streaming permissions

---

## Blind Spots

1. **Order of operations**: If IAM propagation is slow, deploying new subsegment code simultaneously may fail. Deploy IAM changes first, wait, then deploy code changes.
2. **CI user permissions**: The CI/CD user already has X-Ray management permissions (`ci-user-policy.tf:736-793`), so Terraform can create these attachments.
