# Tasks: Remove Dead NewsAPI Code

## Pre-Implementation

- [x] Audit all NEWSAPI references (127 found)
- [x] Classify as REMOVE vs PRESERVE
- [x] Create spec.md

## Phase 1: Config Layer (Python)

- [ ] Remove `newsapi_secret_arn` field from `IngestionConfig` dataclass in `config.py`
- [ ] Remove `newsapi_secret_arn` validation in `_validate()` method
- [ ] Remove `newsapi_secret_arn` loading in `get_config()` function
- [ ] Update unit tests in `tests/unit/test_ingestion_config.py`

## Phase 2: Infrastructure Layer (Terraform)

- [ ] Remove `aws_secretsmanager_secret.newsapi` resource from `modules/secrets/main.tf`
- [ ] Remove `aws_secretsmanager_secret_rotation.newsapi` resource
- [ ] Remove `newsapi_secret_arn` and `newsapi_secret_name` outputs from `modules/secrets/outputs.tf`
- [ ] Remove `newsapi_secret_arn` variable from `modules/iam/variables.tf`
- [ ] Remove IAM policy statement for newsapi secret access from `modules/iam/main.tf`
- [ ] Remove `NEWSAPI_SECRET_ARN` env var from ingestion Lambda in `main.tf`
- [ ] Remove `newsapi_secret_arn` parameter from IAM module call in `main.tf`
- [ ] Remove `newsapi_secret_arn` root output from `main.tf`
- [ ] Run `terraform fmt` on all modified files
- [ ] Run `terraform validate`

## Phase 3: CI/CD Layer

- [ ] Remove `NEWSAPI_SECRET_ARN` from `.github/workflows/deploy.yml`

## Phase 4: Shell Scripts

- [ ] Remove NewsAPI sections from `scripts/setup-github-secrets.sh`
- [ ] Remove NewsAPI sections from `infrastructure/scripts/setup-credentials.sh`
- [ ] Remove NewsAPI checks from `infrastructure/scripts/pre-deploy-checklist.sh`
- [ ] Remove NewsAPI references from `infrastructure/scripts/demo-setup.sh`
- [ ] Remove NewsAPI checks from `infrastructure/scripts/test-credential-isolation.sh`
- [ ] Remove NewsAPI from `infrastructure/terraform/import-existing.sh`

## Phase 5: Documentation

- [ ] Update `src/lambdas/ingestion/README.md` to remove `NEWSAPI_SECRET_ARN`
- [ ] Update `src/lambdas/README.md` to remove NewsAPI env var reference
- [ ] Update `infrastructure/terraform/README.md` to remove NewsAPI setup instructions
- [ ] Update `docs/DEPLOYMENT.md` to remove NewsAPI row
- [ ] Update `docs/GITHUB_SECRETS_SETUP.md` to remove NewsAPI sections
- [ ] Update `docs/GITHUB_ENVIRONMENTS_SETUP.md` to remove NewsAPI references

## Phase 6: Verification

- [ ] `grep -rn "NEWSAPI_SECRET_ARN" --include="*.tf" --include="*.py" --include="*.yml"` returns empty
- [ ] `grep -rn "newsapi" infrastructure/terraform/modules/secrets/` returns empty
- [ ] `SOURCE_PREFIX = "newsapi"` still exists in `src/lib/deduplication.py`
- [ ] All tests pass: `make test-local`
- [ ] Terraform validates: `terraform validate`

## Post-Implementation

- [ ] Generate proof report showing all removals
- [ ] Create PR with audit summary
