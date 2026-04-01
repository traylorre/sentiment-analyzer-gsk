# Feature 1292: Plan

## Implementation
Per-file rewrite from `requests.get(URL)` → `PreprodAPIClient` async invoke.

### test_canary_preprod.py
- Convert `TestCanaryPreprod` to async, add `api_client` fixture
- Replace `requests.get(f"{url}/health")` → `await api_client.get("/health")`
- Remove header assertions (invoke doesn't return HTTP headers)
- Convert concurrent test from `concurrent.futures.ThreadPoolExecutor` → `asyncio.gather()`
- Keep `TestCanaryMetadata` unchanged (no HTTP calls)

### test_admin_lockdown_preprod.py
- Convert to async with `api_client` fixture
- Replace `requests.get(f"{DASHBOARD_URL}/path")` → `await api_client.get("/path")`
- Replace `requests.post(...)` → `await api_client.post(...)`
- Remove `DASHBOARD_URL` skip condition → use `api_client` (skips if no PREPROD_API_URL)

### test_chaos_lockdown_preprod.py
- Same pattern as admin lockdown
- Replace all `requests.get/post/delete()` → `api_client.get/post/delete()`

## Clarifications
All self-answered. No ambiguities.

## Adversarial Review #2
No drift from AR#1. Gate passes.
