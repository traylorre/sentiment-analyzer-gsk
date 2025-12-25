# Tasks: Dashboard Lambda KMS Decrypt Permission

**Feature Branch**: `1058-dashboard-kms-decrypt`
**Created**: 2025-12-25
**Spec**: [spec.md](./spec.md)
**Plan**: [plan.md](./plan.md)

## Summary

Add KMS decrypt permission to the dashboard Lambda's secrets policy, enabling OHLC data fetching by allowing the Lambda to decrypt Tiingo/Finnhub API keys from Secrets Manager.

## Dependency Graph

```
Phase 1 (Setup) → Phase 2 (Foundational) → Phase 3 (User Story 1) → Phase 4 (Polish)
```

All phases are sequential for this feature due to single-file modification scope.

---

## Phase 1: Setup

**Goal**: Verify current state and prepare for modification

- [ ] T001 Verify current dashboard_secrets policy structure in infrastructure/terraform/modules/iam/main.tf
- [ ] T002 Verify secrets_kms_key_arn variable exists in infrastructure/terraform/modules/iam/variables.tf

---

## Phase 2: Foundational

**Goal**: Understand the pattern to replicate

- [ ] T003 Document ingestion Lambda KMS decrypt pattern (lines 79-87) in infrastructure/terraform/modules/iam/main.tf

---

## Phase 3: User Story 1 - Dashboard OHLC Data Access (P1)

**Goal**: Enable dashboard Lambda to decrypt secrets with customer-managed KMS keys
**Independent Test**: terraform plan shows expected policy modification with kms:Decrypt action

- [ ] T004 [US1] Add conditional KMS decrypt statement to dashboard_secrets policy in infrastructure/terraform/modules/iam/main.tf

Pattern to implement:
```hcl
policy = jsonencode({
  Version = "2012-10-17"
  Statement = concat([
    {
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = [
        var.dashboard_api_key_secret_arn,
        var.tiingo_secret_arn,
        var.finnhub_secret_arn
      ]
    }
  ],
  # KMS decrypt required when secrets use customer-managed KMS keys
  var.secrets_kms_key_arn != "" ? [
    {
      Effect = "Allow"
      Action = [
        "kms:Decrypt"
      ]
      Resource = var.secrets_kms_key_arn
    }
  ] : [])
})
```

- [ ] T005 [US1] Run terraform fmt on infrastructure/terraform/modules/iam/main.tf
- [ ] T006 [US1] Run terraform validate in infrastructure/terraform/

---

## Phase 4: Polish & Validation

**Goal**: Ensure change meets quality standards

- [ ] T007 Run make validate in repository root
- [ ] T008 Run terraform plan to verify expected policy changes

---

## Parallel Execution Examples

Due to single-file scope, sequential execution is required. No parallelization opportunities.

## Implementation Strategy

**MVP Scope**: Phase 3 (User Story 1) - Single policy modification
**Incremental Delivery**: Complete in one PR
**Validation**: terraform plan shows only dashboard_secrets policy modification

## Task Count Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| Phase 1 | 2 | Setup verification |
| Phase 2 | 1 | Pattern documentation |
| Phase 3 | 3 | User Story 1 implementation |
| Phase 4 | 2 | Polish & validation |
| **Total** | **8** | |
