# Research: Complete NewsAPI Reference Purge

**Feature**: 501-purge-newsapi
**Date**: 2025-12-19
**Status**: Complete

## Research Summary

Comprehensive scan of `/home/traylorre/projects/sentiment-analyzer-gsk` identified **93 files** containing "newsapi" or "news_api" references across 6 categories.

---

## 1. Core Source Files (src/lib/*.py)

**File Count**: 2 files
**Change Type**: Prefix constant update + docstring examples

### Files

| File | Occurrences | Critical Changes |
|------|-------------|------------------|
| `src/lib/deduplication.py` | ~15 | `SOURCE_PREFIX = "newsapi"` → `"article"`, all docstrings |
| `src/lib/metrics.py` | ~5 | CloudWatch filter examples |

### Key Change

```python
# src/lib/deduplication.py:38
# BEFORE
SOURCE_PREFIX = "newsapi"

# AFTER
SOURCE_PREFIX = "article"
```

---

## 2. Lambda Source Files (src/lambdas/**/*.py)

**File Count**: 9 files
**Change Type**: Mixed (prefix updates + dead code removal)

### Active Files (need prefix updates)

| File | Occurrences | Type |
|------|-------------|------|
| `shared/schemas.py` | 4 | Validator field examples |
| `shared/dynamodb.py` | 2 | Docstring examples |
| `shared/secrets.py` | 4 | Secret path examples |
| `shared/chaos_injection.py` | 1 | Scenario type |
| `dashboard/chaos.py` | 5 | Chaos scenario types |
| `dashboard/handler.py` | 1 | API doc example |
| `ingestion/adapters/base.py` | 2 | Docstring examples |

### Dead Code (can remove comments)

| File | Content |
|------|---------|
| `ingestion/__init__.py` | "# Legacy: NewsAPI-based ingestion removed" |
| `ingestion/adapters/__init__.py` | "# Legacy: NewsAPI adapter removed" |

---

## 3. Test Files (tests/**/*.py)

**File Count**: 16 files
**Change Type**: Test fixture/assertion updates

### Files with Most Occurrences

| File | Occurrences | Type |
|------|-------------|------|
| `tests/unit/test_analysis_handler.py` | 15+ | Test fixtures |
| `tests/unit/test_secrets.py` | 12+ | Mock secrets |
| `tests/unit/test_metrics.py` | 8 | Assertions |
| `tests/unit/test_deduplication.py` | 8 | Core assertions |
| `tests/unit/test_errors.py` | 4 | Resource IDs |
| `tests/unit/test_schemas.py` | 3 | Validation |
| `tests/unit/test_dynamodb_helpers.py` | 2 | Examples |
| `tests/unit/test_dashboard_handler.py` | 2 | API tests |
| `tests/unit/test_dashboard_metrics.py` | 2 | Metrics |
| `tests/unit/test_chaos_injection.py` | 2 | Chaos |
| `tests/unit/test_chaos_fis.py` | 1 | FIS |
| `tests/integration/test_analysis_dev.py` | 2 | Integration |
| `tests/integration/test_analysis_preprod.py` | 2 | Integration |
| `tests/e2e/test_full_pipeline.py` | 1 | E2E |
| `tests/conftest.py` | 2 | Shared fixtures |
| `tests/fixtures/synthetic_data.py` | 3 | Synthetic data |

---

## 4. Documentation (*.md)

**File Count**: 23 files
**Change Type**: Narrative/example updates

### Categories

| Category | Files | Change Required |
|----------|-------|-----------------|
| Project root | CLAUDE.md | Update examples |
| docs/ | 21 files | Update operator guides, runbooks |
| src/lib/ | README.md | Update lib overview |

### Key Files

- `CLAUDE.md` - Project guidelines
- `docs/CHAOS_TESTING_OPERATOR_GUIDE.md` - Chaos scenarios
- `docs/GITHUB_SECRETS_SETUP.md` - Secret names
- `docs/DEPLOYMENT.md` - Deployment examples
- `docs/LESSONS_LEARNED.md` - Historical context

---

## 5. Infrastructure (infrastructure/**)

**File Count**: 12 files
**Change Type**: Secret path examples, script updates

### Terraform

| File | Content |
|------|---------|
| `terraform/ci-user-policy.tf` | Secret policy examples |

### Scripts

| File | Content |
|------|---------|
| `scripts/demo-setup.sh` | Demo credentials |
| `scripts/demo-validate.sh` | Validation |
| `scripts/setup-credentials.sh` | Credential setup |
| `scripts/test-credential-isolation.sh` | Isolation test |
| `scripts/pre-deploy-checklist.sh` | Checklist |

### Documentation

| File | Content |
|------|---------|
| `terraform/README.md` | Terraform overview |
| `terraform/bootstrap/README.md` | Bootstrap guide |
| `docs/CREDENTIAL_SEPARATION_SETUP.md` | Credential guide |
| `docs/TERRAFORM_RESOURCE_VERIFICATION.md` | Verification guide |

---

## 6. Specifications (specs/**)

**File Count**: 24 files
**Change Type**: Historical context (mostly preserve)

### Active Specs (update)

| File | Status |
|------|--------|
| `specs/501-purge-newsapi/spec.md` | Current removal spec |
| `specs/E-remove-newsapi-dead-code/spec.md` | Related removal spec |

### Historical Specs (preserve as-is)

- `specs/001-interactive-dashboard-demo/*` - Original planning docs
- `specs/004-remove-test-placeholders/*` - Test debt
- `specs/005-synthetic-test-data/*` - Test data
- `specs/006-user-config-dashboard/*` - Dashboard spec
- `specs/086-test-debt-burndown/*` - Debt tracking
- `specs/087-test-coverage-completion/*` - Coverage tracking

---

## Decision: article# Prefix

### Why "article#" is correct

1. **Source-agnostic**: Represents WHAT the entity is, not WHERE it came from
2. **Future-proof**: No code changes when adding/removing data sources
3. **Deduplication**: Same article from different sources gets same ID
4. **Not a code smell**: "tiingo#" or "finnhub#" would couple deduplication to vendors

### Alternatives Rejected

| Alternative | Reason Rejected |
|-------------|-----------------|
| `tiingo#` | Vendor-specific, code smell |
| `finnhub#` | Vendor-specific, code smell |
| `news#` | Too generic, could conflict |
| `source#` | Ambiguous meaning |

---

## Implementation Order

1. **Core source** (src/lib/deduplication.py) - Fix the constant FIRST
2. **Lambda source** (src/lambdas/shared/schemas.py) - Fix validators
3. **Tests** - Update assertions to match new prefix
4. **Dead code** - Remove legacy comments
5. **Documentation** - Update examples and narratives
6. **Infrastructure** - Update script examples
7. **Verification** - grep must return 0 matches
