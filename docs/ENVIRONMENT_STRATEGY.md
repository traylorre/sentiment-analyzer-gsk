# Environment Strategy: Dev / Preprod / Prod

**Date**: 2025-11-20
**Status**: IMPLEMENTED

---

## Overview

This project uses a **three-environment strategy** to balance development velocity, cost control, and production confidence.

```
LOCAL → DEV → PREPROD → PROD
```

Each environment serves a distinct purpose with different testing and deployment strategies.

---

## Environment Breakdown

### LOCAL (Developer Machine)

**Purpose**: Rapid development and debugging

**Testing**:
- ✅ Unit tests ONLY (all mocked)
- ❌ No integration tests (too slow for local iteration)

**Run Triggers**:
- On file save (IDE auto-test)
- On `git commit` (pre-commit hook)
- Manual: `pytest tests/unit/ -v`

**Cost**: $0

**Resources**:
- No AWS resources
- All tests use moto/unittest.mock

---

### DEV (CI Pipeline - Mocked AWS)

**Purpose**: Continuous integration with fast feedback

**Testing**:
- ✅ Unit tests (all mocked)
- ✅ E2E tests with mocked AWS (moto)
  - Files: `tests/integration/test_*_dev.py`
  - Mock: DynamoDB, SNS, SQS, Secrets Manager (moto)
  - Mock: NewsAPI (responses library)
  - Mock: ML inference (unittest.mock)

**Run Triggers**:
- Every PR to main
- Every merge to main
- Dependabot PRs (auto-merge eligible)

**CI Workflow**: `.github/workflows/test.yml`

**Cost**: $0 (no real AWS resources)

**Deployment**: None (tests only)

**Why Mocked AWS?**
- Fast execution (no real API calls)
- No AWS costs
- Safe for high-frequency runs (Dependabot PRs)
- Immediate feedback on code changes

---

### PREPROD (AWS - Production Mirror)

**Purpose**: Final validation before production deployment

**Testing**:
- ✅ Integration tests against REAL AWS
  - Files: `tests/integration/test_*_preprod.py`
  - Real: DynamoDB, Lambda, SNS, SQS, S3, Secrets Manager
  - Mock: NewsAPI (external dependency)
  - Mock: ML inference (expensive/non-deterministic)

**Run Triggers**:
- ❌ NOT on every PR/merge (cost control)
- ✅ Manual trigger via GitHub Actions
- ✅ Weekly automated run (optional)
- ✅ Before production deployment (required)

**CI Workflow**: `.github/workflows/preprod-validation.yml`

**Cost**: ~$5-20/month
- On-demand DynamoDB
- Lambda invocations during tests
- S3 storage minimal
- EventBridge scheduled at 2-hour intervals (vs 15 min in prod)

**Deployment**:
```bash
cd infrastructure/terraform
terraform init -backend-config=backend-preprod.hcl -reconfigure
terraform apply -var-file=preprod.tfvars
```

**Infrastructure**:
- Identical Terraform modules to prod
- Different `preprod.tfvars` for scale/cost optimization
- Separate state file: `preprod/terraform.tfstate`
- Separate lock table: `terraform-state-lock-preprod`

**Why Real AWS?**
- Catches infrastructure mismatches (GSI projections, IAM permissions)
- Tests actual Terraform-deployed resources
- High confidence: works in preprod → works in prod
- Production rehearsal

---

### PROD (AWS - Live)

**Purpose**: Serve real users

**Testing**:
- ✅ Canary test (hourly health check)
- ✅ Alerting on failures
- ❌ No integration tests (read-only monitoring only)

**Run Triggers**:
- Manual deployment after preprod validation
- Requires: Preprod integration tests passing

**CI Workflow**: `.github/workflows/deploy-prod.yml` (manual trigger)

**Cost**: TBD based on usage
- Provisioned capacity or on-demand
- EventBridge at 15-minute intervals
- Production-scale resources

**Deployment**:
```bash
cd infrastructure/terraform
terraform init -backend-config=backend-prod.hcl -reconfigure
terraform apply -var-file=prod.tfvars
```

**Promotion Flow**:
1. Code merged to main
2. Dev tests pass (auto)
3. **Manual**: Trigger preprod validation
4. Preprod integration tests pass
5. **Manual**: Review preprod results
6. **Manual**: Deploy to prod
7. Canary test confirms health

---

## Test File Organization

### Unit Tests (`tests/unit/`)
**All Environments**: Local, Dev CI

```
test_analysis_handler.py     # Analysis Lambda logic
test_dashboard_handler.py    # Dashboard API logic
test_ingestion_handler.py    # Ingestion Lambda logic
test_newsapi_adapter.py      # NewsAPI client
test_sentiment.py            # ML inference wrapper
```

**Mocking**: Everything (moto, unittest.mock, pytest fixtures)

---

### Dev Integration Tests (`tests/integration/test_*_dev.py`)
**Environment**: Dev CI only

```
test_analysis_dev.py         # E2E with mocked AWS
test_dashboard_dev.py        # E2E with mocked AWS
test_ingestion_dev.py        # E2E with mocked AWS
```

**Mocking**:
- ✅ AWS (moto): DynamoDB, SNS, SQS, Secrets
- ✅ NewsAPI (responses)
- ✅ ML inference (unittest.mock)

**Run**: Every PR, every merge, Dependabot

---

### Preprod Integration Tests (`tests/integration/test_*_preprod.py`)
**Environment**: Preprod AWS only

```
test_analysis_preprod.py     # E2E with REAL AWS
test_dashboard_preprod.py    # E2E with REAL AWS
test_ingestion_preprod.py    # E2E with REAL AWS
```

**Mocking**:
- ❌ AWS infrastructure (uses REAL preprod DynamoDB, Lambda, SNS)
- ✅ NewsAPI (responses) - external dependency
- ✅ ML inference (unittest.mock) - expensive exception

**Run**: Manual trigger, weekly automation, before prod deploy

---

## Workflow Decision Tree

### When to Run Which Tests?

```
┌─────────────────────────────────────────────────────────────┐
│ Developer commits code                                      │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Pre-commit hook       │
              │ → Unit tests          │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ git push              │
              │ → Dev CI              │
              │   • Unit tests        │
              │   • Dev E2E (mocked)  │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ PR merge to main      │
              │ → Dev CI (same)       │
              └───────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │ Ready for release?    │
              └───────────────────────┘
                          │
                     ┌────┴────┐
                     ▼         ▼
               ┌─────┐     ┌──────┐
               │ No  │     │ Yes  │
               └─────┘     └──────┘
                               │
                               ▼
              ┌───────────────────────────────┐
              │ Manual: Trigger preprod       │
              │ → Deploy preprod              │
              │ → Run integration tests       │
              │   (REAL AWS)                  │
              └───────────────────────────────┘
                               │
                          ┌────┴────┐
                          ▼         ▼
                     ┌────────┐ ┌──────┐
                     │ Fail   │ │ Pass │
                     └────────┘ └──────┘
                          │         │
                          │         ▼
                          │    ┌─────────────────────┐
                          │    │ Manual: Deploy prod │
                          │    └─────────────────────┘
                          │
                          ▼
                   ┌───────────────┐
                   │ Fix in dev    │
                   │ Repeat        │
                   └───────────────┘
```

---

## Cost Comparison

| Environment | Monthly Cost | Runs Per Month | Cost Per Run |
|-------------|--------------|----------------|--------------|
| Local       | $0           | Unlimited      | $0           |
| Dev (CI)    | $0           | ~500 (PRs)     | $0           |
| Preprod     | $5-20        | ~4-10 (manual) | ~$1-2        |
| Prod        | TBD          | 1 (live)       | N/A          |

**Savings from this strategy**:
- Before: Dev integration tests on every PR = ~500 AWS runs/month
- After: Preprod integration tests on release only = ~4-10 AWS runs/month
- **Cost reduction**: ~98%

---

## Migration from Previous State

### What Changed?

**Before** (Single Dev Environment):
- Dev had REAL AWS resources
- Integration tests ran on every PR
- High cost, slow feedback

**After** (Three Environments):
- Dev: Mocked AWS, fast, $0 cost
- Preprod: Real AWS, manual, ~$10/month
- Prod: Real AWS, live

### Migration Checklist

- [x] Create `test_*_dev.py` with moto mocks
- [x] Rename real AWS tests to `test_*_preprod.py`
- [x] Create `backend-preprod.hcl`
- [x] Create `preprod.tfvars`
- [x] Create `bootstrap-preprod.sh`
- [ ] Run `bootstrap-preprod.sh` to create lock table
- [ ] Update `.github/workflows/test.yml` (dev CI)
- [ ] Create `.github/workflows/preprod-validation.yml`
- [ ] Update constitution with environment strategy
- [ ] First preprod deploy and validation

---

## Key Principles

1. **Dev is for iteration**: Fast feedback, zero cost, high frequency
2. **Preprod is production rehearsal**: Real AWS, controlled cost, low frequency
3. **Prod is sacred**: Manual deployment, high confidence from preprod
4. **Cost follows value**: Pay for real AWS only when validating releases
5. **Tests run where appropriate**: Unit (everywhere), E2E mocked (dev), E2E real (preprod)

---

## FAQs

**Q: Can I run preprod tests locally?**
A: Yes, if you have AWS credentials for preprod. But it's expensive and slow. Use dev tests locally.

**Q: How do I validate a Dependabot PR?**
A: Dev CI runs automatically with mocked AWS. No preprod validation needed for dependencies.

**Q: When should I trigger preprod validation?**
A: Before deploying to production, or weekly to catch infrastructure drift.

**Q: What if preprod tests fail?**
A: Fix the issue in dev, merge to main, then re-trigger preprod validation.

**Q: Can we skip preprod and deploy directly to prod?**
A: **Never.** Preprod is the safety net. Always validate there first.

**Q: How do I know preprod matches prod?**
A: Same Terraform modules, only `tfvars` differ (scale/schedule). Infrastructure is identical.
