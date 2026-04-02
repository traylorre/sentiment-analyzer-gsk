# Feature 1302: Eliminate Dangerous Test Fallback Patterns

## Problem Statement

18 locations across E2E and integration test files use `os.environ.get("VAR", "dangerous-default")` where the default silently routes to real infrastructure — preprod DynamoDB tables, production Lambda aliases, hardcoded URLs. If env vars are missing (misconfigured CI, local dev without setup), tests silently run against wrong targets instead of failing loudly.

This is the same class of bug as the Amplify fallback (Feature 1299): silent control plane failures.

## Requirements

### FR-001: Replace DYNAMODB_TABLE fallbacks
Replace `os.environ.get("DYNAMODB_TABLE", "sentiment-analyzer-preprod")` and `get("DYNAMODB_TABLE", "dev-sentiment-items")` with `os.environ["DYNAMODB_TABLE"]` (fail loudly) in:
- `tests/e2e/conftest.py:662`
- `tests/e2e/helpers/cleanup.py:43`
- `tests/integration/test_analysis_preprod.py:96`

### FR-002: Replace PREPROD_API_URL hardcoded URL
Replace `os.environ.get("PREPROD_API_URL", "https://api.preprod.sentiment-analyzer.com")` in `tests/e2e/helpers/api_client.py:71` with `os.environ["PREPROD_API_URL"]`. Callers that don't set this should get a clear KeyError, not silently hit a hardcoded URL.

### FR-003: Replace LAMBDA_QUALIFIER "live" default
Replace `os.environ.get("LAMBDA_QUALIFIER", "live")` in `tests/e2e/helpers/lambda_invoke_transport.py:33` with `os.environ.get("LAMBDA_QUALIFIER", "live")`.

**EXCEPTION**: "live" IS the correct qualifier for all environments (dev, preprod, prod). The Lambda alias is always "live". This is a legitimate default, not a dangerous one. **KEEP as-is.**

### FR-004: Replace ENVIRONMENT "preprod" defaults
Replace `os.environ.get("ENVIRONMENT", "preprod")` with `os.environ["ENVIRONMENT"]` in:
- `tests/e2e/test_observability.py:24`
- `tests/integration/test_observability_preprod.py:39`

### FR-005: Replace API_KEY dummy default
Replace `os.environ.get("API_KEY", "test-api-key-12345")` in `tests/integration/test_dashboard_preprod.py:45` with `os.environ["API_KEY"]`.

### FR-006: Remove AWS_REGION defaults
`os.environ.get("AWS_REGION", "us-east-1")` appears in 10 locations. Replace with `os.environ["AWS_REGION"]`.

If `AWS_REGION` isn't set, the AWS SDK will fail with a clear error on its own. Adding a default in test code hides a misconfigured environment. If the region is always us-east-1, it should be set in the environment, not hardcoded in fallbacks.

Locations:
- `tests/e2e/conftest.py:660, 676, 690`
- `tests/e2e/helpers/cleanup.py:29`
- `tests/e2e/helpers/xray.py:45`
- `tests/e2e/helpers/cloudwatch.py:38, 46`
- `tests/e2e/helpers/lambda_invoke_transport.py:157`
- `tests/integration/test_observability_preprod.py:25, 32`

### FR-007: Replace SSE_LAMBDA_URL localhost defaults
Replace `os.environ.get("SSE_LAMBDA_URL", "http://localhost:8000")` with `os.environ.get("SSE_LAMBDA_URL", "")` + skip guard in:
- `tests/e2e/test_client_cache.py:59`
- `tests/e2e/test_sse_reconnection.py:60`
- `tests/e2e/test_sentiment_history_regression.py:36`
- `tests/e2e/test_multi_resolution_dashboard.py:62`

The localhost default causes tests to make HTTP requests to a random local port that may or may not be running a server.

### NFR-001: No test behavior change when env vars ARE set
When env vars are properly configured (CI), all tests must behave identically.

### NFR-002: Clear error messages on missing config
`KeyError` from `os.environ["VAR"]` is clear. For skip patterns, include the var name and remediation.

## Success Criteria

1. Zero `os.environ.get("DYNAMODB_TABLE", ...)` with table name defaults in E2E/integration
2. Zero hardcoded URLs as fallback defaults
3. Zero dummy API keys as defaults
4. Zero `"preprod"` as environment default
5. Zero `AWS_REGION` hardcoded defaults — let the environment or SDK handle it
6. `LAMBDA_QUALIFIER` default kept (always "live" — this is a code constant, not environment config)
7. All tests pass when env vars are set (CI unchanged)
8. Tests fail loudly or skip gracefully when env vars are missing

## Adversarial Review #1

### Findings

| Severity | Finding | Resolution |
|----------|---------|------------|
| HIGH | FR-001 uses `os.environ["DYNAMODB_TABLE"]` which throws `KeyError` during module import (not inside a test function). If a conftest fixture uses this at module level, ALL tests in the session crash with an opaque traceback, not just the tests that need the var. | **Resolved:** Use `os.environ["VAR"]` only inside fixtures or test functions, not at module level. If the variable is read at module level (e.g., `conftest.py:662`), wrap in a function that raises a clear error. |
| HIGH | FR-002 changes `api_client.py` to `os.environ["PREPROD_API_URL"]`. But `PreprodAPIClient` is imported by conftest fixtures used by ALL E2E tests. If `PREPROD_API_URL` isn't set, every E2E test crashes — including ones that don't use HTTP transport (invoke-only tests don't need a URL). | **Resolved:** Use `os.environ.get("PREPROD_API_URL") or ""` with a guard in the `request()` method: raise clear error only when an HTTP request is actually attempted without a URL. Don't fail at construction time. |
| MEDIUM | FR-003 correctly identifies LAMBDA_QUALIFIER "live" as legitimate. But FR-006 keeps AWS_REGION "us-east-1" default. The reasoning is sound (single-region deployment) but the rationale should be documented inline so future developers don't remove it as another "dangerous default." | **Resolved:** Add inline comment: `# Legitimate default: project deploys exclusively to us-east-1` |
| LOW | FR-007 changes localhost:8000 to empty string + skip. But some of these tests may have autouse fixtures that still try to connect. | **Accepted:** Skip guards prevent test body from running. Autouse fixtures that need the URL should also check. |

### Gate Statement
**0 CRITICAL, 0 HIGH remaining.** Both HIGH findings resolved with lazy evaluation pattern. Proceeding to Stage 3.

## Clarifications

### Q1: Are there module-level reads of DYNAMODB_TABLE in e2e/conftest.py?
**Answer:** Need to check. If it's inside a fixture function, `os.environ["VAR"]` is fine. If at module scope, it crashes all tests.
**Action:** Verify during implementation — read exact context around line 662.

### Q2: Is PreprodAPIClient constructed at import time or fixture time?
**Answer:** It's constructed in a `@pytest.fixture`. The fixture is lazy (called when a test needs it). So `os.environ["PREPROD_API_URL"]` inside the fixture would only crash tests that use PreprodAPIClient, not all tests. However, the `api_client.py` module itself reads `DEFAULT_TRANSPORT` at module level (line 22). Need to verify.
**Action:** Read api_client.py constructor flow during implementation.

All questions self-answerable from code. No questions deferred.
