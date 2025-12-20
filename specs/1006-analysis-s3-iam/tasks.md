# Implementation Tasks: Fix Analysis Lambda S3 IAM Permissions

**Feature**: 1006-analysis-s3-iam
**Date**: 2025-12-20
**Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

## Phase 1: Implementation

### Goal: Add s3:HeadObject permission to Analysis Lambda IAM policy

**Independent Test**: After deploying, invoke Analysis Lambda and verify no 403 errors on S3 HeadObject

- [x] T001 Add s3:HeadObject to analysis_s3_model policy in infrastructure/terraform/modules/iam/main.tf:274-276
- [x] T002 Run terraform fmt in infrastructure/terraform/
- [x] T003 Run terraform validate in infrastructure/terraform/

## Phase 2: Verification

### Goal: Confirm fix resolves the 403 error

- [ ] T004 Commit changes with descriptive message
- [ ] T005 Push and create PR with auto-merge
- [ ] T006 After deploy, invoke Analysis Lambda via aws lambda invoke
- [ ] T007 Check CloudWatch logs for absence of 403 errors
- [ ] T008 Query DynamoDB for items with sentiment attribute
- [ ] T009 Verify dashboard shows non-zero counts

## Dependencies

```
T001 (IAM fix) → T002 (format) → T003 (validate) → T004 (commit) → T005 (PR)
    → T006 (invoke) → T007 (logs) → T008 (DynamoDB) → T009 (dashboard)
```

## Parallel Execution

No parallel tasks - this is a sequential infrastructure fix.

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 9 |
| Phase 1 (Implementation) | 3 |
| Phase 2 (Verification) | 6 |
| MVP Scope | T001-T005 (PR merged) |
