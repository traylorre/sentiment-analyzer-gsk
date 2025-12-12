# 095: IAM User Resource Pattern Fix - Tasks

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 4 |
| Parallelizable | 0 |
| File Changes | 1 (`ci-user-policy.tf`) |
| Estimated Changes | 2 line modifications |

## Phase 1: Implementation

### Goal
Fix IAM policy resource constraint pattern to match actual AWS IAM user names.

### Tasks

- [ ] T001 Update resource pattern in `infrastructure/terraform/ci-user-policy.tf` line 640
  - Change: `"arn:aws:iam::*:user/*-sentiment-deployer"`
  - To: `"arn:aws:iam::*:user/sentiment-analyzer-*-deployer"`

- [ ] T002 Update comment in `infrastructure/terraform/ci-user-policy.tf` line 630
  - Change: `# Updated from sentiment-analyzer-*-deployer to *-sentiment-deployer per 090-security-first-burndown`
  - To: `# Pattern: sentiment-analyzer-*-deployer (preprod, prod)`

## Phase 2: Validation

### Goal
Verify changes pass all validation gates before commit.

### Tasks

- [ ] T003 Run `terraform fmt` and `terraform validate` on changed file

## Phase 3: Commit & Push

### Goal
Commit with GPG signature and push to trigger pipeline.

### Tasks

- [ ] T004 Commit changes with GPG signature and push to main

## Verification Checklist

Post-push verification (via Deploy Pipeline):

- [ ] V001: terraform plan succeeds without IAM errors
- [ ] V002: terraform apply succeeds
- [ ] V003: Deploy to Preprod job completes successfully
- [ ] V004: Only resource pattern change in diff (no new permissions)

## Dependencies

```
T001 ─> T002 ─> T003 ─> T004
```

All tasks are sequential (same file, logical order).

## Success Criteria Mapping

| Success Criteria | Verification Task |
|-----------------|-------------------|
| SC-001: terraform plan succeeds | V001 |
| SC-002: terraform apply succeeds | V002, V003 |
| SC-003: No new permissions added | V004 |
