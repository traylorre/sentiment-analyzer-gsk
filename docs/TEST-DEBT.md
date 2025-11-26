# Test Debt Burndown Report

**Generated:** 2025-11-25
**Last Updated:** 2025-11-25
**Overall Coverage:** 85.99% (target: 80%)
**Total Tests:** 569 unit tests + integration/e2e suites

## Executive Summary

The test suite meets coverage thresholds but has structural weaknesses that reduce confidence in preprod validation. This document tracks test debt items being burned down.

**Progress:** 3 of 6 items resolved, 1 in progress, 2 remaining.

## Test Debt Status

| ID | Description | Status | PR |
|----|-------------|--------|-----|
| TD-001 | Observability tests skip on missing metrics | IN PROGRESS | [#112](https://github.com/traylorre/sentiment-analyzer-gsk/pull/112) |
| TD-002 | E2E Lambda tests have empty placeholders | **RESOLVED** | [#113](https://github.com/traylorre/sentiment-analyzer-gsk/pull/113) |
| TD-003 | Ingestion preprod tests have empty exception handlers | **RESOLVED** | [#113](https://github.com/traylorre/sentiment-analyzer-gsk/pull/113) |
| TD-004 | No synthetic data for E2E validation | **RESOLVED** | [#114](https://github.com/traylorre/sentiment-analyzer-gsk/pull/114) |
| TD-005 | Dashboard handler low coverage (72%) | OPEN | - |
| TD-006 | Sentiment model S3 loading untested (74%) | OPEN | - |

---

## Resolved Items

### TD-002: E2E Lambda Tests Empty Placeholders ✅
**Resolved:** PR #113 merged 2025-11-25

**What was fixed:**
- `test_malformed_json_handled_gracefully`: Implemented actual test that sends malformed JSON to `/api/chaos/experiments` and verifies 422 response
- `test_benchmark_cold_start_time`: Added proper `pytest.skip()` with explanation that cold start benchmark requires Lambda config update

### TD-003: Ingestion Preprod Empty Exception Handlers ✅
**Resolved:** PR #113 merged 2025-11-25

**What was fixed:**
- 5 exception handlers in `tests/integration/test_ingestion_preprod.py` now log warnings instead of silently swallowing errors
- Added `logging` import and logger instance
- Changed `except Exception: pass` to `except Exception as e: logger.warning("Cleanup failed (best-effort): %s", e)`

### TD-004: No Synthetic Data for E2E Validation ✅
**Resolved:** PR #114 merged 2025-11-25

**What was added:**
- `tests/fixtures/synthetic_data.py`: New `SyntheticDataGenerator` class
  - Creates 6 deterministic items (2 positive, 2 neutral, 2 negative)
  - Items have `TEST_E2E_` prefix for easy identification
  - Automatic cleanup via context manager
- `tests/conftest.py`: New `synthetic_data` session-scoped fixture
  - Auto-skips for unit tests (mocked DynamoDB)
  - Creates test dataset for preprod tests

---

## In Progress

### TD-001: Observability Tests Skip on Missing Metrics
**Status:** IN PROGRESS - PR #112 awaiting merge
**File:** `tests/integration/test_observability_preprod.py`

**Problem:** Tests skip when CloudWatch metrics don't exist, hiding the fact that metrics SHOULD exist if the system is running correctly.

**Solution implemented:**
1. Added "Warm Up Lambdas for Metrics" step to `.github/workflows/deploy.yml`
   - Invokes dashboard Lambda endpoints before integration tests
   - Waits 60s for CloudWatch metrics to propagate
2. Created `tests/integration/test_observability_preprod.py`
   - Tests use assertions (not skips) to fail when metrics missing
   - Validates invocation count, duration metrics, error rates
   - Validates CloudWatch log groups exist

**Acceptance criteria:** Zero `pytest.skip` calls in observability tests

---

## Remaining Items

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

**Acceptance criteria:** Dashboard handler coverage >= 85%

---

### TD-006: Sentiment Model S3 Loading Untested
**File:** `src/lambdas/analysis/sentiment.py`
**Status:** OPEN
**Coverage:** 74%

**Problem:** Lines 81-139 (S3 model download and loading) are never executed in unit tests.

**Root Cause:** Unit tests mock the model directly, never exercising S3 download path.

**Solution:** Add integration test that loads model from real S3 in preprod.

**Acceptance criteria:** Sentiment model coverage >= 85%

---

## Coverage by Module

| Module | Coverage | Risk Level | Notes |
|--------|----------|------------|-------|
| `dashboard/handler.py` | 72% | HIGH | TD-005 |
| `analysis/sentiment.py` | 74% | MEDIUM | TD-006 |
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

## Metrics Summary

```
Overall Coverage: 85.99% (target: 80%) ✅
Test Debt Items: 6 total
  - Resolved: 3 (TD-002, TD-003, TD-004)
  - In Progress: 1 (TD-001)
  - Remaining: 2 (TD-005, TD-006)
Modules Below 80%: 3 (handler.py, sentiment.py, chaos.py)
```
