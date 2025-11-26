# Test Debt Burndown Report

**Generated:** 2025-11-25
**Overall Coverage:** 85.99% (target: 80%)
**Total Tests:** 569 unit tests + integration/e2e suites

## Executive Summary

The test suite meets coverage thresholds but has structural weaknesses that reduce confidence in preprod validation. This document tracks test debt items to be burned down over time.

## Coverage by Module

| Module | Coverage | Risk Level | Notes |
|--------|----------|------------|-------|
| `dashboard/handler.py` | 72% | HIGH | SSE streaming, WebSocket, static file paths untested |
| `analysis/sentiment.py` | 74% | MEDIUM | S3 model loading path untested |
| `dashboard/chaos.py` | 75% | MEDIUM | FIS experiment execution paths |
| `dashboard/api_v2.py` | 86% | LOW | Some edge cases missing |
| `ingestion/handler.py` | 87% | LOW | Error handling paths |
| `shared/secrets.py` | 88% | LOW | Edge cases |
| `ingestion/adapters/newsapi.py` | 87% | LOW | Error paths |
| `shared/dynamodb.py` | 91% | LOW | Good coverage |
| `dashboard/metrics.py` | 92% | LOW | Good coverage |
| `shared/logging_utils.py` | 100% | NONE | Fully covered |
| `shared/errors.py` | 100% | NONE | Fully covered |
| `shared/schemas.py` | 100% | NONE | Fully covered |
| `shared/chaos_injection.py` | 100% | NONE | Fully covered |

## Tests With Skips/Fallbacks

### TD-001: Observability Tests Skip on Missing Metrics
**File:** `tests/integration/test_observability_preprod.py`
**Status:** OPEN
**Lines:** 72, 122, 130, 165, 200, 261, 281

**Problem:** Tests skip when CloudWatch metrics don't exist, hiding the fact that metrics SHOULD exist if the system is running correctly.

**Root Cause:** No guaranteed metric generation during preprod deployment.

**Solution:** See spec `003-preprod-metrics-generation`

---

### TD-002: E2E Lambda Tests Have Empty Placeholders
**File:** `tests/integration/test_e2e_lambda_invocation_preprod.py`
**Status:** OPEN
**Lines:** 373, 556

**Problem:** Tests have `pass` placeholders that do nothing, giving false confidence.

**Root Cause:** Tests were scaffolded but never implemented.

**Solution:** See spec `004-remove-test-placeholders`

---

### TD-003: Ingestion Preprod Tests Have Empty Exception Handlers
**File:** `tests/integration/test_ingestion_preprod.py`
**Status:** OPEN
**Lines:** 328, 405, 480

**Problem:** Exception handlers with `pass` silently swallow failures.

**Root Cause:** Defensive coding that hides real issues.

**Solution:** See spec `004-remove-test-placeholders`

---

### TD-004: No Synthetic Data for E2E Validation
**File:** Multiple preprod test files
**Status:** OPEN

**Problem:** E2E tests depend on real data existing in preprod. If table is empty or stale, tests give false positives.

**Root Cause:** No on-demand test data generation.

**Solution:** See spec `005-synthetic-test-data`

---

### TD-005: Dashboard Handler Low Coverage
**File:** `src/lambdas/dashboard/handler.py`
**Status:** OPEN
**Coverage:** 72%

**Problem:** SSE streaming, WebSocket, and static file error paths are untested.

**Uncovered Lines:**
- 115-129: Static file serving initialization
- 557-628: SSE streaming implementation
- 746-760: WebSocket handling
- 939-953: Error response formatting
- 1079-1093: Request validation edge cases

**Solution:** Add unit tests mocking SSE/WebSocket connections.

---

### TD-006: Sentiment Model S3 Loading Untested
**File:** `src/lambdas/analysis/sentiment.py`
**Status:** OPEN
**Coverage:** 74%

**Problem:** Lines 81-139 (S3 model download and loading) are never executed in unit tests.

**Root Cause:** Unit tests mock the model directly.

**Solution:** Add integration test that loads model from real S3 in preprod.

## Burndown Specifications

| Spec ID | Title | Status | Resolves |
|---------|-------|--------|----------|
| 003-preprod-metrics-generation | Generate Metrics During Preprod Deploy | PLANNED | TD-001 |
| 004-remove-test-placeholders | Remove Empty Test Placeholders | PLANNED | TD-002, TD-003 |
| 005-synthetic-test-data | On-Demand Synthetic Test Data | PLANNED | TD-004 |

## Progress Tracking

### Week of 2025-11-25
- [x] Identified all test debt items
- [x] Created TEST-DEBT.md tracking document
- [x] Created spec placeholders for burndown work
- [ ] TD-001: Implement preprod metrics generation
- [ ] TD-002: Remove test placeholders
- [ ] TD-003: Add synthetic data generation

### Acceptance Criteria for Closing Items

- **TD-001:** Zero `pytest.skip` calls in observability tests
- **TD-002:** Zero `pass` statements in test files (except `__init__.py`)
- **TD-003:** Same as TD-002
- **TD-004:** E2E tests create/verify their own data
- **TD-005:** Dashboard handler coverage >= 85%
- **TD-006:** Sentiment model coverage >= 85%

## Metrics

Track these metrics weekly:

```
Overall Coverage: 85.99%
Skip Count: 7
Pass Placeholder Count: 6
Modules Below 80%: 3 (handler.py, sentiment.py, chaos.py)
```
