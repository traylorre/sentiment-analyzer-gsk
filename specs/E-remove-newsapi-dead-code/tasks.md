# Tasks: Remove Dead NewsAPI Code

## Status: ALL TASKS COMPLETED

All phases completed successfully. See PROOF_REPORT.md for verification evidence.

## Pre-Implementation

- [x] Audit all NEWSAPI references (127 found)
- [x] Classify as REMOVE vs PRESERVE
- [x] Create spec.md

## Phase 1: Config Layer (Python)

- [x] Remove `newsapi_secret_arn` field from `IngestionConfig` dataclass in `config.py`
- [x] Remove `newsapi_secret_arn` validation in `_validate()` method
- [x] Remove `newsapi_secret_arn` loading in `get_config()` function
- [x] Update unit tests in `tests/unit/test_ingestion_config.py`

## Phase 2: Infrastructure Layer (Terraform)

- [x] Remove `aws_secretsmanager_secret.newsapi` resource from `modules/secrets/main.tf`
- [x] Remove `aws_secretsmanager_secret_rotation.newsapi` resource
- [x] Remove `newsapi_secret_arn` and `newsapi_secret_name` outputs from `modules/secrets/outputs.tf`
- [x] Remove `newsapi_secret_arn` variable from `modules/iam/variables.tf`
- [x] Remove IAM policy statement for newsapi secret access from `modules/iam/main.tf`
- [x] Remove `NEWSAPI_SECRET_ARN` env var from ingestion Lambda in `main.tf`
- [x] Remove `newsapi_secret_arn` parameter from IAM module call in `main.tf`
- [x] Remove `newsapi_secret_arn` root output from `main.tf`
- [x] Run `terraform fmt` on all modified files
- [x] Run `terraform validate`

## Phase 3: CI/CD Layer

- [x] Remove `NEWSAPI_SECRET_ARN` from `.github/workflows/deploy.yml`

## Phase 4: Shell Scripts

- [x] Remove NewsAPI sections from `scripts/setup-github-secrets.sh`
- [x] Remove NewsAPI sections from `infrastructure/scripts/setup-credentials.sh`
- [x] Remove NewsAPI checks from `infrastructure/scripts/pre-deploy-checklist.sh`
- [x] Remove NewsAPI references from `infrastructure/scripts/demo-setup.sh`
- [x] Remove NewsAPI checks from `infrastructure/scripts/test-credential-isolation.sh`
- [x] Remove NewsAPI from `infrastructure/terraform/import-existing.sh`

## Phase 5: Documentation

- [x] Update `src/lambdas/ingestion/README.md` to remove `NEWSAPI_SECRET_ARN`
- [x] Update `src/lambdas/README.md` to remove NewsAPI env var reference
- [x] Update `infrastructure/terraform/README.md` to remove NewsAPI setup instructions
- [x] Update `docs/DEPLOYMENT.md` to remove NewsAPI row
- [x] Update `docs/GITHUB_SECRETS_SETUP.md` to remove NewsAPI sections
- [x] Update `docs/GITHUB_ENVIRONMENTS_SETUP.md` to remove NewsAPI references

## Phase 6: Verification

- [x] `grep -rn "NEWSAPI_SECRET_ARN" --include="*.tf" --include="*.py" --include="*.yml"` returns empty
- [x] `grep -rn "newsapi" infrastructure/terraform/modules/secrets/` returns empty
- [x] `SOURCE_PREFIX = "newsapi"` still exists in `src/lib/deduplication.py`
- [x] All tests pass: `make test-local`
- [x] Terraform validates: `terraform validate`

## Post-Implementation

- [x] Generate proof report showing all removals
- [x] Create PR with audit summary
