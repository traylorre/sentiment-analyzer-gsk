# Feature 1292: Tasks

## T-001: Rewrite test_canary_preprod.py
Convert 6 HTTP tests to async PreprodAPIClient. Remove header assertions. Convert concurrent test to asyncio.gather().

## T-002: Rewrite test_admin_lockdown_preprod.py
Convert 8 tests to async PreprodAPIClient. Remove DASHBOARD_URL dependency.

## T-003: Rewrite test_chaos_lockdown_preprod.py
Convert 6 tests to async PreprodAPIClient. Remove DASHBOARD_URL dependency.

## T-004: Run tests locally to verify
`PREPROD_TRANSPORT=invoke pytest tests/integration/test_canary_preprod.py tests/e2e/test_admin_lockdown_preprod.py tests/e2e/test_chaos_lockdown_preprod.py -v`

## Adversarial Review #3
**Highest risk**: T-001 (canary) — concurrent test rewrite + header assertion removal.
**Most likely rework**: Response object differences between LambdaResponse and httpx.Response.
**READY FOR IMPLEMENTATION.**
