# Research: Skip Pattern Inventory

**Feature**: 078 - Close Config Creation 500 E2E Test Skips
**Date**: 2025-12-10

## Executive Summary

Found **19 total skip patterns** with "500" in E2E tests:
- **18 in-scope** (config creation related, fixed by Feature 077)
- **1 out-of-scope** (magic link endpoint, unrelated to Feature 077)

## Skip Pattern Inventory

### In-Scope: Config Creation 500 Skips (18 total)

| File | Line | Skip Message | Test Function |
|------|------|--------------|---------------|
| test_config_crud.py | 54 | "Config creation endpoint returning 500 - API issue" | test_create_config |
| test_config_crud.py | 98 | "Config creation endpoint returning 500 - API issue" | test_update_config |
| test_config_crud.py | 141 | "Config creation endpoint returning 500 - API issue" | test_delete_config |
| test_config_crud.py | 184 | "Config creation endpoint returning 500 - API issue" | test_get_config |
| test_config_crud.py | 239 | "Config creation endpoint returning 500 - API issue" | test_list_configs |
| test_config_crud.py | 293 | "Config creation endpoint returning 500 - API issue" | test_config_validation |
| test_config_crud.py | 381 | "Config creation endpoint returning 500 - API issue" | test_config_duplicates |
| test_config_crud.py | 422 | "Config lookup endpoint returning 500 - API issue" | test_config_not_found |
| test_anonymous_restrictions.py | 132 | "Config creation endpoint returning 500 - API issue" | test_anonymous_create_config |
| test_anonymous_restrictions.py | 181 | "Config creation endpoint returning 500 - API issue" | test_anonymous_update_config |
| test_anonymous_restrictions.py | 233 | "Config creation endpoint returning 500 - API issue" | test_anonymous_delete_config |
| test_anonymous_restrictions.py | 296 | "Config creation endpoint returning 500 - API issue" | test_anonymous_list_configs |
| test_anonymous_restrictions.py | 345 | "Config creation endpoint returning 500 - API issue" | test_anonymous_config_access |
| test_auth_anonymous.py | 122 | "Config creation endpoint returning 500 - API issue" | test_authenticated_config_create |
| test_auth_anonymous.py | 215 | "Config creation endpoint returning 500 - API issue" | test_authenticated_config_operations |
| test_alerts.py | 54 | "Config creation endpoint returning 500 - API issue" | test_alert_config_dependency |
| test_sentiment.py | 444 | "Invalid config lookup returning 500 - API issue" | test_sentiment_with_invalid_config |
| test_failure_injection.py | 59 | "Config creation endpoint returning 500 - API issue" | test_failure_injection_setup |

### Out-of-Scope: Non-Config 500 Skips (1 total)

| File | Line | Skip Message | Reason Out-of-Scope |
|------|------|--------------|---------------------|
| test_rate_limiting.py | 291 | "Magic link endpoint returning 500 - API issue" | Magic link feature, not fixed by Feature 077 |

## Skip Pattern Analysis

### Pattern Type 1: Direct Conditional Skip (Most Common)
```python
if response.status_code == 500:
    pytest.skip("Config creation endpoint returning 500 - API issue")
```
**Count**: 16 occurrences
**Removal Strategy**: Delete entire `if` block (2-3 lines)

### Pattern Type 2: Comment + Conditional Skip
```python
# Skip if API returns 500 (backend issue, not test issue)
if response.status_code == 500:
    pytest.skip("Config creation endpoint returning 500 - API issue")
```
**Count**: 2 occurrences (test_config_crud.py:52-54, test_auth_anonymous.py:120-122)
**Removal Strategy**: Delete comment AND `if` block

## Research Decisions

### RD-001: Remove Only Config-Related Skips
**Decision**: Only remove skips mentioning "Config creation" or "Config lookup"
**Rationale**: Feature 077 fixed config endpoint, not magic link endpoint

### RD-002: Preserve Other Skip Conditions
**Decision**: If a test has multiple skip conditions, only remove the 500-related one
**Rationale**: Other conditions (e.g., "endpoint not implemented") remain valid

### RD-003: Remove Associated Comments
**Decision**: Remove explanatory comments like "# Skip if API returns 500"
**Rationale**: Clean removal, no dead comments

## Pre-Implementation Verification

Before removing skips, verify Feature 077 is deployed:
```bash
# Config creation should return 422 for invalid input, not 500
curl -X POST https://preprod-api.example.com/api/v2/config \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}' \
  -w "%{http_code}"
# Expected: 422
```

## Files to Modify Summary

| File | Skip Count | Parallelizable |
|------|------------|----------------|
| test_config_crud.py | 8 | No (same file) |
| test_anonymous_restrictions.py | 5 | Yes |
| test_auth_anonymous.py | 2 | Yes |
| test_alerts.py | 1 | Yes |
| test_sentiment.py | 1 | Yes |
| test_failure_injection.py | 1 | Yes |
| **Total** | **18** | 5 files parallelizable |

## Post-Implementation Validation

1. Run `grep -r "500" tests/e2e/ | grep -i skip` - expect empty
2. Run `pytest tests/e2e/ -k "config" -v` - all should pass
3. Count total skips before/after - should decrease by 18
