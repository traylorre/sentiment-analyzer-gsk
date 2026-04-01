# Feature 1293: Tasks

## T-001: Add skip decorators to 5 SSE streaming tests
File: `tests/e2e/test_sse_connection_preprod.py`. Add `_SKIP_SSE_HTTP` condition and `@pytest.mark.skipif` to all 5 tests.

## Adversarial Review #3
**Lowest risk feature.** Single file, additive change.
**READY FOR IMPLEMENTATION.**
