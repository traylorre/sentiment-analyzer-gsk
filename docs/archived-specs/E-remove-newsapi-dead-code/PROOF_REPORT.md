# NEWSAPI Dead Code Removal - Proof Report

**Date:** 2025-12-18
**Branch:** E-remove-newsapi-dead-code
**Audit:** Third major audit (previous two incomplete)

## Executive Summary

This report documents the surgical removal of dead NewsAPI code following the Feature 006 migration to Tiingo/Finnhub APIs. All NEWSAPI_SECRET_ARN references have been removed while preserving `SOURCE_PREFIX = "newsapi"` data identifiers.

## Pre-Removal Audit

**Total references found:** 127
**References classified as REMOVE:** 22 (production code, infrastructure)
**References classified as PRESERVE:** 105 (documentation, test fixtures, data identifiers)

### Removal Breakdown

| Category | Files Modified | Changes |
|----------|----------------|---------|
| **Python Config** | `src/lambdas/ingestion/config.py` | Removed `newsapi_secret_arn` field, validation, loading |
| **Terraform Secrets** | `modules/secrets/main.tf` | Removed `aws_secretsmanager_secret.newsapi` resource |
| **Terraform Outputs** | `modules/secrets/outputs.tf` | Removed `newsapi_secret_arn`, `newsapi_secret_name` outputs |
| **Terraform IAM Vars** | `modules/iam/variables.tf` | Removed `newsapi_secret_arn` variable, added `tiingo_secret_arn`, `finnhub_secret_arn` |
| **Terraform IAM Policy** | `modules/iam/main.tf` | Updated `ingestion_secrets` policy to use Tiingo/Finnhub |
| **Terraform Root** | `main.tf` | Removed `NEWSAPI_SECRET_ARN` env var, module param, output |
| **GitHub Workflow** | `.github/workflows/deploy.yml` | Removed `NEWSAPI_SECRET_ARN` env injection |
| **Unit Tests** | `tests/unit/test_ingestion_config.py` | Removed `NEWSAPI_SECRET_ARN` from fixtures |

## Verification Commands

### 1. No NEWSAPI_SECRET_ARN in Infrastructure/Code

```bash
$ grep -rn "NEWSAPI_SECRET_ARN" --include="*.tf" --include="*.py" --include="*.yml" --exclude-dir=mutants
# Result: No matches - CLEAN
```

### 2. No newsapi in Secrets Module

```bash
$ grep -rn "newsapi" infrastructure/terraform/modules/secrets/
# Result: No matches - CLEAN
```

### 3. SOURCE_PREFIX Preserved

```bash
$ grep -n "SOURCE_PREFIX" src/lib/deduplication.py
38:SOURCE_PREFIX = "newsapi"
81:    source_id = f"{SOURCE_PREFIX}#{hash_truncated}"
# Result: PRESERVED (data identifier, not API reference)
```

### 4. Terraform Validation

```bash
$ terraform fmt -recursive
$ terraform validate
Success! The configuration is valid.
```

### 5. Python Syntax Validation

```bash
$ python -m py_compile src/lambdas/ingestion/config.py tests/unit/test_ingestion_config.py
# Result: PASS
```

## Preserved References (Intentional)

The following newsapi references are **intentionally preserved** as they are data identifiers, not API references:

| File | Reference | Reason |
|------|-----------|--------|
| `src/lib/deduplication.py:38` | `SOURCE_PREFIX = "newsapi"` | DynamoDB source_id format |
| `tests/**/*.py` | `source_id="newsapi#..."` | Test fixture data |
| `CHANGELOG.md` | Migration documentation | Historical record |
| Various docs | Setup instructions | Archived for reference |

## IAM Policy Migration

The `ingestion_secrets` IAM policy was updated from:

```hcl
# BEFORE (removed)
Resource = var.newsapi_secret_arn
```

To:

```hcl
# AFTER (current)
Resource = [
  var.tiingo_secret_arn,
  var.finnhub_secret_arn
]
```

## Files Changed Summary

```
src/lambdas/ingestion/config.py           # -newsapi_secret_arn field
infrastructure/terraform/modules/secrets/main.tf  # -newsapi secret resource
infrastructure/terraform/modules/secrets/outputs.tf  # -newsapi outputs
infrastructure/terraform/modules/iam/variables.tf  # -newsapi, +tiingo, +finnhub
infrastructure/terraform/modules/iam/main.tf  # Updated policy
infrastructure/terraform/main.tf  # -newsapi env, params, outputs
.github/workflows/deploy.yml  # -NEWSAPI_SECRET_ARN
tests/unit/test_ingestion_config.py  # -newsapi from fixtures
specs/E-remove-newsapi-dead-code/spec.md  # Created
specs/E-remove-newsapi-dead-code/tasks.md  # Created
```

## Post-Deployment Actions Required

1. **Remove GitHub Secret:** Delete `NEWSAPI_SECRET_ARN` from repository secrets
2. **Terraform State:** If `aws_secretsmanager_secret.newsapi` exists in state, run `terraform state rm` before destroy
3. **Optional:** Delete the actual NewsAPI secret from AWS Secrets Manager (preserves cost)

## Conclusion

All dead NewsAPI code has been surgically removed. The codebase now correctly uses only Tiingo and Finnhub for financial news ingestion as documented in CHANGELOG.md Feature 006.

**Verification Status:** COMPLETE
