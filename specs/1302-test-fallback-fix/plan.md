# Feature 1302: Implementation Plan

## Fix Categories

### Category A: DYNAMODB_TABLE — fail loudly (FR-001)
Replace `get("DYNAMODB_TABLE", "table-name")` with `os.environ["DYNAMODB_TABLE"]`.
- `e2e/conftest.py:662` — inside fixture function (safe to use os.environ[])
- `e2e/helpers/cleanup.py:43` — inside function (safe)
- `integration/test_analysis_preprod.py:96` — inside fixture/function (safe)

### Category B: PREPROD_API_URL — lazy validation (FR-002)
Replace hardcoded URL default with empty string. Guard at usage time, not construction.
- `e2e/helpers/api_client.py:71` — change to `os.environ.get("PREPROD_API_URL", "")`. Add guard in request methods.

### Category C: ENVIRONMENT — fail loudly (FR-004)
Replace `get("ENVIRONMENT", "preprod")` with `os.environ["ENVIRONMENT"]`.
- `e2e/test_observability.py:24` — inside class/function
- `integration/test_observability_preprod.py:39` — inside function

### Category D: API_KEY — fail loudly (FR-005)
Replace `get("API_KEY", "test-api-key-12345")` with `os.environ["API_KEY"]`.
- `integration/test_dashboard_preprod.py:45` — inside fixture

### Category E: SSE_LAMBDA_URL localhost — empty + skip (FR-007)
Replace `get("SSE_LAMBDA_URL", "http://localhost:8000")` with `get("SSE_LAMBDA_URL", "")`.
Add skip guard: `if not url: pytest.skip("SSE_LAMBDA_URL not set")`.
- `e2e/test_client_cache.py:59`
- `e2e/test_sse_reconnection.py:60`
- `e2e/test_sentiment_history_regression.py:36`
- `e2e/test_multi_resolution_dashboard.py:62`

### Category F: AWS_REGION — fail loudly (FR-006)
Replace `os.environ.get("AWS_REGION", "us-east-1")` with `os.environ["AWS_REGION"]` in all 10 locations.
If region isn't configured, the AWS SDK will fail clearly on its own. Test code should not paper over misconfigured environments.

### Category G: KEEP as-is (FR-003)
- `LAMBDA_QUALIFIER` default "live" — this is a code constant (the alias name), not environment config.

## Files Modified

| File | Changes |
|------|---------|
| `tests/e2e/conftest.py` | DYNAMODB_TABLE fail-loud (line 662) |
| `tests/e2e/helpers/cleanup.py` | DYNAMODB_TABLE fail-loud (line 43) |
| `tests/e2e/helpers/api_client.py` | PREPROD_API_URL empty default + guard (line 71) |
| `tests/e2e/test_observability.py` | ENVIRONMENT fail-loud (line 24) |
| `tests/e2e/test_client_cache.py` | SSE_LAMBDA_URL empty + skip (line 59) |
| `tests/e2e/test_sse_reconnection.py` | SSE_LAMBDA_URL empty + skip (line 60) |
| `tests/e2e/test_sentiment_history_regression.py` | SSE_LAMBDA_URL empty + skip (line 36) |
| `tests/e2e/test_multi_resolution_dashboard.py` | SSE_LAMBDA_URL empty + skip (line 62) |
| `tests/integration/test_analysis_preprod.py` | DYNAMODB_TABLE fail-loud (line 96) |
| `tests/integration/test_dashboard_preprod.py` | API_KEY fail-loud (line 45) |
| `tests/integration/test_observability_preprod.py` | ENVIRONMENT fail-loud (line 39) |

## Adversarial Review #2

No drift. Plan matches spec (including AR#1 corrections for lazy validation). Gate: PASS.
