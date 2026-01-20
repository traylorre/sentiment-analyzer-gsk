# Technical Debt Inventory - Target Repo (sentiment-analyzer-gsk)

**Generated**: 2025-12-10
**Status**: Consolidated tech debt and deferred work

---

## Summary

| Category | Count | Priority |
|----------|-------|----------|
| E2E Test Skips (Config Creation 500) | ~15 | **NOW CLOSEABLE** (Feature 077 merged) |
| E2E Test Skips (Endpoint Not Implemented) | ~60 | Feature work required |
| E2E Test Skips (Auth/Environment) | ~20 | Integration constraints |
| Unit Test Skips (Validator TODO) | 6 | Easy - use /add-validator |
| Source TODOs | 3 | Documentation |
| Deferred Architecture | 1 | Future improvement |

---

## 1. E2E Tests - NOW CLOSEABLE (Feature 077)

These tests were skipping due to "Config creation endpoint returning 500" which is now fixed:

| File | Tests | Action |
|------|-------|--------|
| `test_config_crud.py` | 8 tests | Remove skip, should pass |
| `test_alerts.py` | 2 tests | Remove skip, should pass |
| `test_anonymous_restrictions.py` | 5 tests | Remove skip, should pass |
| `test_auth_anonymous.py` | 2 tests | Remove skip, should pass |
| `test_failure_injection.py` | 1 test | Remove skip, should pass |

**Total**: ~18 tests can be unskipped after preprod deployment

**Next Step**: After `make deploy-preprod`, run:
```bash
pytest tests/e2e/ -k "config" --no-skip -v
```

---

## 2. E2E Tests - Endpoint Not Implemented

These require feature implementation before unskipping:

### Notifications (~10 tests)
- `test_notifications.py`: 7 tests - "Notifications endpoint not implemented"
- `test_notification_preferences.py`: 13 tests - "Preferences endpoint not implemented"

### Alerts (~9 tests)
- `test_alerts.py`: 9 tests - "Alerts endpoint not implemented"

### Market Status (~6 tests)
- `test_market_status.py`: 6 tests - "Market status endpoint not implemented"

### Ticker Validation (~7 tests)
- `test_ticker_validation.py`: 7 tests - "Ticker validation/search endpoint not implemented"

### Quota (~6 tests)
- `test_quota.py`: 6 tests - "Quota endpoint not implemented"

### Dashboard (~2 tests)
- `test_dashboard_buffered.py`: 2 tests - "Dashboard metrics/Heatmap endpoint not implemented"

### Sentiment Analysis (~3 tests)
- `test_sentiment.py`: 3 tests - "Heatmap/Volatility/Correlation endpoint not implemented"

### Magic Link Auth (~10 tests)
- `test_auth_magic_link.py`: 10 tests - "Magic link endpoint not implemented"
- `test_session_consistency_preprod.py`: 3 tests - "Magic link endpoint not implemented"

### Rate Limiting (~4 tests)
- `test_rate_limiting.py`: 4 tests - "Rate limit recovery/Magic link not implemented"

---

## 3. E2E Tests - Environment/Auth Constraints

These skip based on environment or auth requirements:

### Cleanup Utilities (6 tests)
- `test_cleanup.py`: 6 tests - "Use --run-cleanup to execute"
- **Intentional**: These are cleanup utilities, not tests

### Observability (8 tests)
- `test_observability.py`: 8 tests - CloudWatch/X-Ray access checks
- **Environment**: Requires AWS credentials with CloudWatch/X-Ray permissions

### Preprod Auth (14 tests)
- `test_e2e_lambda_invocation_preprod.py`: 14 tests - "Auth format incompatible - API v2 uses X-User-ID header"
- **Intentional**: v1 auth format deprecated, v2 tests exist

---

## 4. Unit Tests - Validator TODO

6 tests in `tests/unit/resource_naming_consistency/` with `@pytest.mark.skip`:

| Test | Reason |
|------|--------|
| `test_all_lambda_names_valid` | Validator not yet implemented |
| `test_all_dynamodb_names_valid` | Validator not yet implemented |
| `test_all_sqs_names_valid` | Validator not yet implemented |
| `test_all_sns_names_valid` | Validator not yet implemented |
| `test_all_resources_covered_by_iam` | Validator not yet implemented |
| `test_no_orphaned_iam_patterns` | Validator not yet implemented |

**Note**: Feature 075 implemented `src/validators/resource_naming.py` with 32 tests.
These 6 may be redundant TODOs from before that implementation.

**Action**: Audit if these are now covered by Feature 075, then either:
- Delete as redundant, OR
- Implement remaining logic

---

## 5. Source TODOs

| File | Line | TODO |
|------|------|------|
| `tests/e2e/test_quota.py` | 304-305 | "Tests require actually sending emails to increment quota - would incur costs" |
| `tests/unit/resource_naming_consistency/test_resource_name_pattern.py` | 84 | "Implement extraction of resource names from Terraform files" |
| `tests/unit/resource_naming_consistency/test_iam_pattern_coverage.py` | 101 | "Implement full extraction and validation logic" |

---

## 6. Deferred Architecture

### Project Name Parameterization (docs/FUTURE_WORK.md)

**Current state**: `*-sentiment-*` hardcoded throughout IAM policies and resource names

**Deferred reason**: `iam_resource_alignment.py` does static text analysis and cannot resolve Terraform variables/locals

**Future work**:
1. Create `local.project_slug = "sentiment"` in main.tf
2. Update all resource names to use `${local.project_slug}`
3. Update validator to resolve Terraform locals (separate feature)

---

## Priority Matrix

### Immediate (Post Feature 077 Deployment)
1. Remove "Config creation 500" skips from ~18 E2E tests
2. Verify tests pass against preprod

### Short-Term (Next Sprint)
3. Audit 6 resource naming unit test skips vs Feature 075 coverage
4. Document remaining TODOs or close them

### Feature Work (Backlog)
5. Implement missing endpoints (notifications, alerts, market status, etc.)
6. Unskip E2E tests as endpoints become available

### Intentionally Deferred
- Project name parameterization (architectural)
- Quota email tests (cost concern)
- Cleanup utility tests (not tests, utilities)

---

## Closed Items (Features 075-077)

| Feature | What Closed | Tests |
|---------|-------------|-------|
| 075 | Resource naming validators, JWT auth | +64 new |
| 076 | v1 API integration tests | -21 removed |
| 077 | Config creation 500 error | ~18 unskippable |

---

## Next Actions

1. **Deploy to preprod** - `make deploy-preprod`
2. **Verify Feature 077 fix** - `curl -X POST .../v2/config -d '{"bad":"data"}'` should return 422
3. **Remove 500 skips** - Update test files, run E2E suite
4. **Audit resource naming TODOs** - Check if Feature 075 covers them
