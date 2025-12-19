# Feature: Remove Dead NewsAPI Code

## Status: COMPLETED

All dead NewsAPI code has been surgically removed from the codebase. See PROOF_REPORT.md for verification evidence.

## Overview

Surgically remove all dead NEWSAPI/NEWS_API code following Feature 006 migration to Tiingo/Finnhub APIs.

**Context:** Feature 006 migrated from NewsAPI to Tiingo+Finnhub for financial news (see CHANGELOG.md lines 12-46). The migration was completed but dead NewsAPI code persisted after 2 previous incomplete cleanup audits. This specification documented the third audit which successfully removed all production references.

## Problem Statement

127 references to NEWSAPI/NEWS_API remain in the codebase despite:
1. CHANGELOG explicitly documenting removal of NewsAPI integration
2. handler.py using only Tiingo/Finnhub adapters
3. Two previous manual cleanup audits

The dead code:
- Wastes AWS Secrets Manager storage costs
- Creates confusion about which APIs are actually used
- Triggers false positives in security scans
- Violates the constitution's "no dead code" principle

## Requirements

### MUST Remove

| Category | Files | References |
|----------|-------|------------|
| **Config** | `src/lambdas/ingestion/config.py` | `newsapi_secret_arn` field, validation |
| **Terraform** | `modules/secrets/main.tf` | `aws_secretsmanager_secret.newsapi` resource |
| **Terraform** | `modules/secrets/outputs.tf` | `newsapi_secret_arn`, `newsapi_secret_name` outputs |
| **Terraform** | `modules/iam/variables.tf` | `newsapi_secret_arn` variable |
| **Terraform** | `modules/iam/main.tf` | IAM policy for newsapi secret access |
| **Terraform** | `main.tf` | `NEWSAPI_SECRET_ARN` env var |
| **Terraform** | `main.tf` | `newsapi_secret_arn` module parameter |
| **Shell** | `scripts/setup-github-secrets.sh` | NewsAPI setup sections |
| **Shell** | `infrastructure/scripts/setup-credentials.sh` | NewsAPI secret creation |
| **Workflows** | `.github/workflows/deploy.yml` | `NEWSAPI_SECRET_ARN` env injection |
| **Docs** | Various | NewsAPI registration/setup instructions |

### MUST NOT Remove

| Category | Files | Reason |
|----------|-------|--------|
| **Deduplication** | `src/lib/deduplication.py` | `SOURCE_PREFIX = "newsapi"` is data identifier stored in DynamoDB |
| **Test Fixtures** | `tests/**/*.py` | `source_id="newsapi#..."` patterns are valid test data |
| **CHANGELOG** | `CHANGELOG.md` | Historical record of migration |
| **Docs** | Migration docs | Historical context |

## Acceptance Criteria

1. **Zero NewsAPI env vars**: `grep -r "NEWSAPI_SECRET_ARN" infrastructure/` returns empty
2. **Zero NewsAPI secrets in TF**: `grep -r "newsapi" infrastructure/terraform/modules/secrets/` returns empty
3. **Config simplified**: `config.py` has no `newsapi` fields
4. **Tests pass**: All unit, integration, and E2E tests pass
5. **Terraform validates**: `terraform validate` succeeds
6. **Deduplication preserved**: `SOURCE_PREFIX = "newsapi"` still exists in deduplication.py

## Non-Goals

- Changing existing `source_id` format in DynamoDB (would break existing data)
- Removing historical documentation about the migration
- Modifying test fixtures that use `newsapi#` source IDs

## Risks

### Risk: Terraform State Drift
**Mitigation**: Check if `aws_secretsmanager_secret.newsapi` exists in state before removing. If yes, use `terraform state rm` to remove from state without destroying the secret (preserve data).

### Risk: CI/CD Pipeline Failure
**Mitigation**: Remove GitHub secrets `NEWSAPI_SECRET_ARN` from repository settings after code is deployed.

## Dependencies

- None (purely removal task)

## Out of Scope

- Refactoring deduplication to use a different source prefix
- Migrating existing DynamoDB data

## Audit Trail

This specification was generated during the third major audit to purge NEWSAPI code smell. Previous audits:
1. Feature 006 migration (incomplete - left config references)
2. Unknown prior audit (incomplete - left Terraform resources)
3. **This audit**: Comprehensive removal with proof report
