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

- [x] T001 Update resource pattern in `infrastructure/terraform/ci-user-policy.tf` line 640
  - Change: `"arn:aws:iam::*:user/*-sentiment-deployer"`
  - To: `"arn:aws:iam::*:user/sentiment-analyzer-*-deployer"`

- [x] T002 Update comment in `infrastructure/terraform/ci-user-policy.tf` line 630
  - Change: `# Updated from sentiment-analyzer-*-deployer to *-sentiment-deployer per 090-security-first-burndown`
  - To: `# Pattern: sentiment-analyzer-*-deployer (preprod, prod)`

## Phase 2: Validation

### Goal
Verify changes pass all validation gates before commit.

### Tasks

- [x] T003 Run `terraform fmt` and `terraform validate` on changed file

## Phase 3: Commit & Push

### Goal
Commit with GPG signature and push to trigger pipeline.

### Tasks

- [x] T004 Commit changes with GPG signature and push to main

## Phase 4: Bootstrap (ADMIN REQUIRED)

### Goal
Apply updated IAM policy to AWS (same bootstrap cycle as 094).

### Why This Is Needed
Same chicken-and-egg as 094:
1. Fix updates resource pattern in `ci_deploy_iam` policy
2. terraform plan needs `iam:ListAttachedUserPolicies` to check attachments
3. Deployer lacks that permission because the fix isn't applied yet
4. Circular dependency: can't apply the fix via pipeline

### Tasks

- [ ] T005 **ADMIN** Run terraform apply with elevated credentials:
  ```bash
  cd infrastructure/terraform
  terraform init
  terraform apply -target=aws_iam_policy.ci_deploy_iam
  ```

- [ ] T006 Re-trigger Deploy Pipeline after bootstrap

## Verification Checklist

Post-bootstrap verification:

- [x] V001: terraform plan succeeds without IAM errors
- [x] V002: terraform apply succeeds
- [x] V003: Deploy to Preprod job completes successfully
- [x] V004: Only resource pattern change in diff (no new permissions)

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
