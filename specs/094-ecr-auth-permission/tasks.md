# 094: ECR Authorization Permission Fix - Tasks

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 6 |
| Parallelizable | 2 (T001, T002) |
| File Changes | 1 (`ci-user-policy.tf`) |
| Estimated Changes | 8 string replacements |

## Phase 1: Implementation

### Goal
Update IAM policy attachment user references to match actual AWS IAM user names.

### Tasks

- [x] T001 [P] Update preprod user references in `infrastructure/terraform/ci-user-policy.tf`
  - Line 1143: `preprod-sentiment-deployer` → `sentiment-analyzer-preprod-deployer`
  - Line 1148: `preprod-sentiment-deployer` → `sentiment-analyzer-preprod-deployer`
  - Line 1153: `preprod-sentiment-deployer` → `sentiment-analyzer-preprod-deployer`
  - Line 1158: `preprod-sentiment-deployer` → `sentiment-analyzer-preprod-deployer`

- [x] T002 [P] Update prod user references in `infrastructure/terraform/ci-user-policy.tf`
  - Line 1169: `prod-sentiment-deployer` → `sentiment-analyzer-prod-deployer`
  - Line 1174: `prod-sentiment-deployer` → `sentiment-analyzer-prod-deployer`
  - Line 1179: `prod-sentiment-deployer` → `sentiment-analyzer-prod-deployer`
  - Line 1184: `prod-sentiment-deployer` → `sentiment-analyzer-prod-deployer`

## Phase 2: Validation

### Goal
Verify changes pass all validation gates before commit.

### Tasks

- [x] T003 Run `make validate` to verify formatting and security checks pass
- [x] T004 Run `terraform fmt` and `terraform validate` on changed files

## Phase 3: Commit & PR

### Goal
Create PR with GPG-signed commit and verify CI passes.

### Tasks

- [ ] T005 Commit changes with GPG signature (`git commit -S`)
- [ ] T006 Push branch and create PR with auto-merge enabled

## Verification Checklist

Post-merge verification (via TFC and Deploy Pipeline):

- [ ] V001: Terraform plan shows exactly 8 policy attachment changes
- [ ] V002: Terraform apply succeeds without errors
- [ ] V003: Deploy Pipeline ECR login step passes
- [ ] V004: No new IAM permissions added (diff shows only user attribute changes)

## Dependencies

```
T001 ─┬─> T003 ─> T004 ─> T005 ─> T006
T002 ─┘
```

T001 and T002 can run in parallel (different line ranges in same file).
T003-T006 must run sequentially after implementation.

## Success Criteria Mapping

| Success Criteria | Verification Task |
|-----------------|-------------------|
| SC-001: ECR login succeeds | V003 |
| SC-002: 4 preprod attachments updated | T001 + V001 |
| SC-003: 4 prod attachments updated | T002 + V001 |
| SC-004: Only attachment changes | V001, V004 |
| SC-005: No new permissions | V004 |
