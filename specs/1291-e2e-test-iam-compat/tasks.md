# Feature 1291: Implementation Tasks

## Task Summary
- **Total tasks**: 6
- **Files modified**: 3
- **Risk**: LOW

## Tasks

### T-001: Add API Gateway URL to deploy workflow test env
**File**: `.github/workflows/deploy.yml`
**Change**: Add `PREPROD_API_GATEWAY_URL: ${{ needs.deploy-preprod.outputs.api_url }}` to the preprod integration test job environment variables (~line 1507).
**FR**: FR-001

### T-002: Rewrite test_cors_404_e2e.py to use API Gateway
**File**: `tests/e2e/test_cors_404_e2e.py`
**Change**:
1. Replace `PREPROD_API_URL` with `PREPROD_API_GATEWAY_URL`
2. Add JWT token generation (import from conftest pattern)
3. Change target route to a nonexistent path under `{proxy+}` catch-all
4. Send authenticated request with `Origin` header
5. Assert 404 + CORS headers (allow-origin, vary, allow-credentials)
6. Test bad origin still gets 404 but no allow-origin header
**FR**: FR-002

### T-003: Add skip to SSE streaming tests
**File**: `tests/e2e/test_sse.py`
**Change**: Add `@pytest.mark.skipif(os.environ.get("PREPROD_TRANSPORT") == "invoke", reason="SSE HTTP streaming not available with IAM-auth Function URLs in invoke mode")` to `test_global_stream_available` and `test_sse_connection_established`.
**FR**: FR-003

### T-004: Verify remaining SSE tests pass via invoke
**Action**: Run `PREPROD_TRANSPORT=invoke pytest tests/e2e/test_sse.py -v --timeout=30` locally and confirm the non-streaming tests pass.
**FR**: FR-004

### T-005: Run full preprod test suite locally
**Action**: Run `pytest tests/e2e/ -v --timeout=60 -k "preprod"` and verify no new failures.
**SC**: SC-001

### T-006: Push and verify pipeline
**Action**: Commit, push, verify preprod integration tests pass in CI.
**SC**: SC-001, SC-002

## Requirement Coverage

| Requirement | Tasks |
|------------|-------|
| FR-001 | T-001 |
| FR-002 | T-002 |
| FR-003 | T-003 |
| FR-004 | T-004 |
| SC-001 | T-005, T-006 |
| SC-002 | T-006 (verify no auth changes) |
| SC-003 | T-002 (CORS assertions in rewritten test) |

## Adversarial Review #3

### Risk Assessment
**Highest-risk task**: T-002 (rewriting CORS 404 test). The test must generate a valid JWT, send it through API Gateway, and verify Lambda-level CORS headers are preserved. If API Gateway strips or overwrites CORS headers, the test will fail for a new reason.

**Most likely rework**: T-002 if the API Gateway `{proxy+}` route with Cognito auth doesn't pass through Lambda's CORS headers correctly. Mitigation: test locally first.

### Gate Statement
**READY FOR IMPLEMENTATION.** 6 tasks, 3 files, low risk.
