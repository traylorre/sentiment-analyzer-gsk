# Validation Gap Analysis - Target Repo (sentiment-analyzer-gsk)

**Generated**: 2025-12-09
**Status**: Reference document for closing gaps

## Summary Statistics

| Category | Count | Closeable |
|----------|-------|-----------|
| Skipped Unit Tests (unimplemented validators) | 6 | ✅ Easy |
| ~~Skipped Integration Tests (v1 API deprecated)~~ | 0 | ✅ CLOSED (Feature 076) |
| Skipped E2E Tests (features not implemented) | ~35 | ⚠️ Feature work |
| IAM Allowlist Exemptions | 4 | ⚠️ Architectural |
| Bidirectional Spec Exemptions | 19 | 🚫 Intentional |
| Security Suppressions (nosec/noqa) | 9 | 🚫 Acceptable use |
| Source TODOs | 1 | ✅ Easy |

---

## By Validation Coverage/Effectiveness

### HIGH PRIORITY - Gaps Reducing Coverage

**1. Unimplemented Validators (6 tests skipped)**
```
tests/unit/resource_naming_consistency/test_iam_pattern_coverage.py:
  - test_all_resources_covered_by_iam
  - test_no_orphaned_iam_patterns

tests/unit/resource_naming_consistency/test_resource_name_pattern.py:
  - test_all_lambda_names_valid
  - test_all_dynamodb_names_valid
  - test_all_sqs_names_valid
  - test_all_sns_names_valid
```
**Impact**: No automated validation that Terraform resources match IAM patterns
**Feasibility**: ✅ EASY - Use `/add-validator` command to scaffold

**2. JWT Auth Not Implemented (1 TODO)**
```
src/lambdas/shared/middleware/auth_middleware.py:
  # TODO: Add JWT validation for authenticated sessions
```
**Impact**: Missing authentication validation for authenticated users
**Feasibility**: ✅ EASY - Feature 006 scope

---

### MEDIUM PRIORITY - Partial Coverage

**3. E2E Feature Gaps (~35 conditional skips)**
Most are features not yet implemented:
```
- Notifications endpoint (6 skips)
- Magic link authentication (5 skips)
- Rate limiting recovery (4 skips)
- Token refresh (2 skips)
- Dashboard metrics (2 skips)
- Circuit breaker state (1 skip)
- Config creation (8 skips)
```
**Impact**: No E2E coverage for unimplemented features
**Feasibility**: ⚠️ MEDIUM - Requires feature implementation first

---

### LOW PRIORITY - Acceptable Suppressions

**4. Security Suppressions (9 total, all justified)**
```
✓ nosec B324 (3x) - MD5 for cache keys, not cryptographic
  - src/lambdas/dashboard/sentiment.py:63
  - src/lambdas/shared/adapters/tiingo.py:41
  - src/lambdas/shared/adapters/finnhub.py:44

✓ nosec B108/B202 (3x) - Lambda /tmp storage, AWS standard pattern
  - src/lambdas/analysis/sentiment.py:60,102,118

✓ type: ignore (3x) - Python type system limitations
  - src/lambdas/ingestion/handler.py:540
  - src/lambdas/shared/failure_tracker.py:91
  - src/lambdas/shared/models/ohlc.py:52
```
**Impact**: None - all suppressions are documented and justified
**Feasibility**: 🚫 NOT NEEDED - These are false positives

---

## By Feasibility of Implementation

### ✅ EASY (Can close immediately)

| Gap | Effort | Approach |
|-----|--------|----------|
| 6 unimplemented validators | 2-4 hours | Use `/add-validator` to scaffold |
| 1 JWT TODO | 1-2 hours | Feature 006 auth completion |

### ⚠️ MEDIUM (Requires feature work)

| Gap | Effort | Dependency |
|-----|--------|------------|
| Notifications E2E (6 tests) | Feature work | Implement notification endpoints |
| Magic link auth (5 tests) | Feature work | Implement magic link flow |
| Rate limiting (4 tests) | API work | Rate limit API implementation |
| Token refresh (2 tests) | Auth work | OAuth token refresh |

### 🚫 INTENTIONAL (Should NOT close)

| Gap | Reason |
|-----|--------|
| ~~21 v1 API integration tests~~ | CLOSED (Feature 076) - Tests removed, v2 coverage verified |
| 5 vaporware specs | Frontend specs for backend-only project |
| 10 infrastructure specs | SC-005 exemption - Terraform semantic matching limitation |
| 3 test-infrastructure specs | Test methodology, not production code |
| Pre-existing Lambda code paths | Tagged SPECOVERHAUL:UNDOCUMENTED for future initiative |

### 🔒 ARCHITECTURAL (Require design changes)

| Gap | Why Architectural |
|-----|-------------------|
| 4 IAM allowlist patterns | CI/CD permissions needed for terraform operations |
| src/lambdas/* path exclusion | Retrofitting specs to existing code is major effort |

---

## Recommended Actions

**Immediate (closes 7 gaps):**
1. Run `/add-validator resource-naming` to implement the 6 skipped resource naming tests
2. Implement JWT validation (1 TODO)

**Short-term (as features complete):**
3. Remove E2E skips as endpoints are implemented

**NOT recommended:**
- Don't unskip v1 API tests (deprecated)
- Don't remove nosec/type:ignore (false positives)
- Don't remove IAM exemptions (CI/CD requirements)
- Don't remove bidirectional exemptions (SC-005 limitation)

---

## Progress Tracking

- [X] Feature 075: Resource Naming Validators (6 tests) - **CLOSED** (32 tests implemented, 11 IAM coverage tests)
- [X] Feature 075: JWT Authentication Validation (1 TODO) - **CLOSED** (21 tests, TODO removed)
- [X] Feature 076: v1 API Integration Tests (21 skipped) - **CLOSED** (tests removed, v2 coverage verified)
- [ ] Feature ???: Notifications E2E
- [ ] Feature ???: Magic Link Authentication
- [ ] Feature ???: Rate Limiting
- [ ] Feature ???: Token Refresh

---

## Closed Gaps Summary (Feature 075)

**Date Closed**: 2025-12-09
**Total New Tests**: 64

| Category | Tests Added |
|----------|-------------|
| Resource Naming Validators | 32 |
| IAM Coverage Validators | 11 |
| JWT Authentication | 21 |

**Implementation Files**:
- `src/validators/resource_naming.py` - Terraform resource extraction and naming validation
- `src/validators/iam_coverage.py` - IAM pattern coverage analysis
- `src/lambdas/shared/middleware/auth_middleware.py` - JWT validation (updated)

**Test Files**:
- `tests/unit/validators/test_resource_naming.py`
- `tests/unit/validators/test_iam_coverage.py`
- `tests/unit/middleware/test_jwt_validation.py`

---

## Closed Gaps Summary (Feature 076)

**Date Closed**: 2025-12-10
**Tests Removed**: 21 (v1 API deprecated)
**Tests Preserved**: 3 (version-agnostic)

| Action | Count |
|--------|-------|
| v1 tests audited | 21 |
| v2 equivalents found | 15 |
| Deprecated features | 6 |
| Coverage gaps | 0 |

**Audit Document**: `specs/076-v1-test-deprecation/audit.md`

**Modified Files**:
- `tests/integration/test_dashboard_preprod.py` - 21 skipped tests removed, 3 preserved
