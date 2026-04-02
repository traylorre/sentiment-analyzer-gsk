# Feature 1302: Tasks

## Tasks

### T1: Fix DYNAMODB_TABLE fallbacks (Category A)
**Files:** e2e/conftest.py, helpers/cleanup.py, test_analysis_preprod.py
Replace `get("DYNAMODB_TABLE", "table-name")` → `os.environ["DYNAMODB_TABLE"]`

### T2: Fix PREPROD_API_URL hardcoded URL (Category B)
**File:** helpers/api_client.py
Replace hardcoded URL default → empty string + usage-time guard

### T3: Fix ENVIRONMENT defaults (Category C)
**Files:** test_observability.py, test_observability_preprod.py
Replace `get("ENVIRONMENT", "preprod")` → `os.environ["ENVIRONMENT"]`

### T4: Fix API_KEY dummy default (Category D)
**File:** test_dashboard_preprod.py
Replace `get("API_KEY", "test-api-key-12345")` → `os.environ["API_KEY"]`

### T5: Fix SSE_LAMBDA_URL localhost defaults (Category E)
**Files:** 4 E2E test files
Replace localhost → empty string + skip guard

### T6: Add inline comments on kept defaults (Category F)
**Files:** lambda_invoke_transport.py, all AWS_REGION locations
Add `# Legitimate default: ...` comments

### T7: Verify all tests pass
Run `pytest tests/unit/ tests/integration/ -q`

## Requirements Coverage

| Requirement | Task(s) |
|-------------|---------|
| FR-001 | T1 |
| FR-002 | T2 |
| FR-003 | T6 (keep) |
| FR-004 | T3 |
| FR-005 | T4 |
| FR-006 | T6 (keep) |
| FR-007 | T5 |
| NFR-001 | T7 |
| NFR-002 | T1-T5 |

## Adversarial Review #3

**Highest-risk task:** T2 (api_client.py). Changing default behavior of PreprodAPIClient constructor affects many E2E tests.
**Most likely rework:** T5 — skip guard placement may interfere with autouse fixtures.

### Gate Statement
**READY FOR IMPLEMENTATION.**
