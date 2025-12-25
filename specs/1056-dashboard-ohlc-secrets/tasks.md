# Tasks: Dashboard Lambda OHLC Secrets Configuration

**Feature**: 1056-dashboard-ohlc-secrets
**Spec**: [spec.md](./spec.md)

## Phase 1: Setup

- [ ] T001 Verify secrets module outputs exist in infrastructure/terraform/modules/secrets/outputs.tf

## Phase 2: Infrastructure Changes

- [ ] T002 [P] [US1] Add TIINGO_SECRET_ARN to dashboard_lambda environment_variables in infrastructure/terraform/main.tf
- [ ] T003 [P] [US1] Add FINNHUB_SECRET_ARN to dashboard_lambda environment_variables in infrastructure/terraform/main.tf
- [ ] T004 [US1] Verify Dashboard Lambda IAM role has secretsmanager:GetSecretValue in infrastructure/terraform/modules/iam/main.tf

## Phase 3: Validation

- [ ] T005 Run terraform fmt to format changes in infrastructure/terraform/
- [ ] T006 Run terraform validate to check syntax in infrastructure/terraform/

## Dependencies

```
T001 → T002, T003 (must verify outputs exist before using them)
T002, T003 → T004 (env vars first, then IAM)
T004 → T005, T006 (validate after all changes)
```

## Parallel Execution

Tasks T002 and T003 can run in parallel [P] as they modify different lines in the same block.

## Implementation Notes

### Pattern to Follow

From the Ingestion Lambda configuration (infrastructure/terraform/main.tf ~line 289):
```hcl
TIINGO_SECRET_ARN  = module.secrets.tiingo_secret_arn
FINNHUB_SECRET_ARN = module.secrets.finnhub_secret_arn
```

### Target Location

In `module.dashboard_lambda` block, add to `environment_variables`:
```hcl
environment_variables = {
    # ... existing vars ...

    # Feature 1056: OHLC data source secrets for Tiingo/Finnhub adapters
    TIINGO_SECRET_ARN  = module.secrets.tiingo_secret_arn
    FINNHUB_SECRET_ARN = module.secrets.finnhub_secret_arn
}
```
