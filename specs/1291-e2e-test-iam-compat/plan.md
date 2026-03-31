# Feature 1291: Implementation Plan

## Files Modified

| File | Change | Risk |
|------|--------|------|
| `.github/workflows/deploy.yml` | Add `PREPROD_API_GATEWAY_URL` env var to test job | LOW |
| `tests/e2e/test_cors_404_e2e.py` | Rewrite to use API Gateway + auth + nonexistent route | MEDIUM |
| `tests/e2e/test_sse.py` | Add skip for streaming tests when PREPROD_TRANSPORT=invoke | LOW |

## Implementation Phases

### Phase 1: Workflow Change
Add `PREPROD_API_GATEWAY_URL` to the preprod integration test environment:
```yaml
PREPROD_API_GATEWAY_URL: ${{ needs.deploy-preprod.outputs.api_url }}
```
The `api_url` output already exists (deploy.yml:1081) but isn't passed to the test job.

### Phase 2: Rewrite CORS 404 Test
Replace raw `httpx.get()` with authenticated requests through API Gateway:
1. Read `PREPROD_API_GATEWAY_URL` env var
2. Generate JWT token using `PREPROD_TEST_JWT_SECRET` (existing pattern from conftest.py)
3. Hit nonexistent route with `Origin` header
4. Assert 404 status + CORS headers present
5. Hit same route with bad origin — assert CORS origin header absent

### Phase 3: Skip SSE Streaming Tests
Add `pytest.mark.skipif` to `test_global_stream_available` and `test_sse_connection_established` when `PREPROD_TRANSPORT == "invoke"`. Use SkipInfo pattern from conftest.py.

## Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| API Gateway URL empty on first deploy | LOW | LOW | Skip test with message |
| JWT token generation fails | LOW | LOW | Skip with remediation message |

## Adversarial Review #2

### Drift Findings
No drift. Clarifications confirmed all assumptions (API Gateway URL exists, stage prefix is v1, {proxy+} catches all paths).

### Gate Statement
**0 CRITICAL, 0 HIGH.** Passes AR#2.
