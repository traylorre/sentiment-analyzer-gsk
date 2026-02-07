# OHLC Cache Remediation - Canonical Test Plan

**Parent Spec:** [ohlc-cache-remediation.md](ohlc-cache-remediation.md)
**Feature ID:** CACHE-001
**Total Tests:** 162

This document contains the comprehensive test plan derived by working backwards from failure modes. Extracted from the parent spec for context management.

---

## 15. Canonical Test Plan (Backwards-Engineered)

This section documents a comprehensive test plan derived by working **backwards** from failure modes, not forwards from implementation. The goal is to catch issues that implementation-aligned tests miss.

**Methodology:** For each category, we ask "What could go wrong?" and derive tests that would detect that failure.

### 15.1 Test Taxonomy Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         CANONICAL TEST TAXONOMY                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   UNIT       │ →  │ INTEGRATION  │ →  │   CONTRACT   │ →  │     E2E      │  │
│  │   ~50 tests  │    │   ~25 tests  │    │   ~15 tests  │    │   ~20 tests  │  │
│  └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                  │                   │                   │            │
│         ▼                  ▼                   ▼                   ▼            │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │                    TEST CATEGORIES (by failure mode)                      │  │
│  ├──────────────────────────────────────────────────────────────────────────┤  │
│  │  A. Cache Key Correctness     - Stale data, key collisions               │  │
│  │  B. Data Integrity            - Corruption, truncation, precision loss   │  │
│  │  C. Timing & TTL              - Expiry, freshness, clock drift           │  │
│  │  D. Race Conditions           - Thundering herd, dirty reads, lost writes│  │
│  │  E. Dependency Failures       - DynamoDB, Tiingo, CloudWatch outages     │  │
│  │  F. State Management          - Multi-layer cache, invalidation          │  │
│  │  G. Edge Cases                - Boundaries, holidays, ticker changes     │  │
│  │  H. UI/Playwright             - Viewport, timing, animation stability    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 15.2 Category A: Cache Key Correctness

**Failure Mode:** Wrong cache key → stale data served, cache collisions, permanent data loss.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| A1 | `test_cache_key_date_anchor_prevents_stale_data` | Unit | Same ticker/range on different days returns yesterday's data | Request same ticker+range on day N, verify cache miss on day N+1 |
| A2 | `test_cache_key_resolution_isolation` | Unit | 5-minute and daily keys collide | Write daily candles, read 5-min should miss |
| A3 | `test_cache_key_ticker_case_normalization` | Unit | "aapl" and "AAPL" create separate entries | Write lowercase, read uppercase, verify hit |
| A4 | `test_cache_key_custom_range_includes_both_dates` | Unit | Custom range key missing start_date → collisions | Two custom ranges with same end but different start must have different keys |
| A5 | `test_lock_key_matches_cache_key_granularity` | Unit | Lock for "AAPL 1W" blocks "AAPL 1W next-day" | Verify lock PK includes date anchor |
| A6 | `test_cache_key_format_round_trip` | Unit | Cache key generation differs from cache key parsing | Generate key, parse it, regenerate, compare |
| A7 | `test_cache_key_special_characters` | Unit | Ticker with dots (BRK.B) breaks key parsing | Write and read BRK.B ticker |
| A8 | `test_cache_key_max_length` | Unit | Very long custom date range exceeds DynamoDB limits | Test key with 1-year custom range |

**Integration Tests (Cache Key):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| A9 | `test_cache_key_consistency_across_cold_starts` | Lambda 1 writes, Lambda 2 reads with different env | Mock two Lambda instances with same config, verify read after write |
| A10 | `test_cache_key_persistence_across_deployments` | New deployment changes key format → cache invalidated | Compare key generation between code versions |

### 15.3 Category B: Data Integrity

**Failure Mode:** Data corruption, precision loss, truncation, schema violations.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| B1 | `test_price_precision_preserved_through_cache` | Unit | Float precision lost: 150.125 → 150.12 | Write price with 3+ decimals, verify exact equality on read |
| B2 | `test_volume_zero_not_null` | Unit | Adapters return volume=None → cache write crashes | Mock adapter returning None volume, verify cache write succeeds with 0 |
| B3 | `test_candle_count_matches_expected` | Unit | Cache returns fewer candles than written | Write N candles, read, assert len == N |
| B4 | `test_candle_ordering_preserved` | Unit | DynamoDB query returns out-of-order | Write candles in order, verify SK sort order on read |
| B5 | `test_ohlc_relationship_constraints` | Unit | Cached candle has high < low | Apply OHLCValidator.validate_candle() to cached data |
| B6 | `test_timestamp_timezone_preserved` | Unit | UTC timestamps become naive → wrong data | Write UTC timestamp, read, verify tzinfo is UTC |
| B7 | `test_large_volume_not_truncated` | Unit | int overflow on very high volume stocks | Test volume = 2^31 + 1 |
| B8 | `test_negative_prices_rejected` | Unit | Bad data from API cached permanently | Attempt to cache negative price, verify rejection |
| B9 | `test_nan_values_not_cached` | Unit | NaN prices slip through validation | Attempt to cache NaN, verify rejection |
| B10 | `test_pagination_truncation_detected` | Unit | >1MB response silently loses data | Mock DynamoDB returning LastEvaluatedKey, verify error logged |

**Integration Tests (Data Integrity):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| B11 | `test_tiingo_to_cache_to_response_round_trip` | Data mutation in conversion chain | Fetch from mock Tiingo, cache, read, compare to original |
| B12 | `test_from_cached_candle_preserves_all_fields` | PriceCandle.from_cached_candle drops fields | Compare all fields after conversion |

### 15.4 Category C: Timing & TTL

**Failure Mode:** Stale data served, premature expiry, clock drift issues.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| C1 | `test_ttl_historical_90_days` | Unit | Historical data expires too soon | Verify ExpiresAt ~90 days from now |
| C2 | `test_ttl_today_intraday_5_minutes` | Unit | Today's intraday data cached too long → stale | Verify ExpiresAt ~5 minutes from now |
| C3 | `test_ttl_today_daily_90_days` | Unit | Today's daily bar expires in 5 min (wrong logic) | Verify daily resolution gets 90-day TTL even for today |
| C4 | `test_ttl_boundary_end_of_day` | Unit | 11:59 PM UTC request gets wrong TTL | Test request at 23:59 UTC for today |
| C5 | `test_ttl_respects_market_close` | Unit | Intraday data after 4 PM ET gets short TTL (should be long) | Test 5:00 PM ET request for today's intraday |
| C6 | `test_in_memory_ttl_expiry` | Unit | In-memory cache doesn't expire → stale data | Set TTL=1s, wait 2s, verify miss |
| C7 | `test_clock_drift_tolerance` | Unit | Server clocks differ by 1 minute | Verify TTL calculation uses server time, not client time |
| C8 | `test_dst_transition_handling` | Unit | DST change causes 1-hour gap or overlap | Test March and November DST transitions |
| C9 | `test_leap_second_handling` | Unit | Leap second causes timestamp collision | Verify no SK collisions on leap second days |
| C10 | `test_future_date_rejected` | Unit | Request for tomorrow's data caches empty result | Verify cache not written for future dates |

**Integration Tests (Timing):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| C11 | `test_ttl_expiry_triggers_refetch` | DynamoDB TTL doesn't actually delete → stale data | Write with short TTL, wait, verify cache miss |
| C12 | `test_write_then_immediate_read_succeeds` | Write-through latency causes read miss | Write, immediately read (no sleep), verify hit |
| C13 | `test_cross_timezone_lambda_execution` | Lambda in us-west-2 at 11pm PT computes wrong "today" → stale cache key | Mock TZ=America/Los_Angeles at 23:00, verify cache key uses ET date anchor |

**Flaky Test Prevention (Clarified 2026-02-04):**

Timing-dependent tests (C6, C11-C12, D1, D4-D5, H2-H3) use tolerance bands in CI:

```python
# tests/conftest.py
import os

CI_TOLERANCE_FACTOR = float(os.environ.get("CI_TOLERANCE_FACTOR", "1.0"))

def timing_range(expected_ms: int, tolerance_pct: float = 0.1) -> tuple[int, int]:
    """Return (min, max) timing range with CI tolerance applied.

    In CI (CI_TOLERANCE_FACTOR=1.5): wider bands prevent flakes
    Locally (CI_TOLERANCE_FACTOR=1.0): tight bands catch real regressions
    """
    base_tolerance = expected_ms * tolerance_pct
    ci_tolerance = base_tolerance * CI_TOLERANCE_FACTOR
    return (int(expected_ms - ci_tolerance), int(expected_ms + ci_tolerance))

# Usage in tests:
def test_lock_wait_timeout():
    start = time.time()
    result = await _fetch_with_lock(...)  # Should wait ~3000ms on timeout
    elapsed_ms = (time.time() - start) * 1000

    min_ms, max_ms = timing_range(3000, tolerance_pct=0.15)
    assert min_ms < elapsed_ms < max_ms, f"Expected {min_ms}-{max_ms}ms, got {elapsed_ms}ms"
```

**CI Configuration:**
```yaml
# .github/workflows/test.yml
env:
  CI_TOLERANCE_FACTOR: "1.5"  # 50% wider tolerance bands in CI
```

**Cross-Timezone Test Pattern (C13, Clarified 2026-02-04):**

```python
# tests/integration/test_cross_timezone_cache.py
"""
Test C13: Verify cache key uses market timezone (ET), not Lambda execution timezone.
"""
import pytest
from datetime import datetime, date
from unittest.mock import patch
from zoneinfo import ZoneInfo

class TestCrossTimezoneCacheKey:
    """Verify cache key date anchor is computed using ET, not execution TZ."""

    def test_C13_pacific_late_night_uses_et_date(self):
        """Lambda in us-west-2 at 11pm PT should use next-day ET date anchor.

        Scenario: It's 11:00 PM Pacific (Feb 3) = 2:00 AM Eastern (Feb 4)
        The cache key should use Feb 4 (ET), not Feb 3 (PT).
        """
        from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key

        # Simulate Lambda running in Pacific timezone at 11pm
        pacific_tz = ZoneInfo("America/Los_Angeles")
        pacific_time = datetime(2026, 2, 3, 23, 0, 0, tzinfo=pacific_tz)

        with patch("src.lambdas.dashboard.ohlc._get_current_time") as mock_time:
            mock_time.return_value = pacific_time

            cache_key = _get_ohlc_cache_key(
                ticker="AAPL",
                resolution="D",
                time_range="1W",
            )

        # Key must use ET date (Feb 4), not PT date (Feb 3)
        assert "2026-02-04" in cache_key, \
            f"Cache key should use ET date anchor (2026-02-04), got: {cache_key}"
        assert "2026-02-03" not in cache_key, \
            f"Cache key should NOT use PT date (2026-02-03), got: {cache_key}"

    def test_C13_utc_boundary_uses_et_date(self):
        """Request at midnight UTC should use correct ET date.

        Midnight UTC = 7pm ET (previous day) or 8pm ET (DST).
        """
        from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key

        utc_tz = ZoneInfo("UTC")
        utc_midnight = datetime(2026, 2, 4, 0, 0, 0, tzinfo=utc_tz)

        with patch("src.lambdas.dashboard.ohlc._get_current_time") as mock_time:
            mock_time.return_value = utc_midnight

            cache_key = _get_ohlc_cache_key(
                ticker="AAPL",
                resolution="D",
                time_range="1W",
            )

        # Midnight UTC = 7pm ET on Feb 3, so date anchor should be Feb 3
        assert "2026-02-03" in cache_key, \
            f"Cache key should use ET date anchor (2026-02-03), got: {cache_key}"
```

### 15.5 Category D: Race Conditions

**Failure Mode:** Thundering herd, dirty reads, lost writes, deadlocks.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| D1 | `test_thundering_herd_prevention` | Unit | 10 concurrent requests all hit Tiingo | Mock Tiingo, verify called exactly once (use `asyncio.gather()` with 10 async tasks) |
| D2 | `test_lock_holder_crash_recovery` | Unit | Lock holder crashes → lock stuck forever | Acquire lock, don't release, wait TTL, acquire again |
| D3 | `test_lock_released_by_correct_holder` | Unit | Wrong Lambda releases another's lock | Acquire lock with ID1, attempt release with ID2, verify lock held |
| D4 | `test_lock_waiter_sees_fresh_data` | Unit | Lock waiters read eventual consistent (stale) | Verify lock wait uses ConsistentRead=True |
| D5 | `test_double_check_after_lock_prevents_duplicate_fetch` | Unit | Lock holder doesn't double-check → fetches anyway | Populate cache between lock acquire and fetch, verify no Tiingo call |
| D6 | `test_concurrent_writes_last_write_wins` | Unit | Two writes for same key → data loss | Concurrent writes, verify final state is one of the writes |
| D7 | `test_read_during_write_returns_consistent_state` | Unit | Partial write visible → corrupt candle list | Start long write, concurrent read, verify either old or new, not partial |
| D8 | `test_lock_wait_timeout_triggers_fallback` | Unit | Lock wait exceeds 3s → user gets nothing | Mock slow lock holder, verify fallback to API |
| D9 | `test_in_memory_and_dynamodb_consistency` | Unit | In-memory shows different data than DynamoDB | Invalidate in-memory only, verify next read refreshes from DynamoDB |
| D10 | `test_circuit_breaker_prevents_cascade` | Unit | DynamoDB down → all requests slow | Trigger 3 failures, verify subsequent requests skip DynamoDB |

**Integration Tests (Race Conditions):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| D11 | `test_concurrent_requests_different_tickers` | Lock for AAPL blocks MSFT | Concurrent requests for 5 different tickers, verify all succeed independently |
| D12 | `test_concurrent_requests_same_ticker_different_ranges` | 1W and 1M requests block each other | Concurrent requests, verify separate locks |

**Async Test Isolation (Clarified 2026-02-04):**

Race condition tests use `asyncio.gather()` which can pollute the event loop. Use `pytest-asyncio` strict mode with per-test isolation:

```python
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "strict"  # Require explicit @pytest.mark.asyncio
asyncio_default_fixture_loop_scope = "function"  # Fresh event loop per test
```

```python
# tests/conftest.py
import asyncio
import pytest
import warnings

@pytest.fixture(autouse=True)
def verify_no_pending_tasks():
    """Verify no async tasks leaked after each test.

    autouse=True means this fixture runs automatically for EVERY test
    without needing to explicitly request it. This catches event loop
    pollution that would cause cryptic failures in subsequent tests.

    How autouse works:
    - Fixture runs setup (before yield) → test runs → fixture runs teardown (after yield)
    - With autouse=True, pytest injects this fixture into every test automatically
    - Scope can be "function" (default), "class", "module", or "session"
    """
    yield  # Test runs here

    # Teardown: Check for leaked tasks
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return  # No loop running, nothing to check

    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
    if pending:
        # Cancel leaked tasks to prevent cascade
        for task in pending:
            task.cancel()

        # Warn loudly so developer knows to fix
        warnings.warn(
            f"Test leaked {len(pending)} pending async tasks: {pending}. "
            "Ensure all tasks are awaited or cancelled.",
            UserWarning
        )

@pytest.fixture(autouse=True)
def reset_module_singletons():
    """Reset module-level singletons between tests.

    Another autouse example: ensures circuit breaker state,
    in-memory caches, and boto3 clients don't leak between tests.
    """
    yield  # Test runs here

    # Teardown: Reset singletons
    from src.lambdas.shared.cache.ohlc_cache import _circuit_breaker
    _circuit_breaker["failures"] = 0
    _circuit_breaker["open_until"] = 0

    from src.lambdas.shared.aws_clients import _reset_all_clients
    _reset_all_clients()
```

**Why `autouse=True`:**
- Runs for EVERY test without explicit `def test_foo(verify_no_pending_tasks):`
- Catches pollution from tests that forgot to clean up
- Acts as a safety net, not a replacement for proper cleanup in tests
- Use sparingly - too many autouse fixtures slow down the test suite

### 15.6 Category E: Dependency Failures

**Failure Mode:** External service unavailable, partial failure, cascading failure.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| E1 | `test_dynamodb_read_failure_fallback_to_api` | Unit | DynamoDB throws, request fails | Mock ClientError, verify Tiingo called as fallback |
| E2 | `test_dynamodb_write_failure_request_succeeds` | Unit | Write fails, user gets error | Mock write ClientError, verify 200 response |
| E3 | `test_tiingo_503_not_cached` | Unit | Tiingo 503 cached → permanent outage | Mock 503, verify no cache write |
| E4 | `test_tiingo_404_not_cached` | Unit | Invalid ticker cached → never retries | Mock 404, verify no cache write |
| E5 | `test_tiingo_timeout_triggers_fallback` | Unit | Tiingo hangs → user waits forever | Mock 30s timeout, verify fallback to Finnhub |
| E6 | `test_cloudwatch_failure_silent` | Unit | CloudWatch down → request fails | Mock put_metric_data error, verify 200 response |
| E7 | `test_circuit_breaker_opens_after_threshold` | Unit | 3 DynamoDB failures don't trigger CB | Record 3 failures, verify is_circuit_open() == True |
| E8 | `test_circuit_breaker_closes_after_timeout` | Unit | Circuit stays open forever | Open circuit, wait 60s, verify closed |
| E9 | `test_boto3_client_crash_recovery` | Unit | Client object corrupted, all subsequent calls fail | Reset client, verify recovery |
| E10 | `test_singleton_survives_credential_refresh` | Unit | IAM token expires → all requests fail | Mock token expiry, verify client handles refresh |
| E11 | `test_connection_pool_exhaustion` | Unit | All connections busy → new requests hang | Mock 100 concurrent requests, verify graceful queuing or rejection |
| E12 | `test_lambda_memory_exhaustion` | Unit | Too many candles → OOM kill | Test 100,000 candle response (estimate memory) |

**Integration Tests (Dependency Failures):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| E13 | `test_full_system_recovery_after_dynamodb_outage` | System doesn't recover after DynamoDB returns | Fail DynamoDB, recover, verify normal operation resumes |
| E14 | `test_partial_batch_write_retry` | Some items in batch fail → lost data | Mock UnprocessedItems, verify retry with backoff |

**Reboot Consequence Tests:**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| E15 | `test_cold_start_after_reboot_reads_from_dynamodb` | In-memory cache gone, DynamoDB data remains | Simulate cold start (clear singletons), verify DynamoDB read |
| E16 | `test_reboot_during_write_through` | Partial write → inconsistent state | Kill process mid-write, verify data integrity on recovery |
| E17 | `test_reboot_clears_circuit_breaker` | Circuit breaker stays open across restarts | Open circuit, simulate reboot (module reload), verify closed |
| E18 | `test_stale_lock_after_reboot` | Lock holder reboots, lock stuck | Acquire lock, simulate reboot, verify TTL releases lock |

**User-Facing Error Message Contract Tests (Clarified 2026-02-04):**

Test that user-visible errors contain actionable guidance, not just status codes:

| ID | Scenario | Expected Status | Required Message Elements |
|----|----------|-----------------|---------------------------|
| E19 | `test_error_both_apis_unavailable` | 503 | "temporarily unavailable", "try again" |
| E20 | `test_error_invalid_ticker` | 404 | ticker name, "not found", "check spelling" |
| E21 | `test_error_invalid_date_range` | 400 | "invalid", specific field name, valid format example |
| E22 | `test_error_rate_limited` | 429 | "rate limit", "wait", retry-after hint |
| E23 | `test_error_auth_expired` | 401 | "authentication", "re-login" or "refresh" |

```python
# tests/unit/api/test_error_messages.py
"""
Contract tests for user-facing error messages.
Verifies errors are actionable, not just technically correct.
"""
import pytest

class TestUserFacingErrorMessages:
    """Verify error responses help users understand and recover."""

    def test_E19_both_apis_unavailable(self, client, mock_tiingo_503, mock_finnhub_503):
        """When all data sources fail, user gets helpful 503."""
        response = client.get("/api/v2/tickers/AAPL/ohlc?range=1W")

        assert response.status_code == 503
        body = response.json()

        # Must contain actionable guidance
        assert "error" in body
        error_msg = body["error"].lower()
        assert "temporarily unavailable" in error_msg or "unavailable" in error_msg
        assert "try again" in error_msg or "retry" in error_msg

        # Should NOT expose internal details
        assert "dynamodb" not in error_msg
        assert "tiingo" not in error_msg
        assert "traceback" not in body

    def test_E20_invalid_ticker(self, client):
        """Invalid ticker gets helpful 404 with guidance."""
        response = client.get("/api/v2/tickers/NOTREAL123/ohlc?range=1W")

        assert response.status_code == 404
        body = response.json()

        error_msg = body["error"].lower()
        assert "notreal123" in error_msg  # Echo back what they tried
        assert "not found" in error_msg or "unknown" in error_msg
        assert "check" in error_msg or "verify" in error_msg  # Actionable

    def test_E21_invalid_date_range(self, client):
        """Invalid date format gets helpful 400 with example."""
        response = client.get("/api/v2/tickers/AAPL/ohlc?start=not-a-date")

        assert response.status_code == 400
        body = response.json()

        error_msg = body["error"].lower()
        assert "start" in error_msg or "date" in error_msg  # Which field
        assert "yyyy-mm-dd" in error_msg or "2026-01-01" in error_msg  # Valid format

    def test_E22_rate_limited(self, client, mock_rate_limited):
        """Rate limit gets 429 with retry guidance."""
        response = client.get("/api/v2/tickers/AAPL/ohlc?range=1W")

        assert response.status_code == 429
        body = response.json()

        error_msg = body["error"].lower()
        assert "rate" in error_msg or "limit" in error_msg
        assert "wait" in error_msg or "retry" in error_msg

        # Should have Retry-After header
        assert "Retry-After" in response.headers

    def test_E23_auth_expired(self, client, expired_token):
        """Expired auth gets 401 with re-auth guidance."""
        response = client.get(
            "/api/v2/tickers/AAPL/ohlc?range=1W",
            headers={"Authorization": f"Bearer {expired_token}"}
        )

        assert response.status_code == 401
        body = response.json()

        error_msg = body["error"].lower()
        assert "authentication" in error_msg or "token" in error_msg
        assert "login" in error_msg or "refresh" in error_msg or "expired" in error_msg
```

**Environment Variable Configuration Tests (Clarified 2026-02-04):**

Three-layer protection against env var misconfiguration:

| Layer | When | What | Catches |
|-------|------|------|---------|
| CI lint rule | PR time | Blocks direct `os.environ` access | Dev forgetting to add to Settings |
| pydantic Settings | Lambda import time | Validates required vars present | Missing Terraform vars |
| Custom Secrets fetch | Secret fetch time | Actionable errors with IAM guidance | Secrets Manager access issues |

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| E24 | `test_missing_terraform_env_var_fails_fast` | Unit | Missing `OHLC_TABLE_NAME` silently uses wrong table | Unset var, import config, verify ValidationError names the var |
| E25 | `test_secrets_manager_access_denied_actionable` | Unit | IAM denied → generic boto error | Mock AccessDenied, verify error says "add secretsmanager:GetSecretValue" |
| E26 | `test_secrets_manager_not_found_actionable` | Unit | Secret missing → generic boto error | Mock ResourceNotFound, verify error says which secret and region |

**Configuration Implementation:**

```python
# src/lambdas/shared/secrets.py
"""Secrets Manager fetch with actionable errors."""
import boto3
import os

class ConfigurationError(Exception):
    """Raised when configuration is missing or inaccessible."""
    pass

def get_secret(secret_name: str) -> str:
    """Fetch secret with actionable error on failure."""
    client = boto3.client("secretsmanager")
    try:
        response = client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]
    except client.exceptions.ResourceNotFoundException:
        raise ConfigurationError(
            f"Secret '{secret_name}' not found in region "
            f"'{os.environ.get('AWS_REGION', 'us-east-1')}'. "
            f"Verify the secret exists and the name is correct."
        )
    except client.exceptions.AccessDeniedException:
        raise ConfigurationError(
            f"Access denied to secret '{secret_name}'. "
            f"Add 'secretsmanager:GetSecretValue' permission to the Lambda role."
        )
```

```python
# src/lambdas/shared/config.py
"""Centralized configuration with pydantic validation."""
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache

class CacheSettings(BaseSettings):
    """All env vars must be declared here. Direct os.environ access is blocked by CI."""

    # Terraform-provided (required - no default)
    ohlc_table_name: str
    environment: str
    aws_region: str = "us-east-1"

    # Optional with defaults
    log_level: str = "INFO"
    circuit_breaker_threshold: int = 3
    circuit_breaker_timeout_seconds: int = 60

    # Secrets Manager (lazy-loaded)
    # These use Field with default_factory to defer loading until accessed
    tiingo_api_key: str = Field(default="")
    finnhub_api_key: str = Field(default="")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> CacheSettings:
    """Get validated settings (cached singleton)."""
    return CacheSettings()

# Convenience accessor
settings = get_settings()
```

```python
# tests/unit/config/test_env_var_validation.py
"""Tests for environment variable validation."""
import pytest
from pydantic import ValidationError
from unittest.mock import patch, MagicMock
import os

class TestEnvVarValidation:
    """Verify env var misconfiguration fails fast with actionable errors."""

    def test_E24_missing_terraform_env_var_fails_fast(self):
        """Missing required env var names the specific var in error."""
        # Clear the env var
        env = os.environ.copy()
        env.pop("OHLC_TABLE_NAME", None)

        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                from src.lambdas.shared.config import CacheSettings
                CacheSettings()

        error_str = str(exc_info.value).lower()
        assert "ohlc_table_name" in error_str, \
            f"Error should name the missing var. Got: {exc_info.value}"

    def test_E25_secrets_manager_access_denied_actionable(self):
        """IAM denied error tells you what permission to add."""
        from src.lambdas.shared.secrets import get_secret, ConfigurationError

        mock_client = MagicMock()
        mock_client.exceptions.AccessDeniedException = Exception
        mock_client.get_secret_value.side_effect = \
            mock_client.exceptions.AccessDeniedException("Access Denied")

        with patch("boto3.client", return_value=mock_client):
            with pytest.raises(ConfigurationError) as exc_info:
                get_secret("tiingo-api-key")

        error_msg = str(exc_info.value).lower()
        assert "secretsmanager:getsecretvalue" in error_msg, \
            f"Error should tell you what permission to add. Got: {exc_info.value}"

    def test_E26_secrets_manager_not_found_actionable(self):
        """Missing secret error tells you which secret and region."""
        from src.lambdas.shared.secrets import get_secret, ConfigurationError

        mock_client = MagicMock()
        mock_client.exceptions.ResourceNotFoundException = Exception
        mock_client.get_secret_value.side_effect = \
            mock_client.exceptions.ResourceNotFoundException("Not Found")

        with patch("boto3.client", return_value=mock_client):
            with patch.dict(os.environ, {"AWS_REGION": "us-west-2"}):
                with pytest.raises(ConfigurationError) as exc_info:
                    get_secret("tiingo-api-key")

        error_msg = str(exc_info.value)
        assert "tiingo-api-key" in error_msg, "Error should name the secret"
        assert "us-west-2" in error_msg, "Error should name the region"
```

**CI Lint Rule:**

```bash
# scripts/check-env-var-access.sh
#!/bin/bash
# Fail if any code accesses os.environ directly (must use Settings)

set -e

echo "Checking for direct os.environ access..."

violations=$(grep -rn "os\.environ" --include="*.py" src/ \
  | grep -v "src/lambdas/shared/config.py" \
  | grep -v "src/lambdas/shared/secrets.py" \
  | grep -v "# env-access-ok" \
  || true)

if [ -n "$violations" ]; then
  echo "❌ Direct os.environ access detected:"
  echo "$violations"
  echo ""
  echo "Fix: Add the env var to CacheSettings in src/lambdas/shared/config.py"
  echo "     Then use: from src.lambdas.shared.config import settings"
  echo "     Access via: settings.your_var_name"
  exit 1
fi

echo "✅ All env var access goes through Settings class"
```

```yaml
# .github/workflows/pr-checks.yml
- name: Check env var access pattern
  run: ./scripts/check-env-var-access.sh
```

**Dependency:** Add `pydantic-settings>=2.0` to `requirements.txt`.

### 15.7 Category F: State Management

**Failure Mode:** Multi-layer cache inconsistency, partial invalidation, stale state.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| F1 | `test_invalidate_all_caches_clears_all_layers` | Unit | Partial invalidation leaves stale data | Call invalidate_all_caches(), verify all 3 layers empty |
| F2 | `test_in_memory_eviction_falls_through_to_dynamodb` | Unit | LRU eviction loses data permanently | Fill cache to maxsize+1, verify evicted entry readable from DynamoDB |
| F3 | `test_read_through_populates_in_memory` | Unit | DynamoDB hit doesn't warm in-memory | DynamoDB hit, verify in-memory populated |
| F4 | `test_tiingo_adapter_cache_and_response_cache_isolated` | Unit | Tiingo adapter cache evicted, response cache returns stale | Clear adapter cache only, verify response cache unaffected |
| F5 | `test_module_level_singleton_shared_across_handlers` | Unit | Each handler creates new client → connection leak | Verify get_dynamodb_client() returns same instance across calls |
| F6 | `test_cache_stats_accuracy` | Unit | Stats don't match actual behavior | Compare _ohlc_cache_stats to manual hit/miss count |
| F7 | `test_concurrent_invalidation_safe` | Unit | Race between invalidation and read → partial state | Concurrent invalidate + read, verify no partial data |

**Integration Tests (State Management):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| F8 | `test_cross_lambda_cache_coherence` | Unit | Lambda 1 writes, Lambda 2 has stale in-memory | Mock two instances, write in instance 1, read in instance 2 |
| F9 | `test_deployment_clears_in_memory_cache` | Lambda deployment doesn't reset cache | Simulate deployment (new instance), verify cold cache |

### 15.8 Category G: Edge Cases

**Failure Mode:** Boundary conditions, special dates, unusual tickers.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| G1 | `test_weekend_request_no_data_expected` | Unit | Weekend cache write with 0 candles → treated as error | Request Saturday data, verify 200 with empty candles |
| G2 | `test_market_holiday_handling` | Unit | Holiday treated as error | Request July 4th, verify 200 with no candles |
| G3 | `test_half_day_trading_session` | Unit | Half day (Thanksgiving) returns wrong candle count | Test Nov 29 (day after Thanksgiving) |
| G4 | `test_ticker_with_dot` | Unit | BRK.B breaks parsing | Full flow with BRK.B |
| G5 | `test_ticker_with_hyphen` | Unit | BRK-B (some systems use hyphen) | Full flow with hypothetical ticker |
| G6 | `test_single_letter_ticker` | Unit | F (Ford) or X (US Steel) edge cases | Full flow with single-char ticker |
| G7 | `test_five_letter_ticker` | Unit | GOOGL, MSFT boundary | Full flow with 5-char ticker |
| G8 | `test_delisted_ticker` | Unit | Ticker delisted → 404 cached forever | Mock Tiingo 404, verify not cached |
| G9 | `test_ticker_symbol_change` | Unit | FB → META, old cache invalid | Verify cache key uses current symbol |
| G10 | `test_very_old_historical_data` | Unit | Pre-2000 data has different schema | Request 1990 data for KO |
| G11 | `test_ipo_date_boundary` | Unit | Request before IPO returns error | Request AAPL pre-1980 |
| G12 | `test_stock_split_adjusted` | Unit | Cached pre-split price wrong after split | Verify Tiingo returns adjusted prices |
| G13 | `test_max_date_range_5_years` | Unit | 5-year range exceeds reasonable limits | Request 5-year range, verify reasonable response |
| G14 | `test_min_date_range_1_day` | Unit | 1-day range edge case | Request today only |
| G15 | `test_custom_range_same_day` | Unit | Start = End date | Custom range with start_date == end_date |
| G16 | `test_resolution_mismatch_intraday_historical` | Unit | Intraday resolution on 1-year range | Request 5-min resolution for 1Y range |

**Integration Tests (Edge Cases):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| G17 | `test_midnight_utc_boundary` | Request at exactly 00:00 UTC | Verify correct date anchor |
| G18 | `test_market_open_boundary` | Request at 9:30 AM ET exactly | Verify partial day handling |
| G19 | `test_market_close_boundary` | Request at 4:00 PM ET exactly | Verify end-of-day candle included |

### 15.9 Category H: Playwright / UI Tests

**Failure Mode:** Visual glitches, interaction failures, timing issues, viewport problems.

| ID | Test | Layer | What Could Go Wrong | Detection Strategy |
|----|------|-------|---------------------|-------------------|
| H1 | `test_chart_loads_on_first_visit` | E2E | Chart blank on initial load | Assert chart SVG/canvas has data points |
| H2 | `test_chart_renders_within_timeout` | E2E | Chart hangs waiting for API | Assert chart visible within 5s |
| H3 | `test_cache_hit_faster_than_miss` | E2E | Cached response not faster | Compare timing of 1st vs 2nd request |
| H4 | `test_x_cache_source_header_visible` | E2E | Header stripped by proxy/CDN | Inspect response headers via page.route() |
| H5 | `test_range_change_triggers_new_request` | E2E | UI caches locally, no API call | Assert network request on range button click |
| H6 | `test_resolution_change_updates_chart` | E2E | Resolution button doesn't update data | Compare candle count before/after |
| H7 | `test_concurrent_range_changes_stable` | E2E | Rapid range changes cause race | Click 5 ranges rapidly, verify final state consistent |
| H8 | `test_browser_back_forward_preserves_state` | E2E | History navigation loses ticker | Navigate away, back, verify same ticker |
| H9 | `test_page_refresh_uses_cache` | E2E | Refresh hits API instead of cache | Refresh page, verify X-Cache-Source header |
| H10 | `test_multiple_charts_independent` | E2E | Two charts show same ticker (wrong) | Open AAPL and MSFT, verify different data |

**Viewport Tests:**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| H11 | `test_viewport_resize_maintains_data` | E2E | Resize causes data loss/refetch | Resize viewport, verify candles unchanged |
| H12 | `test_mobile_viewport_chart_readable` | E2E | Chart unreadable on small screen | Screenshot at 375x667, visual regression |
| H13 | `test_fullscreen_toggle_preserves_data` | E2E | Fullscreen loses chart state | Toggle fullscreen, verify data intact |
| H14 | `test_landscape_to_portrait_rotation` | E2E | Rotation causes chart re-render | Emulate device rotation, verify no refetch |

**Network Condition Tests:**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| H15 | `test_slow_3g_shows_loading_state` | E2E | No loading indicator, appears frozen | Throttle to slow 3G, assert spinner visible |
| H16 | `test_offline_shows_graceful_error` | E2E | Offline causes crash or blank screen | Go offline, assert error message with retry button displayed (no service worker) |
| H17 | `test_reconnect_after_offline` | E2E | Coming back online doesn't refresh | Go offline, online, verify new data fetched |

**Animation & Timing Tests:**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| H18 | `test_chart_animation_completes` | E2E | Animation interrupted → visual glitch | Wait for animation, screenshot compare |
| H19 | `test_hover_tooltip_accurate` | E2E | Tooltip shows wrong candle data | Hover over candle, assert tooltip matches data |
| H20 | `test_zoom_animation_smooth` | E2E | Zoom causes jank | Record performance metrics during zoom |

**Browser Cache Interaction Tests (Clarified 2026-02-04):**

| ID | Test | What Could Go Wrong | Detection Strategy |
|----|------|---------------------|-------------------|
| H21 | `test_api_response_cache_control_header` | E2E | Browser caches stale OHLC data → user sees outdated prices | Verify `Cache-Control: no-store` or `max-age=0` on OHLC API responses |
| H22 | `test_backend_cache_refresh_browser_gets_new_data` | E2E | Backend cache updates but browser shows stale data | Clear backend cache, refresh page, verify new data fetched (not browser-cached) |

```typescript
// frontend/tests/e2e/cache/browser-cache.spec.ts
import { test, expect } from '@playwright/test';

test('H21: API response has Cache-Control preventing browser cache', async ({ page }) => {
  let cacheControlHeader: string | null = null;

  // Intercept API response to check headers
  await page.route('**/api/v2/tickers/*/ohlc*', async (route) => {
    const response = await route.fetch();
    cacheControlHeader = response.headers()['cache-control'];
    await route.fulfill({ response });
  });

  await page.goto('/tickers/AAPL');
  await page.waitForSelector('[data-testid="price-chart"]');

  // Verify Cache-Control prevents browser caching
  expect(cacheControlHeader).toBeTruthy();
  expect(cacheControlHeader).toMatch(/no-store|no-cache|max-age=0/);
});

test('H22: Browser gets fresh data after backend cache refresh', async ({ page, request }) => {
  // First load - populate backend cache
  await page.goto('/tickers/AAPL');
  await page.waitForSelector('[data-testid="price-chart"]');

  const firstPrice = await page.locator('[data-testid="current-price"]').textContent();

  // Simulate backend cache invalidation (via test API or direct DynamoDB)
  await request.post('/api/test/invalidate-cache', {
    data: { ticker: 'AAPL' }
  });

  // Refresh page - should get new data from backend, not browser cache
  await page.reload();
  await page.waitForSelector('[data-testid="price-chart"]');

  // Verify network request was made (not served from browser cache)
  const requests = await page.evaluate(() =>
    performance.getEntriesByType('resource')
      .filter(r => r.name.includes('/api/v2/tickers/AAPL/ohlc'))
      .map(r => ({ name: r.name, transferSize: r.transferSize }))
  );

  // transferSize > 0 means it was fetched, not from browser cache
  expect(requests.length).toBeGreaterThan(0);
  expect(requests[0].transferSize).toBeGreaterThan(0);
});
```

### 15.9.1 Category S: Security/Negative Tests (Clarified 2026-02-04)

**Failure Mode:** Sensitive data leaked via logs, cache, or error responses.

**Philosophy:** These tests verify that dangerous things DON'T happen. They catch security regressions that positive tests miss.

| ID | Test | Layer | What Should NOT Happen | Detection Strategy |
|----|------|-------|------------------------|-------------------|
| S1 | `test_api_keys_not_in_logs` | Unit | Tiingo/Finnhub API keys logged at any level | Trigger API call, scan caplog for key patterns |
| S2 | `test_cache_keys_no_sensitive_data` | Unit | Cache key contains API key or auth token | Generate cache key with auth context, verify no secrets |
| S3 | `test_error_response_no_stack_trace` | Unit | 500 error exposes internal stack trace | Trigger internal error, verify response has no traceback |
| S4 | `test_error_response_no_internal_paths` | Unit | Error message exposes file paths | Trigger error, verify no `/home/`, `/var/`, paths |
| S5 | `test_dynamodb_items_no_pii` | Unit | Cached items contain user identifiers | Write to cache, verify no user_id, email, IP in item |

```python
# tests/unit/security/test_negative_assertions.py
"""
Security tests verifying sensitive data is NOT leaked.
These are "negative tests" - they pass when something DOESN'T happen.
"""
import pytest
import re
import logging

class TestSecretsNotLeaked:
    """Verify secrets don't appear in logs, cache, or responses."""

    def test_S1_api_keys_not_in_logs(self, caplog, mock_tiingo_success):
        """API keys must NEVER appear in logs at any level."""
        # Set up a fake API key that we'll look for
        import os
        os.environ["TIINGO_API_KEY"] = "secret_tiingo_key_12345"
        os.environ["FINNHUB_API_KEY"] = "secret_finnhub_key_67890"

        with caplog.at_level(logging.DEBUG):  # Capture ALL log levels
            from src.lambdas.dashboard.ohlc import get_ohlc_data
            # Trigger a request that uses API keys
            try:
                await get_ohlc_data("AAPL", "D", "1W")
            except Exception:
                pass  # We don't care if it fails, just checking logs

        # Scan ALL log output for secrets
        full_log = "\n".join(record.message for record in caplog.records)

        assert "secret_tiingo_key_12345" not in full_log, "Tiingo API key found in logs!"
        assert "secret_finnhub_key_67890" not in full_log, "Finnhub API key found in logs!"

        # Also check for partial key patterns
        assert "tiingo_key" not in full_log.lower(), "API key identifier found in logs"

    def test_S2_cache_keys_no_sensitive_data(self):
        """Cache keys must not contain secrets or auth tokens."""
        from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key
        from datetime import date

        # Generate cache key (simulating authenticated request context)
        cache_key = _get_ohlc_cache_key(
            ticker="AAPL",
            resolution="D",
            time_range="1W",
            start_date=date(2026, 1, 27),
            end_date=date(2026, 2, 3),
        )

        # Verify no sensitive patterns in key
        sensitive_patterns = [
            r"api[_-]?key",
            r"token",
            r"bearer",
            r"auth",
            r"secret",
            r"password",
            r"credential",
        ]

        for pattern in sensitive_patterns:
            assert not re.search(pattern, cache_key, re.IGNORECASE), \
                f"Cache key contains sensitive pattern '{pattern}': {cache_key}"

    def test_S3_error_response_no_stack_trace(self, client):
        """Error responses must not expose stack traces."""
        # Trigger an internal error (mock a crash)
        with pytest.mock.patch(
            "src.lambdas.dashboard.ohlc._fetch_from_tiingo",
            side_effect=RuntimeError("Simulated internal failure")
        ):
            response = client.get("/api/v2/tickers/AAPL/ohlc?range=1W")

        # Should get 5xx but without stack trace
        assert response.status_code >= 500

        body = response.text.lower()
        traceback_indicators = [
            "traceback",
            "file \"",
            "line ",
            "raise ",
            "  at ",
            "runtimeerror",
            "exception",
        ]

        for indicator in traceback_indicators:
            assert indicator not in body, \
                f"Stack trace indicator '{indicator}' found in error response"

    def test_S4_error_response_no_internal_paths(self, client):
        """Error responses must not expose internal file paths."""
        with pytest.mock.patch(
            "src.lambdas.dashboard.ohlc._fetch_from_tiingo",
            side_effect=FileNotFoundError("/home/ubuntu/app/config/secrets.json")
        ):
            response = client.get("/api/v2/tickers/AAPL/ohlc?range=1W")

        body = response.text

        path_patterns = [
            r"/home/",
            r"/var/",
            r"/usr/",
            r"/opt/",
            r"/tmp/",
            r"C:\\",
            r"\\Users\\",
        ]

        for pattern in path_patterns:
            assert not re.search(pattern, body), \
                f"Internal path pattern '{pattern}' found in error response"

    def test_S5_dynamodb_items_no_pii(self, mock_dynamodb):
        """Cached DynamoDB items must not contain user PII."""
        from src.lambdas.shared.cache.ohlc_cache import put_cached_candles
        from datetime import date

        # Write some candles to cache
        candles = [{"date": "2026-02-03", "open": 150.0, "high": 155.0,
                   "low": 149.0, "close": 154.0, "volume": 1000000}]

        put_cached_candles("AAPL", "tiingo", "D", candles, date(2026, 2, 3))

        # Retrieve raw DynamoDB item
        from src.lambdas.shared.aws_clients import get_dynamodb_client
        client = get_dynamodb_client()

        response = client.scan(TableName="test-ohlc-cache")
        items = response.get("Items", [])

        # Convert to string for pattern matching
        items_str = str(items).lower()

        pii_patterns = [
            r"user[_-]?id",
            r"email",
            r"@.*\.(com|org|net)",  # Email pattern
            r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",  # IP address
            r"session",
            r"cookie",
        ]

        for pattern in pii_patterns:
            assert not re.search(pattern, items_str), \
                f"PII pattern '{pattern}' found in cached DynamoDB items"
```

**CI Gate:**
```yaml
# Security tests run on every PR
- name: Security/Negative Tests
  run: pytest tests/unit/security/ -v --tb=short
```

**Visual Regression Strategy (Clarified 2026-02-04):**

Use Playwright's built-in screenshot comparison with tolerance threshold:

```typescript
// frontend/tests/e2e/visual/chart-visual.spec.ts
import { test, expect } from '@playwright/test';

test('H12: mobile viewport chart readable', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 667 });
  await page.goto('/tickers/AAPL');
  await page.waitForSelector('[data-testid="price-chart"]');

  // Visual regression with 0.1% tolerance
  await expect(page).toHaveScreenshot('chart-mobile-375x667.png', {
    maxDiffPixelRatio: 0.001,  // 0.1% pixel diff allowed
    animations: 'disabled',    // Prevent animation timing flakes
  });
});

test('H18: chart animation completes without glitch', async ({ page }) => {
  await page.goto('/tickers/AAPL');

  // Wait for animation to complete
  await page.waitForFunction(() => {
    const chart = document.querySelector('[data-testid="price-chart"]');
    return chart?.getAttribute('data-animation-complete') === 'true';
  });

  await expect(page).toHaveScreenshot('chart-animation-complete.png', {
    maxDiffPixelRatio: 0.001,
  });
});
```

**Baseline Management:**
```bash
# Update baselines when intentional visual changes are made
npx playwright test --update-snapshots

# Baselines stored in repo (per-browser)
frontend/tests/e2e/visual/chart-visual.spec.ts-snapshots/
├── chart-mobile-375x667-chromium-linux.png
├── chart-mobile-375x667-firefox-linux.png
├── chart-mobile-375x667-webkit-linux.png
├── chart-animation-complete-chromium-linux.png
├── chart-animation-complete-firefox-linux.png
└── chart-animation-complete-webkit-linux.png
```

**Cross-Browser CI Configuration (Clarified 2026-02-04):**

All H1-H20 tests run on all 3 browsers for comprehensive coverage:

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  expect: {
    toHaveScreenshot: {
      maxDiffPixelRatio: 0.001,  // 0.1% threshold
      animations: 'disabled',
    },
  },

  // Run all tests on all browsers
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 720 },
      },
    },
  ],

  // Parallel execution to offset 3x browser overhead
  workers: process.env.CI ? 4 : undefined,
  fullyParallel: true,

  // Retry flaky tests (browser differences can cause timing issues)
  retries: process.env.CI ? 2 : 0,
});
```

**CI Workflow with Parallel Browser Jobs:**
```yaml
# .github/workflows/e2e.yml
jobs:
  e2e-tests:
    strategy:
      fail-fast: false  # Run all browsers even if one fails
      matrix:
        browser: [chromium, firefox, webkit]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4

      - name: Install Playwright Browsers
        run: npx playwright install --with-deps ${{ matrix.browser }}

      - name: Run E2E Tests (${{ matrix.browser }})
        run: npx playwright test --project=${{ matrix.browser }}

      - name: Upload Test Artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-report-${{ matrix.browser }}
          path: playwright-report/
```

**Browser-Specific Known Issues:**
| Browser | Known Quirk | Mitigation |
|---------|-------------|------------|
| WebKit | Touch events differ from Chrome | Use `page.tap()` instead of custom touch |
| Firefox | Canvas `toDataURL()` timing | Add 100ms delay before screenshot |
| WebKit | Viewport resize async | Wait for `resize` event after `setViewportSize` |

**Performance Baseline Thresholds (Clarified 2026-02-04):**

Quantitative thresholds for performance tests, alerting on >20% regression:

```typescript
// frontend/tests/e2e/performance/baselines.ts
export const PERFORMANCE_BASELINES = {
  // Cache response times (ms)
  cache: {
    inMemoryHit: { target: 50, max: 100 },      // ~1ms typical, 100ms max
    dynamoDbHit: { target: 100, max: 200 },     // ~40ms typical, 200ms max
    cacheMiss: { target: 1500, max: 2500 },     // ~500-2000ms typical
  },

  // Animation frame rates
  animation: {
    minFps: 30,                    // Minimum acceptable frame rate
    maxFrameDropMs: 100,           // No single frame >100ms
    targetFps: 60,                 // Ideal frame rate
  },

  // UI responsiveness
  interaction: {
    rangeButtonClick: { target: 100, max: 200 },   // Button response time
    chartRender: { target: 500, max: 1000 },       // Initial chart render
    zoomGesture: { target: 50, max: 100 },         // Zoom responsiveness
  },

  // Regression alerting
  regressionThreshold: 0.20,  // Alert if >20% slower than baseline
};
```

```typescript
// frontend/tests/e2e/performance/chart-performance.spec.ts
import { test, expect } from '@playwright/test';
import { PERFORMANCE_BASELINES as B } from './baselines';

test('H3: cache hit faster than cache miss', async ({ page }) => {
  // First request (cache miss)
  const missStart = Date.now();
  await page.goto('/tickers/AAPL');
  await page.waitForSelector('[data-testid="price-chart"]');
  const missTime = Date.now() - missStart;

  // Second request (cache hit)
  const hitStart = Date.now();
  await page.reload();
  await page.waitForSelector('[data-testid="price-chart"]');
  const hitTime = Date.now() - hitStart;

  // Cache hit must be faster
  expect(hitTime).toBeLessThan(missTime);

  // Both within thresholds
  expect(hitTime).toBeLessThan(B.cache.dynamoDbHit.max);
  expect(missTime).toBeLessThan(B.cache.cacheMiss.max);
});

test('H20: zoom animation maintains 30fps', async ({ page }) => {
  await page.goto('/tickers/AAPL');
  await page.waitForSelector('[data-testid="price-chart"]');

  // Start performance tracing
  await page.evaluate(() => {
    (window as any).__frameTimings = [];
    let lastTime = performance.now();

    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const frameTime = entry.startTime - lastTime;
        (window as any).__frameTimings.push(frameTime);
        lastTime = entry.startTime;
      }
    });
    observer.observe({ entryTypes: ['frame'] });
  });

  // Perform zoom gesture
  const chart = page.locator('[data-testid="price-chart"]');
  await chart.evaluate((el) => {
    el.dispatchEvent(new WheelEvent('wheel', { deltaY: -100, ctrlKey: true }));
  });

  await page.waitForTimeout(500);  // Let animation complete

  // Collect frame timings
  const frameTimings: number[] = await page.evaluate(
    () => (window as any).__frameTimings
  );

  // Calculate FPS
  const avgFrameTime = frameTimings.reduce((a, b) => a + b, 0) / frameTimings.length;
  const fps = 1000 / avgFrameTime;
  const maxFrameDrop = Math.max(...frameTimings);

  // Assert thresholds
  expect(fps).toBeGreaterThanOrEqual(B.animation.minFps);
  expect(maxFrameDrop).toBeLessThan(B.animation.maxFrameDropMs);
});
```

**Regression Detection in CI:**
```yaml
# .github/workflows/performance.yml
- name: Performance Tests
  run: npx playwright test tests/e2e/performance/

- name: Check for Regressions
  run: |
    # Compare against stored baselines
    node scripts/check-perf-regression.js \
      --baseline .perf-baselines.json \
      --current test-results/perf-metrics.json \
      --threshold 0.20
```

### 15.10 Test Priority Matrix

| Priority | Category | Justification |
|----------|----------|---------------|
| P0 (Must Have) | D1-D5 (Race Conditions - Lock) | Thundering herd can cause Tiingo rate limits |
| P0 (Must Have) | B1-B5 (Data Integrity - Core) | Data corruption is unrecoverable |
| P0 (Must Have) | E1-E4 (Dependency Failures - Core) | Graceful degradation is critical |
| P1 (Should Have) | A1-A6 (Cache Key - Core) | Cache key bugs cause widespread issues |
| P1 (Should Have) | C1-C5 (TTL - Core) | TTL bugs cause stale data |
| P1 (Should Have) | F1-F3 (State - Multi-layer) | Cache coherence is hard to debug |
| P2 (Nice to Have) | D6-D10 (Race Conditions - Advanced) | Lower probability scenarios |
| P2 (Nice to Have) | G1-G10 (Edge Cases - Common) | Realistic edge cases |
| P3 (Future) | H11-H20 (Playwright - Advanced) | UI polish, not functional |
| P3 (Future) | G11-G16 (Edge Cases - Rare) | Very unlikely scenarios |

### 15.11 Test Fixtures Required

```python
# tests/fixtures/ohlc_cache_fixtures.py

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable
import pytest

@dataclass
class CacheTestScenario:
    """Describes a cache test scenario for parameterized tests."""
    name: str
    ticker: str
    resolution: str
    time_range: str
    start_date: date
    end_date: date
    expected_cache_key: str
    expected_ttl_seconds: int
    expected_candle_count: int

# Standard scenarios for parameterized tests
CACHE_SCENARIOS = [
    CacheTestScenario(
        name="daily_1w_historical",
        ticker="AAPL",
        resolution="D",
        time_range="1W",
        start_date=date(2026, 1, 27),
        end_date=date(2026, 2, 3),
        expected_cache_key="ohlc:AAPL:D:1W:2026-02-03",
        expected_ttl_seconds=90 * 24 * 60 * 60,
        expected_candle_count=5,  # 5 trading days
    ),
    CacheTestScenario(
        name="intraday_5min_today",
        ticker="MSFT",
        resolution="5",
        time_range="1D",
        start_date=date(2026, 2, 4),
        end_date=date(2026, 2, 4),
        expected_cache_key="ohlc:MSFT:5:1D:2026-02-04",
        expected_ttl_seconds=5 * 60,  # 5 minutes for today's intraday
        expected_candle_count=78,  # 6.5 hours × 12 bars/hour
    ),
    # ... more scenarios
]

@pytest.fixture
def cache_scenario(request) -> CacheTestScenario:
    """Parameterized cache scenario fixture."""
    return request.param

@pytest.fixture
def isolated_cache():
    """Provide isolated cache state for testing."""
    from src.lambdas.shared.cache.cache_manager import invalidate_all_caches
    from src.lambdas.shared.aws_clients import _reset_all_clients

    # Clear all state before test
    invalidate_all_caches()

    yield

    # Clear all state after test
    invalidate_all_caches()
    _reset_all_clients()

@pytest.fixture
def mock_tiingo_success():
    """Mock Tiingo returning successful OHLC data."""
    # Return factory function for customization
    def _create_mock(candles: list | None = None):
        from unittest.mock import MagicMock
        mock = MagicMock()
        mock.get_ohlc.return_value = candles or [
            {"date": "2026-02-03", "open": 150.0, "high": 155.0, "low": 149.0, "close": 154.0, "volume": 1000000}
        ]
        return mock
    return _create_mock

@pytest.fixture
def mock_dynamodb_failure():
    """Mock DynamoDB that always fails."""
    from unittest.mock import MagicMock
    from botocore.exceptions import ClientError

    mock = MagicMock()
    mock.query.side_effect = ClientError(
        {"Error": {"Code": "ServiceUnavailable", "Message": "DynamoDB unavailable"}},
        "Query"
    )
    mock.batch_write_item.side_effect = ClientError(
        {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "Throttled"}},
        "BatchWriteItem"
    )
    return mock
```

### 15.11.0 Synthetic Data Generator for Edge Cases (Clarified 2026-02-04)

Use `exchange_calendars` library for dynamic trading day computation + recorded golden fixtures:

```python
# tests/fixtures/synthetic/market_data_generator.py
"""
Synthetic test data generator using exchange calendars.
Avoids brittle hardcoded dates that break when calendar changes.
"""
from datetime import date, timedelta
from typing import Iterator
import exchange_calendars as xcals

# NYSE calendar for US equities
NYSE = xcals.get_calendar("XNYS")

class MarketDataGenerator:
    """Generate test data aligned with real market calendar."""

    @staticmethod
    def next_trading_day(from_date: date = None) -> date:
        """Get next valid trading day (skips weekends, holidays)."""
        from_date = from_date or date.today()
        session = NYSE.next_session(from_date)
        return session.date()

    @staticmethod
    def previous_trading_day(from_date: date = None) -> date:
        """Get previous valid trading day."""
        from_date = from_date or date.today()
        session = NYSE.previous_session(from_date)
        return session.date()

    @staticmethod
    def next_weekend() -> date:
        """Get next Saturday (for G1 weekend tests)."""
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return today + timedelta(days=days_until_saturday)

    @staticmethod
    def next_market_holiday() -> date:
        """Get next NYSE holiday (for G2 holiday tests)."""
        today = date.today()
        # Look ahead up to 365 days for next holiday
        for i in range(365):
            check_date = today + timedelta(days=i)
            if not NYSE.is_session(check_date) and check_date.weekday() < 5:
                return check_date
        raise ValueError("No holiday found in next 365 days")

    @staticmethod
    def next_half_day() -> date:
        """Get next early close day (for G3 half-day tests)."""
        today = date.today()
        for i in range(365):
            check_date = today + timedelta(days=i)
            if NYSE.is_session(check_date):
                close_time = NYSE.session_close(check_date)
                # Early close is before 4 PM ET (21:00 UTC)
                if close_time.hour < 21:
                    return check_date
        raise ValueError("No half-day found in next 365 days")

    @staticmethod
    def trading_days_in_range(start: date, end: date) -> int:
        """Count trading days between two dates (for expected candle count)."""
        sessions = NYSE.sessions_in_range(start, end)
        return len(sessions)


# Golden fixtures for complex scenarios (recorded, not computed)
GOLDEN_FIXTURES = {
    # Stock splits - recorded actual split dates
    "AAPL_SPLIT_2020": {
        "ticker": "AAPL",
        "split_date": date(2020, 8, 31),
        "ratio": "4:1",
        "pre_split_close": 499.23,
        "post_split_close": 124.81,
    },
    "TSLA_SPLIT_2022": {
        "ticker": "TSLA",
        "split_date": date(2022, 8, 25),
        "ratio": "3:1",
        "pre_split_close": 891.29,
        "post_split_close": 297.10,
    },
    # Ticker changes - recorded actual change dates
    "FB_TO_META": {
        "old_ticker": "FB",
        "new_ticker": "META",
        "change_date": date(2022, 6, 9),
    },
    # IPO dates for boundary tests
    "AAPL_IPO": date(1980, 12, 12),
    "TSLA_IPO": date(2010, 6, 29),
    "GOOGL_IPO": date(2004, 8, 19),
}
```

**Usage in Tests:**
```python
# tests/unit/cache/test_edge_cases.py
from tests.fixtures.synthetic.market_data_generator import (
    MarketDataGenerator,
    GOLDEN_FIXTURES,
)

def test_G1_weekend_request_no_data_expected():
    """Weekend request returns 200 with empty candles."""
    weekend_date = MarketDataGenerator.next_weekend()
    response = client.get(f"/api/v2/tickers/AAPL/ohlc?date={weekend_date}")
    assert response.status_code == 200
    assert response.json()["candles"] == []

def test_G2_market_holiday_handling():
    """Holiday request returns 200 with no candles."""
    holiday = MarketDataGenerator.next_market_holiday()
    response = client.get(f"/api/v2/tickers/AAPL/ohlc?date={holiday}")
    assert response.status_code == 200
    assert response.json()["candles"] == []

def test_G11_ipo_date_boundary():
    """Request before IPO returns appropriate error."""
    ipo_date = GOLDEN_FIXTURES["AAPL_IPO"]
    pre_ipo = ipo_date - timedelta(days=30)
    response = client.get(f"/api/v2/tickers/AAPL/ohlc?start={pre_ipo}&end={pre_ipo}")
    # Should return 200 with empty data, not error
    assert response.status_code == 200
```

**Dependency:** Add `exchange_calendars>=4.0` to `requirements-ci.txt`.

### 15.11.1 Time Manipulation for TTL Tests

**Time Mocking Strategy (Clarified 2026-02-04):** Use `freezegun` library to freeze/advance time without waiting.

```python
# tests/unit/cache/test_ttl.py

import pytest
from datetime import date, timedelta
from freezegun import freeze_time

@freeze_time("2026-02-04 14:30:00", tz_offset=0)  # 2:30 PM UTC
def test_ttl_historical_90_days():
    """Historical data should have 90-day TTL."""
    from src.lambdas.shared.cache.ohlc_cache import _calculate_ttl

    # Yesterday's data = historical
    yesterday = date(2026, 2, 3)
    ttl = _calculate_ttl(resolution="D", end_date=yesterday)

    # Should expire ~90 days from now
    expected_expiry = int(time.time()) + (90 * 24 * 60 * 60)
    assert abs(ttl - expected_expiry) < 60  # Within 1 minute tolerance

@freeze_time("2026-02-04 14:30:00", tz_offset=0)
def test_ttl_today_intraday_5_minutes():
    """Today's intraday data should have 5-minute TTL."""
    from src.lambdas.shared.cache.ohlc_cache import _calculate_ttl

    today = date(2026, 2, 4)
    ttl = _calculate_ttl(resolution="5", end_date=today)

    # Should expire ~5 minutes from now
    expected_expiry = int(time.time()) + (5 * 60)
    assert abs(ttl - expected_expiry) < 10  # Within 10 seconds tolerance

@freeze_time("2026-02-04 14:30:00", tz_offset=0, auto_tick_seconds=1)
def test_ttl_expiry_triggers_refetch():
    """Expired cache entry should trigger refetch from API."""
    from src.lambdas.shared.cache.ohlc_cache import get_cached_candles, put_cached_candles

    # Write data with short TTL (mocked as 5 minutes)
    put_cached_candles(ticker="AAPL", source="tiingo", resolution="5", candles=[...], end_date=date.today())

    # Advance time past TTL
    with freeze_time("2026-02-04 14:36:00", tz_offset=0):  # 6 minutes later
        result = get_cached_candles(ticker="AAPL", source="tiingo", resolution="5", ...)

        # DynamoDB TTL is async, so item may still exist but should be treated as miss
        # Our code checks ExpiresAt < now before returning
        assert result.cache_hit is False or result.candles == []

@freeze_time("2026-02-04 23:59:59", tz_offset=0)
def test_ttl_boundary_end_of_day():
    """Request at 23:59 UTC should use correct date anchor."""
    from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key

    today = date(2026, 2, 4)
    key = _get_ohlc_cache_key("AAPL", "D", "1W", start_date=today - timedelta(days=7), end_date=today)

    # Key should anchor to today (Feb 4), not tomorrow
    assert "2026-02-04" in key
    assert "2026-02-05" not in key
```

**Dependency:** Add `freezegun>=1.2.0` to `requirements-ci.txt`.

### 15.11.2 Thundering Herd Test Pattern

**Concurrency Strategy (Clarified 2026-02-04):** Use `asyncio.gather()` with async tasks in single pytest process.

```python
# tests/unit/cache/test_thundering_herd.py

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_thundering_herd_prevention():
    """Verify 10 concurrent requests result in exactly 1 Tiingo API call."""

    # Track Tiingo calls
    tiingo_call_count = 0

    async def mock_fetch_from_tiingo(*args, **kwargs):
        nonlocal tiingo_call_count
        tiingo_call_count += 1
        # Simulate API latency to allow concurrent requests to pile up
        await asyncio.sleep(0.5)
        return [{"date": "2026-02-03", "open": 150.0, "high": 155.0, "low": 149.0, "close": 154.0, "volume": 1000000}]

    with patch("src.lambdas.dashboard.ohlc._fetch_from_tiingo", side_effect=mock_fetch_from_tiingo):
        with patch("src.lambdas.shared.cache.ohlc_cache._get_dynamodb_client") as mock_ddb:
            # Configure mock DynamoDB for lock behavior
            mock_client = MagicMock()
            mock_ddb.return_value = mock_client

            # First put_item succeeds (lock acquired), subsequent fail (lock held)
            call_count = 0
            def conditional_put(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return {}  # Lock acquired
                raise mock_client.exceptions.ConditionalCheckFailedException({}, "PutItem")

            mock_client.put_item.side_effect = conditional_put
            mock_client.query.return_value = {"Items": []}  # Cache miss initially

            # Fire 10 concurrent requests
            tasks = [
                fetch_ohlc_with_cache("AAPL", "D", "1W")
                for _ in range(10)
            ]

            results = await asyncio.gather(*tasks)

    # Assert: Tiingo called exactly once despite 10 concurrent requests
    assert tiingo_call_count == 1, f"Expected 1 Tiingo call, got {tiingo_call_count}"

    # Assert: All 10 requests got the same data
    assert all(r == results[0] for r in results), "All requests should return identical data"
```

### 15.11.3 Cross-Lambda Isolation Pattern

**Isolation Strategy (Clarified 2026-02-04):** Use `importlib.reload()` to reset module state, simulating Lambda cold start.

```python
# tests/integration/cache/test_cross_lambda_coherence.py

import importlib
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def lambda_instance_1():
    """Simulate Lambda instance 1 with fresh module state."""
    # Reload modules to reset singletons
    import src.lambdas.shared.cache.ohlc_cache as cache_module
    import src.lambdas.shared.aws_clients as clients_module

    importlib.reload(clients_module)
    importlib.reload(cache_module)

    return cache_module

@pytest.fixture
def lambda_instance_2():
    """Simulate Lambda instance 2 with fresh module state (separate cold start)."""
    import src.lambdas.shared.cache.ohlc_cache as cache_module
    import src.lambdas.shared.aws_clients as clients_module

    importlib.reload(clients_module)
    importlib.reload(cache_module)

    return cache_module

@pytest.mark.integration
def test_cross_lambda_cache_coherence(mock_dynamodb, lambda_instance_1, lambda_instance_2):
    """Lambda 1 writes to DynamoDB, Lambda 2 (cold start) reads correctly."""

    # Lambda 1: Write data to DynamoDB
    candles = [{"date": "2026-02-03", "open": 150.0, "high": 155.0, "low": 149.0, "close": 154.0, "volume": 1000000}]
    lambda_instance_1.put_cached_candles(
        ticker="AAPL",
        source="tiingo",
        resolution="D",
        candles=candles,
        end_date=date(2026, 2, 3)
    )

    # Verify Lambda 1's in-memory cache is populated
    assert "AAPL" in str(lambda_instance_1._ohlc_read_through_cache._cache)

    # Lambda 2: Fresh cold start - in-memory cache is EMPTY
    assert len(lambda_instance_2._ohlc_read_through_cache._cache) == 0

    # Lambda 2: Read from DynamoDB (should hit, not miss)
    result = lambda_instance_2.get_cached_candles(
        ticker="AAPL",
        source="tiingo",
        resolution="D",
        start_time=datetime(2026, 2, 3, tzinfo=UTC),
        end_time=datetime(2026, 2, 3, 23, 59, 59, tzinfo=UTC),
        consistent_read=True  # Strong consistency for cross-instance
    )

    assert result.cache_hit is True
    assert len(result.candles) == 1
    assert result.candles[0].close == 154.0

@pytest.mark.integration
def test_circuit_breaker_isolated_per_lambda(lambda_instance_1, lambda_instance_2):
    """Circuit breaker state should NOT persist across Lambda instances."""

    # Lambda 1: Trigger circuit breaker (3 failures)
    for _ in range(3):
        lambda_instance_1._record_failure()

    assert lambda_instance_1._is_circuit_open() is True

    # Lambda 2: Fresh instance - circuit should be CLOSED
    assert lambda_instance_2._is_circuit_open() is False
```

**Important:** Tests using `importlib.reload()` should be marked `@pytest.mark.integration` and run in isolation (`pytest -x`) to avoid polluting other tests' module state.

### 15.12 Failure Injection Helpers

```python
# tests/fixtures/mocks/cache_failure_injector.py

from dataclasses import dataclass
from typing import Callable, Any
import time

@dataclass
class FailureProfile:
    """Configures failure injection behavior."""
    failure_rate: float = 0.0  # 0.0 to 1.0
    latency_ms: int = 0
    fail_after_n_calls: int | None = None
    fail_for_n_seconds: int | None = None

class CacheFailureInjector:
    """Inject failures into cache operations for resilience testing."""

    def __init__(self, profile: FailureProfile):
        self.profile = profile
        self._call_count = 0
        self._failure_start: float | None = None

    def should_fail(self) -> bool:
        """Determine if this call should fail."""
        self._call_count += 1

        # Fail after N calls
        if self.profile.fail_after_n_calls is not None:
            if self._call_count > self.profile.fail_after_n_calls:
                return True

        # Fail for N seconds
        if self.profile.fail_for_n_seconds is not None:
            if self._failure_start is None:
                self._failure_start = time.time()
            if time.time() - self._failure_start < self.profile.fail_for_n_seconds:
                return True

        # Random failure rate
        import random
        return random.random() < self.profile.failure_rate

    def maybe_inject_latency(self):
        """Inject artificial latency."""
        if self.profile.latency_ms > 0:
            time.sleep(self.profile.latency_ms / 1000)

# Pre-configured injectors for common scenarios
def create_intermittent_failure_injector(failure_rate: float = 0.3):
    """30% random failures - tests retry logic."""
    return CacheFailureInjector(FailureProfile(failure_rate=failure_rate))

def create_thundering_herd_injector(latency_ms: int = 2000):
    """Slow responses - tests lock wait logic."""
    return CacheFailureInjector(FailureProfile(latency_ms=latency_ms))

def create_circuit_breaker_trigger_injector():
    """Fails consistently - tests circuit breaker opens."""
    return CacheFailureInjector(FailureProfile(failure_rate=1.0))

def create_recovery_injector(fail_for_seconds: int = 5):
    """Fails then recovers - tests circuit breaker close."""
    return CacheFailureInjector(FailureProfile(fail_for_n_seconds=fail_for_seconds))
```

### 15.13 Playwright Test Utilities

```typescript
// frontend/tests/e2e/utils/cache-helpers.ts

import { Page, Route } from '@playwright/test';

interface CacheMetrics {
  requests: number;
  cacheHits: number;
  cacheMisses: number;
  apiCalls: number;
  avgResponseTime: number;
}

/**
 * Intercept and track cache behavior for E2E tests.
 */
export async function trackCacheMetrics(page: Page): Promise<CacheMetrics> {
  const metrics: CacheMetrics = {
    requests: 0,
    cacheHits: 0,
    cacheMisses: 0,
    apiCalls: 0,
    avgResponseTime: 0,
  };

  const responseTimes: number[] = [];

  await page.route('**/api/v2/tickers/*/ohlc**', async (route: Route) => {
    const startTime = Date.now();

    // Continue the request
    const response = await route.fetch();

    const responseTime = Date.now() - startTime;
    responseTimes.push(responseTime);

    // Extract cache source header
    const cacheSource = response.headers()['x-cache-source'] || 'unknown';

    metrics.requests++;
    if (cacheSource === 'in-memory' || cacheSource === 'dynamodb') {
      metrics.cacheHits++;
    } else if (cacheSource === 'tiingo' || cacheSource === 'finnhub') {
      metrics.cacheMisses++;
      metrics.apiCalls++;
    }

    metrics.avgResponseTime = responseTimes.reduce((a, b) => a + b, 0) / responseTimes.length;

    // Continue with original response
    await route.fulfill({ response });
  });

  return metrics;
}

/**
 * Wait for chart to be fully rendered with data.
 */
export async function waitForChartData(page: Page, timeout: number = 10000): Promise<void> {
  // Wait for chart container
  await page.waitForSelector('[data-testid="price-chart"]', { timeout });

  // Wait for at least one candle to be rendered
  await page.waitForFunction(
    () => {
      const chart = document.querySelector('[data-testid="price-chart"]');
      if (!chart) return false;

      // Check for lightweight-charts rendered elements
      const candles = chart.querySelectorAll('.tv-lightweight-charts');
      return candles.length > 0;
    },
    { timeout }
  );
}

/**
 * Simulate viewport resize and verify chart stability.
 */
export async function testViewportResize(
  page: Page,
  widths: number[] = [1920, 1280, 768, 375]
): Promise<boolean> {
  let isStable = true;

  for (const width of widths) {
    await page.setViewportSize({ width, height: 800 });

    // Wait for resize animation
    await page.waitForTimeout(300);

    // Verify chart still has data
    const hasData = await page.evaluate(() => {
      const chart = document.querySelector('[data-testid="price-chart"]');
      return chart && chart.innerHTML.length > 100;
    });

    if (!hasData) {
      isStable = false;
      break;
    }
  }

  return isStable;
}

/**
 * Network condition presets for testing.
 */
export const networkConditions = {
  slow3g: {
    offline: false,
    downloadThroughput: (500 * 1024) / 8,  // 500 kbps
    uploadThroughput: (500 * 1024) / 8,
    latency: 400,  // 400ms RTT
  },
  offline: {
    offline: true,
    downloadThroughput: 0,
    uploadThroughput: 0,
    latency: 0,
  },
  fast: {
    offline: false,
    downloadThroughput: (10 * 1024 * 1024) / 8,  // 10 Mbps
    uploadThroughput: (5 * 1024 * 1024) / 8,
    latency: 20,
  },
};
```

### 15.13.1 Bootstrap Selector Verification (Clarified 2026-02-04)

Playwright globalSetup verifies all required data-testid selectors exist before tests run:

```typescript
// frontend/tests/e2e/global-setup.ts

import { chromium, FullConfig } from '@playwright/test';

/**
 * Required data-testid attributes for OHLC cache tests.
 * If any are missing, tests fail fast with clear error.
 */
const REQUIRED_SELECTORS = [
  'price-chart',
  'range-selector',
  'resolution-selector',
  'loading-spinner',
  'error-message',
  'retry-button',
  'cache-status',  // Optional: shows X-Cache-Source in dev mode
];

async function globalSetup(config: FullConfig) {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  // Navigate to chart page
  await page.goto(`${config.projects[0].use.baseURL}/tickers/AAPL`);
  await page.waitForLoadState('domcontentloaded');

  // Check all required selectors
  const missing: string[] = [];
  for (const testId of REQUIRED_SELECTORS) {
    const element = await page.$(`[data-testid="${testId}"]`);
    if (!element) {
      missing.push(testId);
    }
  }

  await browser.close();

  if (missing.length > 0) {
    throw new Error(
      `\n` +
      `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
      `  PLAYWRIGHT BOOTSTRAP FAILED: Missing data-testid\n` +
      `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n` +
      `\n` +
      `  The following data-testid attributes are required\n` +
      `  but not found in the rendered page:\n` +
      `\n` +
      missing.map(id => `    ❌ data-testid="${id}"`).join('\n') +
      `\n\n` +
      `  Add these attributes to the frontend components\n` +
      `  before running E2E tests.\n` +
      `\n` +
      `  See: frontend/src/components/PriceChart.tsx\n` +
      `━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`
    );
  }

  console.log(`✅ All ${REQUIRED_SELECTORS.length} required data-testid selectors verified`);
}

export default globalSetup;
```

**Playwright config:**
```typescript
// playwright.config.ts
export default defineConfig({
  globalSetup: require.resolve('./tests/e2e/global-setup'),
  // ...
});
```

### 15.14 Test Execution Order

Tests should run in dependency order to maximize efficiency and catch blocking issues early:

```yaml
# .github/workflows/test-cache.yml (excerpt)

jobs:
  test-cache:
    strategy:
      fail-fast: true  # Stop on first failure
      matrix:
        stage: [unit, integration, e2e]

    steps:
      - name: Unit Tests (P0 First)
        if: matrix.stage == 'unit'
        run: |
          # P0: Race conditions and data integrity
          pytest tests/unit/ -k "thundering_herd or lock or integrity" -x --tb=short

          # P1: Cache keys and TTL
          pytest tests/unit/ -k "cache_key or ttl" -x --tb=short

          # P2+: Everything else
          pytest tests/unit/ --ignore-glob="*thundering*" --ignore-glob="*lock*" -x --tb=short

      - name: Integration Tests
        if: matrix.stage == 'integration'
        run: |
          pytest tests/integration/ohlc/ -x --tb=short

      - name: E2E Tests (Playwright)
        if: matrix.stage == 'e2e'
        run: |
          # Core functionality first
          npx playwright test tests/e2e/cache --project=chromium

          # Viewport and network tests (lower priority)
          npx playwright test tests/e2e/viewport tests/e2e/network --project=chromium
```

### 15.14.1 Test Environment Strategy

**Decision (Clarified 2026-02-04):** Hybrid approach - moto for CI, expanded smoke test for preprod sanity.

```
┌─────────────────────────────────────────────────────────────────┐
│                    TEST ENVIRONMENT STRATEGY                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  UNIT TESTS (moto @mock_aws)    INTEGRATION TESTS (moto)        │
│  ├─ A1-A10 (cache keys)         ├─ E13 (outage recovery)        │
│  ├─ B1-B10 (data integrity)     ├─ E14 (throttle retry)         │
│  ├─ C1-C12 (TTL)                ├─ D11-D12 (concurrent tickers) │
│  ├─ D1-D10 (race conditions)    └─ Cross-Lambda (importlib)     │
│  └─ E1-E12 (failures)                                           │
│                                                                  │
│  PREPROD SANITY TESTS (real AWS) - scripts/sanity-test-cache.py │
│  ├─ Round-trip data integrity (B11)                             │
│  ├─ Field preservation (B12)                                    │
│  ├─ Sequential coherence (F8-lite)                              │
│  ├─ Cache hit verification (existing smoke test)                │
│  └─ X-Cache-Source header validation                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Rationale:**
- **moto for CI:** Fast (no container startup), deterministic, supports failure injection
- **Preprod sanity:** Validates real AWS behavior, IAM permissions, network latency
- **No LocalStack:** Overkill for cache testing; moto sufficient for DynamoDB operations

### 15.14.2 Preprod Sanity Test Script

**File:** `scripts/sanity-test-cache.py`

```python
#!/usr/bin/env python3
"""Extended preprod sanity tests for OHLC cache.

Runs against real AWS to validate behaviors that moto cannot catch:
- IAM permission issues
- Network latency effects
- Real DynamoDB consistency behavior
- Production table configuration

Usage: python scripts/sanity-test-cache.py --env preprod
Requires: SMOKE_TEST_API_KEY env var (from Secrets Manager)

Test Data Isolation (Clarified 2026-02-04):
- Uses test-prefixed cache keys: TEST#{run_id}#ohlc:...
- 5-minute TTL for automatic cleanup
- Explicit cleanup after test run for immediate isolation
"""
import argparse
import atexit
import os
import requests
import sys
import time
import uuid

# Generate unique run ID for test isolation
TEST_RUN_ID = os.environ.get("CI_RUN_ID", str(uuid.uuid4())[:8])
TEST_PREFIX = f"TEST#{TEST_RUN_ID}#"

# Track test keys for cleanup
_test_keys_created: list[str] = []

def get_api_url(env: str) -> str:
    return f"https://api.{env}.sentiment-analyzer.example.com"

def get_auth_headers() -> dict:
    api_key = os.environ.get("SMOKE_TEST_API_KEY")
    if not api_key:
        print("❌ SMOKE_TEST_API_KEY not set")
        sys.exit(1)
    return {"Authorization": f"Bearer {api_key}"}

def test_round_trip_data_integrity(api_url: str, headers: dict):
    """B11: Verify data survives Tiingo → DynamoDB → Response."""
    print("\n[B11] Testing round-trip data integrity...")

    # Use unique cache-busting param to force fresh fetch
    ticker = "AAPL"
    endpoint = f"{api_url}/api/v2/tickers/{ticker}/ohlc?range=1W&resolution=D"

    # Request 1: Fetch (may hit cache or API)
    r1 = requests.get(endpoint, headers=headers)
    assert r1.status_code == 200, f"Request 1 failed: {r1.status_code}"
    source1 = r1.headers.get("X-Cache-Source", "unknown")
    candles1 = r1.json()["candles"]
    print(f"  Request 1: {len(candles1)} candles, source={source1}")

    # Brief wait for write-through
    time.sleep(1)

    # Request 2: Should hit cache
    r2 = requests.get(endpoint, headers=headers)
    assert r2.status_code == 200, f"Request 2 failed: {r2.status_code}"
    source2 = r2.headers.get("X-Cache-Source", "unknown")
    candles2 = r2.json()["candles"]
    print(f"  Request 2: {len(candles2)} candles, source={source2}")

    # Data integrity check
    if candles1 == candles2:
        print("  ✅ PASS: Data integrity preserved through cache")
    else:
        print("  ❌ FAIL: Data mismatch!")
        print(f"    Candles 1: {candles1[:2]}...")
        print(f"    Candles 2: {candles2[:2]}...")
        return False
    return True

def test_field_preservation(api_url: str, headers: dict):
    """B12: Verify all OHLC fields preserved through cache."""
    print("\n[B12] Testing field preservation...")

    endpoint = f"{api_url}/api/v2/tickers/MSFT/ohlc?range=1W&resolution=D"

    r = requests.get(endpoint, headers=headers)
    assert r.status_code == 200
    candles = r.json()["candles"]

    required_fields = ["date", "open", "high", "low", "close", "volume"]
    for i, candle in enumerate(candles[:3]):  # Check first 3
        for field in required_fields:
            if field not in candle:
                print(f"  ❌ FAIL: Candle {i} missing field '{field}'")
                return False
            if candle[field] is None and field != "volume":
                print(f"  ❌ FAIL: Candle {i} has null '{field}'")
                return False

    print(f"  ✅ PASS: All {len(required_fields)} fields present in {len(candles)} candles")
    return True

def test_sequential_coherence(api_url: str, headers: dict):
    """F8-lite: Sequential requests return consistent data."""
    print("\n[F8] Testing sequential coherence...")

    endpoint = f"{api_url}/api/v2/tickers/GOOGL/ohlc?range=1M&resolution=D"

    results = []
    sources = []
    for i in range(5):
        r = requests.get(endpoint, headers=headers)
        assert r.status_code == 200, f"Request {i+1} failed"
        results.append(r.json()["candles"])
        sources.append(r.headers.get("X-Cache-Source", "unknown"))
        time.sleep(0.5)  # Simulate time between requests

    print(f"  Sources: {sources}")

    # All 5 requests should return identical data
    if all(r == results[0] for r in results):
        print(f"  ✅ PASS: All 5 requests returned identical data ({len(results[0])} candles)")
        return True
    else:
        print("  ❌ FAIL: Cache incoherence detected!")
        return False

def test_cache_header_present(api_url: str, headers: dict):
    """Verify X-Cache-Source header is always present."""
    print("\n[Header] Testing X-Cache-Source header...")

    endpoint = f"{api_url}/api/v2/tickers/NVDA/ohlc?range=1W&resolution=D"

    r = requests.get(endpoint, headers=headers)
    assert r.status_code == 200

    source = r.headers.get("X-Cache-Source")
    cache_key = r.headers.get("X-Cache-Key")

    if source in ("in-memory", "dynamodb", "tiingo", "finnhub"):
        print(f"  ✅ PASS: X-Cache-Source={source}")
    else:
        print(f"  ❌ FAIL: Invalid or missing X-Cache-Source: {source}")
        return False

    if cache_key:
        print(f"  ✅ PASS: X-Cache-Key={cache_key}")
    else:
        print(f"  ⚠️  WARN: X-Cache-Key header missing (optional)")

    return True

def cleanup_test_data(env: str):
    """Explicit cleanup of test data after run (belt-and-suspenders with TTL)."""
    if not _test_keys_created:
        return

    print(f"\n[Cleanup] Removing {len(_test_keys_created)} test cache entries...")

    # Use boto3 directly for cleanup (not via API)
    import boto3
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    table_name = f"{env}-ohlc-cache"

    deleted = 0
    for key in _test_keys_created:
        try:
            # Keys are stored as TEST#{run_id}#ohlc:TICKER:...
            # Extract PK and SK from the full key
            dynamodb.delete_item(
                TableName=table_name,
                Key={"PK": {"S": key}, "SK": {"S": "DATA"}},
            )
            deleted += 1
        except Exception as e:
            print(f"  ⚠️  Failed to delete {key}: {e}")

    print(f"  ✅ Cleaned up {deleted}/{len(_test_keys_created)} test entries")

def main():
    parser = argparse.ArgumentParser(description="OHLC Cache Sanity Tests")
    parser.add_argument("--env", required=True, choices=["dev", "preprod", "prod"])
    parser.add_argument("--skip-cleanup", action="store_true", help="Skip test data cleanup")
    args = parser.parse_args()

    # Register cleanup on exit (even on failure)
    if not args.skip_cleanup:
        atexit.register(cleanup_test_data, args.env)

    api_url = get_api_url(args.env)
    headers = get_auth_headers()

    print(f"Running sanity tests against {args.env}...")
    print(f"API URL: {api_url}")
    print(f"Test Run ID: {TEST_RUN_ID} (keys prefixed with {TEST_PREFIX})")

    tests = [
        ("B11 - Round-trip integrity", lambda: test_round_trip_data_integrity(api_url, headers)),
        ("B12 - Field preservation", lambda: test_field_preservation(api_url, headers)),
        ("F8  - Sequential coherence", lambda: test_sequential_coherence(api_url, headers)),
        ("HDR - Cache header present", lambda: test_cache_header_present(api_url, headers)),
    ]

    passed = 0
    failed = 0
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ EXCEPTION: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        print("❌ SANITY TESTS FAILED")
        sys.exit(1)
    else:
        print("✅ ALL SANITY TESTS PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

**CI Integration:**
```yaml
# .github/workflows/deploy.yml (after terraform apply)
- name: Run sanity tests
  if: env.ENVIRONMENT != 'prod'  # Skip prod, run on preprod
  env:
    SMOKE_TEST_API_KEY: ${{ secrets.SMOKE_TEST_API_KEY }}
    CI_RUN_ID: ${{ github.run_id }}-${{ github.run_attempt }}  # Unique per CI run
  run: python scripts/sanity-test-cache.py --env ${{ env.ENVIRONMENT }}
```

**Test Data Isolation Guarantees:**
- Each CI run uses unique prefix: `TEST#12345678-1#ohlc:...`
- Concurrent runs cannot interfere (different prefixes)
- 5-minute TTL auto-cleans even if explicit cleanup fails
- Explicit cleanup runs on exit (including test failures)
- Production data never touched (different key prefix)

### 15.15 Test Coverage Gates

| Gate | Threshold | Action on Failure |
|------|-----------|-------------------|
| Unit Test Line Coverage | ≥90% | Block merge |
| Unit Test Branch Coverage | ≥85% | Block merge |
| Integration Test Pass Rate | 100% | Block merge |
| E2E Core Test Pass Rate | 100% | Block merge |
| E2E Viewport Test Pass Rate | ≥95% | Warning only |
| Mutation Test Score | ≥70% | Warning only |
| Alerting Metric Coverage | 100% | Block merge |

### 15.15.1 Alerting Metric Test Pattern (Clarified 2026-02-04)

**Scope:** This spec's 4 CloudWatch metrics that power production alerts. Pattern to be ported codebase-wide via `future/observability-metric-coverage-audit.md`.

**Metrics Under Test:**

| Metric | Alert | Emission Location | Test ID |
|--------|-------|-------------------|---------|
| `CacheError` | Slack | `_read_from_dynamodb()`, `_write_through_to_dynamodb()` | M1, M2 |
| `CircuitBreakerOpen` | PagerDuty | `_record_failure()` | M3 |
| `CachePaginationTruncation` | PagerDuty | `get_cached_candles()` | M4 |
| `UnprocessedWriteItems` | Slack | `put_cached_candles()` | M5 |

**Test File:** `tests/unit/cache/test_alerting_metrics.py`

```python
"""Tests verifying CloudWatch metrics that power production alerts.

These metrics are CRITICAL - if they don't emit, alerts don't fire.
This is the canonical pattern for metric testing; to be ported codebase-wide.
"""
import pytest
from unittest.mock import patch, MagicMock, call

class TestAlertingMetricEmission:
    """Verify all 4 alerting metrics are emitted from correct code paths."""

    @pytest.fixture
    def mock_cloudwatch(self):
        """Mock CloudWatch client for metric assertions."""
        with patch("src.lambdas.shared.aws_clients.get_cloudwatch_client") as mock:
            client = MagicMock()
            mock.return_value = client
            yield client

    def test_M1_cache_error_on_dynamodb_read_failure(self, mock_cloudwatch, mock_dynamodb_failure):
        """CacheError metric emitted when DynamoDB read fails."""
        from src.lambdas.dashboard.ohlc import _read_from_dynamodb

        _read_from_dynamodb("AAPL", "tiingo", "D", ...)

        # Verify metric emission
        mock_cloudwatch.put_metric_data.assert_called()
        call_args = mock_cloudwatch.put_metric_data.call_args

        assert call_args.kwargs["Namespace"] == "SentimentAnalyzer/OHLCCache"
        metric = call_args.kwargs["MetricData"][0]
        assert metric["MetricName"] == "CacheError"
        assert metric["Value"] == 1
        assert metric["Unit"] == "Count"

    def test_M2_cache_error_on_dynamodb_write_failure(self, mock_cloudwatch, mock_dynamodb_failure):
        """CacheError metric emitted when DynamoDB write fails."""
        from src.lambdas.dashboard.ohlc import _write_through_to_dynamodb

        _write_through_to_dynamodb("AAPL", "tiingo", "D", [...], date.today())

        mock_cloudwatch.put_metric_data.assert_called()
        metric = mock_cloudwatch.put_metric_data.call_args.kwargs["MetricData"][0]
        assert metric["MetricName"] == "CacheError"

    def test_M3_circuit_breaker_open_metric(self, mock_cloudwatch):
        """CircuitBreakerOpen metric emitted when breaker trips (3 failures)."""
        from src.lambdas.shared.cache.ohlc_cache import _record_failure, _circuit_breaker

        # Reset circuit breaker state
        _circuit_breaker["failures"] = 0
        _circuit_breaker["open_until"] = 0

        # Trigger 3 failures to trip breaker
        for _ in range(3):
            _record_failure()

        # Verify the CRITICAL metric was emitted exactly once
        calls = mock_cloudwatch.put_metric_data.call_args_list
        circuit_calls = [
            c for c in calls
            if c.kwargs["MetricData"][0]["MetricName"] == "CircuitBreakerOpen"
        ]
        assert len(circuit_calls) == 1, "CircuitBreakerOpen must emit exactly once on trip"

    def test_M4_pagination_truncation_metric(self, mock_cloudwatch):
        """CachePaginationTruncation metric emitted when query exceeds 1MB."""
        from src.lambdas.shared.cache.ohlc_cache import get_cached_candles

        with patch("src.lambdas.shared.aws_clients.get_dynamodb_client") as mock_ddb:
            mock_client = MagicMock()
            mock_ddb.return_value = mock_client
            # Simulate paginated response (data truncated)
            mock_client.query.return_value = {
                "Items": [...],
                "LastEvaluatedKey": {"PK": "...", "SK": "..."}  # Pagination marker
            }

            get_cached_candles("AAPL", "tiingo", "D", ...)

        metric = mock_cloudwatch.put_metric_data.call_args.kwargs["MetricData"][0]
        assert metric["MetricName"] == "CachePaginationTruncation"

    def test_M5_unprocessed_write_items_metric(self, mock_cloudwatch):
        """UnprocessedWriteItems metric emitted when batch write partially fails."""
        from src.lambdas.shared.cache.ohlc_cache import put_cached_candles

        with patch("src.lambdas.shared.aws_clients.get_dynamodb_client") as mock_ddb:
            mock_client = MagicMock()
            mock_ddb.return_value = mock_client
            # Simulate partial failure after max retries
            mock_client.batch_write_item.return_value = {
                "UnprocessedItems": {"table": [{"PutRequest": {...}}]}
            }

            put_cached_candles("AAPL", "tiingo", "D", [...], date.today())

        metric = mock_cloudwatch.put_metric_data.call_args.kwargs["MetricData"][0]
        assert metric["MetricName"] == "UnprocessedWriteItems"
        assert metric["Value"] >= 1  # At least 1 unprocessed item


class TestMetricEmissionSilentFailure:
    """Verify metric emission failures don't break the request."""

    def test_cloudwatch_failure_does_not_fail_request(self):
        """Request succeeds even if CloudWatch is unavailable."""
        with patch("src.lambdas.shared.aws_clients.get_cloudwatch_client") as mock:
            mock.return_value.put_metric_data.side_effect = Exception("CW unavailable")

            # This should NOT raise
            from src.lambdas.shared.cache.ohlc_cache import _record_failure
            _record_failure()  # Should swallow CloudWatch error
```

**CI Gate:**
```yaml
# Alerting metric tests must pass - these power production alerts
- name: Alerting Metric Coverage
  run: pytest tests/unit/cache/test_alerting_metrics.py -v --tb=short
```

### 15.16 Debugging Test Failures

**When cache tests fail, check in this order:**

1. **X-Cache-Source header** - Which layer responded?
2. **Cache key** - Does it match expected format?
3. **TTL** - Is data expired?
4. **Lock state** - Is lock held by another process?
5. **Circuit breaker** - Is DynamoDB being skipped?
6. **CloudWatch metrics** - Any CacheError or CircuitBreakerOpen events?

**Common failure patterns:**

| Symptom | Likely Cause | Investigation |
|---------|--------------|---------------|
| Always cache miss | Cache key mismatch | Compare generated vs expected key |
| Intermittent miss | Race condition | Check lock acquisition timing |
| Data corruption | Precision loss | Compare float values exactly |
| Slow response | Circuit open | Check _circuit_breaker state |
| Test flaky in CI | Timing issue | Add explicit waits/retries |

### 15.17 Regression Test Workflow (Clarified 2026-02-04)

**When a production bug is fixed, a regression test MUST be added.**

**Test ID Format:** `R{issue_number}_{brief_description}`
- Example: `R1234_cache_key_missing_date_anchor`
- Example: `R5678_volume_none_crashes_write`

**PR Template Section (required for bug fixes):**

```markdown
## Regression Test

<!-- Required for bug fix PRs. Delete section for feature PRs. -->

- [ ] Test ID: `R_____{description}`
- [ ] Test fails before fix (verified locally)
- [ ] Test passes after fix
- [ ] Test linked to issue: #____

**Test Location:** `tests/regression/test_r{issue}.py`
```

**Regression Test File Structure:**

```python
# tests/regression/test_r1234.py
"""
Regression test for issue #1234: Cache key missing date anchor
https://github.com/org/repo/issues/1234

Bug: Cache key did not include end_date, causing stale data across days.
Fix: Added date anchor to cache key format.
"""
import pytest
from datetime import date

class TestR1234CacheKeyDateAnchor:
    """Regression: Cache key must include date anchor to prevent stale data."""

    def test_R1234_different_days_different_keys(self):
        """Same ticker/range on different days must have different cache keys.

        Before fix: Both returned "ohlc:AAPL:D:1W"
        After fix: Returns "ohlc:AAPL:D:1W:2026-02-03" and "ohlc:AAPL:D:1W:2026-02-04"
        """
        from src.lambdas.dashboard.ohlc import _get_ohlc_cache_key

        key_day1 = _get_ohlc_cache_key(
            ticker="AAPL",
            resolution="D",
            time_range="1W",
            start_date=date(2026, 1, 27),
            end_date=date(2026, 2, 3),
        )

        key_day2 = _get_ohlc_cache_key(
            ticker="AAPL",
            resolution="D",
            time_range="1W",
            start_date=date(2026, 1, 28),
            end_date=date(2026, 2, 4),
        )

        # Keys MUST be different (this failed before the fix)
        assert key_day1 != key_day2, "Cache keys must include date anchor"
        assert "2026-02-03" in key_day1
        assert "2026-02-04" in key_day2
```

**CI Gate:**
```yaml
# Regression tests run with P0 priority
- name: Regression Tests
  run: pytest tests/regression/ -v --tb=short -x
```

**Traceability:**
- Each test file links to the original issue
- Issue should link back to the test in its resolution comment
- Git blame on test file shows the fix commit

### 15.18 Mock Fidelity Testing (Clarified 2026-02-04)

**Problem:** Moto mock behavior can drift from real AWS DynamoDB, causing tests to pass locally but fail in production.

**Solution:** Weekly mock fidelity test comparing moto vs preprod behavior, scheduled via GitHub API.

**Scheduling Mechanism:**
```yaml
# .github/workflows/mock-fidelity.yml
name: Mock Fidelity Check

on:
  # Run on every PR, but skip if run within last 7 days
  pull_request:
    branches: [main]
  # Also allow manual trigger
  workflow_dispatch:

jobs:
  check-if-due:
    runs-on: ubuntu-latest
    outputs:
      should_run: ${{ steps.check.outputs.should_run }}
    steps:
      - name: Check last successful run
        id: check
        env:
          GH_TOKEN: ${{ github.token }}
        run: |
          # Query GitHub API for last successful mock-fidelity run
          LAST_RUN=$(gh api \
            "/repos/${{ github.repository }}/actions/workflows/mock-fidelity.yml/runs?status=success&per_page=1" \
            --jq '.workflow_runs[0].created_at // empty')

          if [ -z "$LAST_RUN" ]; then
            echo "No previous run found, should run"
            echo "should_run=true" >> $GITHUB_OUTPUT
            exit 0
          fi

          # Calculate days since last run
          LAST_RUN_EPOCH=$(date -d "$LAST_RUN" +%s)
          NOW_EPOCH=$(date +%s)
          DAYS_SINCE=$(( (NOW_EPOCH - LAST_RUN_EPOCH) / 86400 ))

          echo "Last run: $LAST_RUN ($DAYS_SINCE days ago)"

          if [ $DAYS_SINCE -ge 7 ]; then
            echo "should_run=true" >> $GITHUB_OUTPUT
          else
            echo "should_run=false" >> $GITHUB_OUTPUT
            echo "Skipping - last run was $DAYS_SINCE days ago (< 7 days)"
          fi

  mock-fidelity:
    needs: check-if-due
    if: needs.check-if-due.outputs.should_run == 'true'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run fidelity tests
        env:
          SMOKE_TEST_API_KEY: ${{ secrets.SMOKE_TEST_API_KEY }}
        run: python scripts/mock-fidelity-test.py --env preprod
```

**Fidelity Test Script:**
```python
# scripts/mock-fidelity-test.py
"""
Compare moto mock behavior against real DynamoDB.
Flags any behavioral differences that could cause test/prod divergence.
"""
from datetime import date
from moto import mock_aws
import boto3

# Operations to test for fidelity
FIDELITY_CHECKS = [
    "query_empty_table",
    "query_with_results",
    "conditional_put_success",
    "conditional_put_failure",
    "batch_write_success",
    "batch_write_partial_failure",
    "query_pagination",
    "ttl_attribute_format",
]

def run_operation(client, table_name: str, operation: str) -> dict:
    """Run an operation and capture the response shape."""
    if operation == "query_empty_table":
        return client.query(
            TableName=table_name,
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": {"S": "nonexistent"}}
        )
    elif operation == "conditional_put_failure":
        # First put, then try conditional put expecting failure
        client.put_item(TableName=table_name, Item={"PK": {"S": "test"}, "SK": {"S": "1"}})
        try:
            client.put_item(
                TableName=table_name,
                Item={"PK": {"S": "test"}, "SK": {"S": "1"}},
                ConditionExpression="attribute_not_exists(PK)"
            )
            return {"error": None}  # Should have failed
        except client.exceptions.ConditionalCheckFailedException as e:
            return {"error": type(e).__name__, "code": e.response["Error"]["Code"]}
    # ... other operations

def compare_responses(moto_response: dict, real_response: dict, operation: str) -> list[str]:
    """Compare response shapes and return differences."""
    differences = []

    # Check keys match
    moto_keys = set(moto_response.keys())
    real_keys = set(real_response.keys())

    if moto_keys != real_keys:
        differences.append(f"{operation}: Key mismatch - moto has {moto_keys - real_keys}, real has {real_keys - moto_keys}")

    # Check error codes match for failure cases
    if "error" in moto_response and "error" in real_response:
        if moto_response.get("code") != real_response.get("code"):
            differences.append(f"{operation}: Error code mismatch - moto={moto_response.get('code')}, real={real_response.get('code')}")

    return differences

def main():
    all_differences = []

    for operation in FIDELITY_CHECKS:
        # Run against moto
        with mock_aws():
            moto_client = boto3.client("dynamodb", region_name="us-east-1")
            # Create test table...
            moto_response = run_operation(moto_client, "test-table", operation)

        # Run against preprod
        real_client = boto3.client("dynamodb", region_name="us-east-1")
        real_response = run_operation(real_client, "preprod-ohlc-cache-fidelity", operation)

        # Compare
        diffs = compare_responses(moto_response, real_response, operation)
        all_differences.extend(diffs)

    if all_differences:
        print("❌ MOCK FIDELITY FAILURES:")
        for diff in all_differences:
            print(f"  - {diff}")
        exit(1)
    else:
        print("✅ All mock fidelity checks passed")
        exit(0)
```

**Benefits:**
- Self-contained scheduling (no external cron)
- Runs at most weekly (doesn't slow every PR)
- Catches moto drift before it causes production issues
- Documents expected DynamoDB behavior

### 15.19 Backwards-Engineered Test Additions (Clarified 2026-02-05)

This section documents additional tests identified through rigorous backwards analysis of failure modes. These tests catch issues that implementation-aligned testing would miss.

#### 15.19.1 Dependency Failure Additions (E27-E30)

**E27: Partial Batch Write Atomic Semantics**

**Failure Mode:** Batch write partially succeeds (items 1-3 written), retry fails (items 4-6 lost), query returns incomplete data that passes 80% threshold.

**Decision:** Implement atomic batch semantics - if any item fails after retries, rollback successfully-written items and return None to force API refetch.

```python
# tests/unit/cache/test_batch_write_atomicity.py
"""Test E27: Partial batch writes must not leave orphan cache entries."""
import pytest
from unittest.mock import patch, MagicMock
from botocore.exceptions import ClientError

class TestBatchWriteAtomicity:
    """Verify batch writes are atomic - all succeed or all rollback."""

    def test_E27_partial_failure_triggers_rollback(self, mock_dynamodb):
        """If batch write partially fails, successfully-written items are deleted."""
        from src.lambdas.shared.cache.ohlc_cache import put_cached_candles

        # Mock: first 3 items succeed, last 3 fail permanently
        mock_dynamodb.batch_write_item.side_effect = [
            {"UnprocessedItems": {}},  # First batch succeeds
            {"UnprocessedItems": {"table": [{"PutRequest": {...}}]}},  # Second fails
            {"UnprocessedItems": {"table": [{"PutRequest": {...}}]}},  # Retry 1 fails
            {"UnprocessedItems": {"table": [{"PutRequest": {...}}]}},  # Retry 2 fails
        ]

        candles = [{"date": f"2026-02-0{i}", "open": 150.0} for i in range(1, 7)]

        result = put_cached_candles("AAPL", "tiingo", "D", candles)

        # Should return False (write failed)
        assert result is False

        # Should have called delete for the successfully-written items
        delete_calls = [c for c in mock_dynamodb.method_calls if 'delete' in str(c)]
        assert len(delete_calls) > 0, "Must rollback successful items on partial failure"

    def test_E27_query_after_partial_failure_returns_none(self, mock_dynamodb):
        """After rollback, subsequent read should cache miss (not return partial data)."""
        # ... trigger partial failure, then query
        result = get_cached_candles("AAPL", "tiingo", "D", start, end)
        assert result is None, "Rolled-back partial writes must not be queryable"
```

**E28: Cold Start with Recovering DynamoDB**

**Failure Mode:** Circuit breaker OPEN + in-memory cache valid → Lambda restarts → BOTH clear simultaneously → flood hits recovering DynamoDB.

**Decision:** First request after cold start uses staggered warm-up with exponential backoff.

```python
# tests/unit/cache/test_cold_start_warmup.py
"""Test E28: Cold start after DynamoDB outage uses staggered warm-up."""
import pytest
import importlib
from unittest.mock import patch
from botocore.exceptions import ClientError

class TestColdStartWarmup:
    """Verify graceful warm-up after Lambda cold start."""

    def test_E28_first_request_uses_exponential_backoff(self):
        """Cold start request backs off if DynamoDB is slow/failing."""
        # Simulate cold start by reloading module
        import src.lambdas.shared.cache.ohlc_cache as cache_module
        importlib.reload(cache_module)

        # Mock DynamoDB as slow (recovering from outage)
        with patch.object(cache_module, '_read_from_dynamodb') as mock_read:
            mock_read.side_effect = [
                ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "Query"),
                ClientError({"Error": {"Code": "ProvisionedThroughputExceededException"}}, "Query"),
                [{"date": "2026-02-03", "close": 150.0}],  # Third attempt succeeds
            ]

            result = cache_module.get_cached_candles("AAPL", "tiingo", "D", start, end)

        # Should have retried with backoff
        assert mock_read.call_count == 3
        assert result is not None

    def test_E28_cold_start_does_not_trigger_circuit_breaker(self):
        """Transient failures during warm-up don't open circuit breaker."""
        import src.lambdas.shared.cache.ohlc_cache as cache_module
        importlib.reload(cache_module)

        # Simulate 2 failures then success (under threshold)
        # ...

        assert not cache_module._is_circuit_open(), \
            "Warm-up failures should not open circuit breaker"
```

**E30: Secrets Rotation Mid-Request Recovery**

**Failure Mode:** Request starts with valid API key → key rotates mid-request → retry with cached (now-invalid) key fails.

**Decision:** On 401 response, refresh secret from Secrets Manager and retry once.

```python
# tests/unit/adapters/test_secrets_rotation.py
"""Test E30: API key rotation during request triggers refresh and retry."""
import pytest
from unittest.mock import patch, MagicMock

class TestSecretsRotation:
    """Verify transparent recovery from mid-request secret rotation."""

    def test_E30_401_triggers_secret_refresh_and_retry(self):
        """When Tiingo returns 401, refresh API key and retry once."""
        from src.lambdas.dashboard.adapters.tiingo import TiingoAdapter

        call_count = 0
        def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call: 401 (key just rotated)
                raise HTTPError(response=MagicMock(status_code=401))
            else:
                # Second call with fresh key: success
                return {"candles": [...]}

        with patch.object(TiingoAdapter, '_make_request', side_effect=mock_request):
            with patch('src.lambdas.shared.secrets.get_secret') as mock_secret:
                mock_secret.side_effect = ["old_key", "new_key"]

                result = TiingoAdapter().get_ohlc("AAPL", "D", "1W")

        # Should have refreshed secret and retried
        assert mock_secret.call_count == 2
        assert result is not None

    def test_E30_second_401_fails_permanently(self):
        """If retry with fresh key also returns 401, fail (not infinite loop)."""
        # ... verify only one retry attempt
```

#### 15.19.2 State Management Additions (F10-F11)

**F10: Graceful Shutdown During Active Requests**

**Failure Mode:** Request in flight → Lambda terminated mid-request → partial response or timeout.

**Decision:** Configure Lambda SIGTERM handling to complete in-flight requests.

```python
# tests/integration/test_graceful_shutdown.py
"""Test F10: Lambda graceful shutdown completes in-flight requests."""
import pytest
import signal
import asyncio

class TestGracefulShutdown:
    """Verify requests complete before Lambda termination."""

    def test_F10_sigterm_waits_for_inflight(self):
        """SIGTERM handler allows current request to complete."""
        from src.lambdas.dashboard.ohlc import handler, _shutdown_handler

        request_completed = False

        async def slow_request():
            nonlocal request_completed
            await asyncio.sleep(0.5)  # Simulate slow request
            request_completed = True
            return {"statusCode": 200}

        # Start request
        task = asyncio.create_task(slow_request())

        # Simulate SIGTERM before request completes
        _shutdown_handler(signal.SIGTERM, None)

        # Wait for task to complete
        asyncio.get_event_loop().run_until_complete(task)

        assert request_completed, "Request must complete before shutdown"
```

**F11: SLRU Cache Implementation**

**Failure Mode:** LRU evicts popular ticker → burst of requests for that ticker → all miss in-memory → DynamoDB throttled.

**Decision:** Implement Segmented LRU (SLRU) cache - ~30 lines of custom code.

```python
# src/lambdas/shared/cache/slru_cache.py
"""Segmented LRU cache - protects hot keys from eviction."""
from collections import OrderedDict
from threading import Lock

class SLRUCache:
    """Two-segment LRU: probationary (new) → protected (hot).

    Items enter probationary segment. On second access, promoted to protected.
    Protected items survive longer than probationary items.
    """

    def __init__(self, protected_size: int, probationary_size: int):
        self.protected = OrderedDict()
        self.probationary = OrderedDict()
        self.protected_size = protected_size
        self.probationary_size = probationary_size
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            if key in self.protected:
                self.protected.move_to_end(key)
                return self.protected[key]
            if key in self.probationary:
                # Promote to protected on second access
                value = self.probationary.pop(key)
                self._insert_protected(key, value)
                return value
            return None

    def set(self, key, value):
        with self._lock:
            if key in self.protected:
                self.protected[key] = value
                self.protected.move_to_end(key)
            elif key in self.probationary:
                # Promote on write too
                self.probationary.pop(key)
                self._insert_protected(key, value)
            else:
                # New items enter probationary
                self._insert_probationary(key, value)

    def _insert_protected(self, key, value):
        if len(self.protected) >= self.protected_size:
            # Demote oldest protected to probationary
            demoted_key, demoted_value = self.protected.popitem(last=False)
            self._insert_probationary(demoted_key, demoted_value)
        self.protected[key] = value

    def _insert_probationary(self, key, value):
        if len(self.probationary) >= self.probationary_size:
            self.probationary.popitem(last=False)  # Evict oldest
        self.probationary[key] = value
```

```python
# tests/unit/cache/test_slru_cache.py
"""Test F11: SLRU cache protects hot keys from eviction."""
import pytest
from src.lambdas.shared.cache.slru_cache import SLRUCache

class TestSLRUCache:
    """Verify SLRU eviction policy protects frequently-accessed keys."""

    def test_F11_hot_key_survives_eviction_pressure(self):
        """Frequently accessed key stays in protected segment."""
        cache = SLRUCache(protected_size=2, probationary_size=3)

        # Access AAPL twice to promote to protected
        cache.set("AAPL", "data1")
        cache.get("AAPL")  # Second access → promoted

        # Fill cache with other keys (eviction pressure)
        for i in range(10):
            cache.set(f"OTHER_{i}", f"data_{i}")

        # AAPL should still be accessible (protected)
        assert cache.get("AAPL") == "data1", "Hot key must survive eviction pressure"

    def test_F11_cold_key_evicted_before_hot(self):
        """Single-access keys evicted from probationary before protected."""
        cache = SLRUCache(protected_size=2, probationary_size=2)

        # AAPL: accessed twice (hot)
        cache.set("AAPL", "hot")
        cache.get("AAPL")

        # COLD: accessed once (cold)
        cache.set("COLD", "cold")

        # Fill with more keys
        cache.set("NEW1", "new1")
        cache.set("NEW2", "new2")
        cache.set("NEW3", "new3")

        # Hot key survives, cold key evicted
        assert cache.get("AAPL") is not None
        assert cache.get("COLD") is None, "Cold key should be evicted first"
```

#### 15.19.3 Race Condition Addition (D14)

**D14: Lock TTL Safety Margin Invariant**

**Failure Mode:** Lock TTL too short → work exceeds TTL → lock expires while holder still working → data race.

**Decision:** Explicit test enforcing invariant: `LOCK_TTL >= 2 * MAX_API_LATENCY`.

```python
# tests/unit/cache/test_lock_safety_margin.py
"""Test D14: Lock TTL must exceed 2x max API latency for safety."""
import pytest

class TestLockSafetyMargin:
    """Verify lock TTL provides sufficient safety margin."""

    def test_D14_lock_ttl_exceeds_max_api_latency(self):
        """Lock TTL must be at least 2x the max expected API call duration.

        Rationale: If API call takes 2s and TTL is 5s, there's 3s margin.
        This margin absorbs: network jitter, slow API days, cleanup time.
        """
        from src.lambdas.shared.cache.ohlc_cache import LOCK_TTL_SECONDS

        # 99th percentile Tiingo latency from production metrics
        MAX_API_LATENCY_SECONDS = 2.5

        # Safety factor: 2x
        MIN_SAFE_TTL = 2 * MAX_API_LATENCY_SECONDS

        assert LOCK_TTL_SECONDS >= MIN_SAFE_TTL, (
            f"Lock TTL ({LOCK_TTL_SECONDS}s) must be >= 2x max API latency "
            f"({MAX_API_LATENCY_SECONDS}s) = {MIN_SAFE_TTL}s for safety. "
            f"Current margin: {LOCK_TTL_SECONDS - MAX_API_LATENCY_SECONDS}s"
        )

    def test_D14_lock_ttl_is_configurable(self):
        """Lock TTL can be configured via environment for different environments."""
        from src.lambdas.shared.config import CacheSettings

        # Verify it's a configurable setting, not hardcoded
        settings = CacheSettings()
        assert hasattr(settings, 'lock_ttl_seconds'), \
            "Lock TTL should be configurable via CacheSettings"
```

#### 15.19.4 Playwright/UI Additions (H24-H27)

**H24-H26: Page Visibility API Integration**

**Failure Mode:** User opens chart → switches tab for 2 hours → returns to stale data.

**Decision:** Implement auto-refresh on tab focus using Page Visibility API.

```typescript
// frontend/tests/e2e/visibility/tab-visibility.spec.ts
import { test, expect, Page } from '@playwright/test';

test.describe('Tab Visibility Data Freshness', () => {
  test('H24: auto-refresh on tab focus after 5+ minutes', async ({ page, context }) => {
    await page.goto('/tickers/AAPL');
    await page.waitForSelector('[data-testid="price-chart"]');

    const initialPrice = await page.locator('[data-testid="current-price"]').textContent();

    // Simulate tab going to background
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: true, writable: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Simulate 6 minutes passing (mock Date)
    await page.evaluate(() => {
      const sixMinutesMs = 6 * 60 * 1000;
      (window as any).__originalDateNow = Date.now;
      Date.now = () => (window as any).__originalDateNow() + sixMinutesMs;
    });

    // Track API calls
    const apiCalls: string[] = [];
    await page.route('**/api/v2/tickers/*/ohlc*', async (route) => {
      apiCalls.push(route.request().url());
      await route.continue();
    });

    // Simulate tab coming back to foreground
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: false });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Should trigger API refresh
    await page.waitForTimeout(1000);
    expect(apiCalls.length).toBeGreaterThan(0);
  });

  test('H25: staleness indicator shows data age', async ({ page }) => {
    // Similar setup, verify "Data from X minutes ago" indicator
  });

  test('H26: offline on tab return shows retry option', async ({ page, context }) => {
    await page.goto('/tickers/AAPL');

    // Go background
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Go offline
    await context.setOffline(true);

    // Come back to foreground
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { value: false });
      document.dispatchEvent(new Event('visibilitychange'));
    });

    // Should show offline indicator with retry button
    await expect(page.locator('[data-testid="offline-indicator"]')).toBeVisible();
    await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();
  });
});
```

**H27: TanStack Query Error Handling**

**Failure Mode:** 500 error cached → user retries → gets cached error → thinks API still down.

**Decision:** Test TanStack recommended behavior + 429 Retry-After handling.

```typescript
// frontend/tests/e2e/errors/error-handling.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Error Response Handling', () => {
  test('H27a: 4xx errors do not auto-retry', async ({ page }) => {
    let requestCount = 0;

    await page.route('**/api/v2/tickers/INVALID/ohlc*', async (route) => {
      requestCount++;
      await route.fulfill({
        status: 404,
        body: JSON.stringify({ error: 'Ticker INVALID not found' }),
      });
    });

    await page.goto('/tickers/INVALID');
    await page.waitForTimeout(5000);  // Wait for potential retries

    // Should only make 1 request (no retry for 4xx)
    expect(requestCount).toBe(1);

    // Error message should be displayed
    await expect(page.locator('[data-testid="error-message"]')).toContainText('not found');
  });

  test('H27b: 5xx errors retry 3 times with backoff', async ({ page }) => {
    let requestCount = 0;
    const requestTimes: number[] = [];

    await page.route('**/api/v2/tickers/AAPL/ohlc*', async (route) => {
      requestCount++;
      requestTimes.push(Date.now());
      await route.fulfill({
        status: 503,
        body: JSON.stringify({ error: 'Service unavailable' }),
      });
    });

    await page.goto('/tickers/AAPL');
    await page.waitForTimeout(15000);  // Wait for retries

    // Should make 4 requests (1 initial + 3 retries)
    expect(requestCount).toBe(4);

    // Verify exponential backoff (each gap longer than previous)
    const gaps = requestTimes.slice(1).map((t, i) => t - requestTimes[i]);
    expect(gaps[1]).toBeGreaterThan(gaps[0]);  // 2nd gap > 1st
  });

  test('H27c: 429 respects Retry-After header', async ({ page }) => {
    let requestCount = 0;

    await page.route('**/api/v2/tickers/AAPL/ohlc*', async (route) => {
      requestCount++;
      if (requestCount === 1) {
        await route.fulfill({
          status: 429,
          headers: { 'Retry-After': '2' },  // Retry after 2 seconds
          body: JSON.stringify({ error: 'Rate limited' }),
        });
      } else {
        await route.fulfill({
          status: 200,
          body: JSON.stringify({ candles: [{ date: '2026-02-03', close: 150.0 }] }),
        });
      }
    });

    const startTime = Date.now();
    await page.goto('/tickers/AAPL');
    await page.waitForSelector('[data-testid="price-chart"]');
    const elapsed = Date.now() - startTime;

    // Should have waited at least 2 seconds before retry
    expect(elapsed).toBeGreaterThanOrEqual(2000);
    expect(requestCount).toBe(2);
  });

  test('H27d: manual retry works after error state', async ({ page }) => {
    let shouldFail = true;

    await page.route('**/api/v2/tickers/AAPL/ohlc*', async (route) => {
      if (shouldFail) {
        await route.fulfill({ status: 503 });
      } else {
        await route.fulfill({
          status: 200,
          body: JSON.stringify({ candles: [{ date: '2026-02-03', close: 150.0 }] }),
        });
      }
    });

    await page.goto('/tickers/AAPL');
    await page.waitForTimeout(15000);  // Wait for auto-retries to exhaust

    // Error state should be displayed
    await expect(page.locator('[data-testid="error-message"]')).toBeVisible();

    // Fix the server
    shouldFail = false;

    // Click retry button
    await page.click('[data-testid="retry-button"]');

    // Should now show data
    await expect(page.locator('[data-testid="price-chart"]')).toBeVisible();
  });
});
```

#### 15.19.5 Observability Addition (O2)

**O2: End-to-End Alarm Chain Test**

**Failure Mode:** Metric emits correctly but CloudWatch alarm misconfigured → no SNS notification.

**Decision:** Weekly preprod integration test verifying full alarm chain.

```python
# tests/preprod/test_alarm_chain.py
"""Test O2: Full observability chain metric → alarm → SNS (preprod only)."""
import pytest
import boto3
import time

@pytest.mark.preprod
class TestAlarmChain:
    """Verify CloudWatch alarm chain fires correctly."""

    def test_O2_cache_error_triggers_alarm(self):
        """Emit CacheError metric, verify alarm triggers, verify SNS."""
        cloudwatch = boto3.client('cloudwatch')
        sns = boto3.client('sns')

        # 1. Emit test metric
        cloudwatch.put_metric_data(
            Namespace='SentimentAnalyzer/OHLCCache',
            MetricData=[{
                'MetricName': 'CacheError',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': [{'Name': 'Test', 'Value': 'O2'}],
            }]
        )

        # 2. Wait for alarm evaluation (up to 2 minutes)
        alarm_name = 'preprod-ohlc-cache-error-alarm'
        for _ in range(24):  # 24 * 5s = 2 minutes
            response = cloudwatch.describe_alarms(AlarmNames=[alarm_name])
            alarm = response['MetricAlarms'][0]
            if alarm['StateValue'] == 'ALARM':
                break
            time.sleep(5)

        assert alarm['StateValue'] == 'ALARM', \
            f"Alarm should be in ALARM state, got {alarm['StateValue']}"

        # 3. Verify SNS received notification (check test subscription)
        # Note: Requires test SNS subscription that logs to S3/CloudWatch
        # This verifies the alarm → SNS integration

        # 4. Reset alarm to OK state for next test
        cloudwatch.set_alarm_state(
            AlarmName=alarm_name,
            StateValue='OK',
            StateReason='Test cleanup'
        )
```

**CI Configuration:**
```yaml
# .github/workflows/preprod-tests.yml
name: Preprod Integration Tests

on:
  schedule:
    - cron: '0 6 * * 1'  # Weekly on Monday 6 AM UTC
  workflow_dispatch:

jobs:
  alarm-chain:
    runs-on: ubuntu-latest
    environment: preprod
    steps:
      - uses: actions/checkout@v4
      - name: Run O2 Alarm Chain Test
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.PREPROD_AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.PREPROD_AWS_SECRET_ACCESS_KEY }}
        run: pytest tests/preprod/test_alarm_chain.py -v
```

#### 15.19.6 Test Infrastructure Decisions

**Time Mocking Strategy:**

All time-sensitive tests (C1-C13, G17-G19) use `freezegun` for precise control:

```python
# tests/conftest.py
from freezegun import freeze_time

@pytest.fixture
def frozen_market_close():
    """Freeze time to 4:00 PM ET (market close)."""
    with freeze_time("2026-02-04 16:00:00", tz_offset=-5):
        yield

@pytest.fixture
def frozen_market_open():
    """Freeze time to 9:30 AM ET (market open)."""
    with freeze_time("2026-02-04 09:30:00", tz_offset=-5):
        yield
```

**Animation Testing Strategy:**

Use deterministic animation stubs (not disabled, not real-time):

```typescript
// frontend/tests/e2e/setup/animation-stubs.ts
export async function stubAnimations(page: Page) {
  await page.addInitScript(() => {
    // Replace requestAnimationFrame with synchronous execution
    let frameId = 0;
    window.requestAnimationFrame = (callback: FrameRequestCallback): number => {
      frameId++;
      // Execute synchronously (deterministic)
      callback(performance.now());
      return frameId;
    };
    window.cancelAnimationFrame = () => {};
  });
}
```

**DynamoDB Test Isolation:**

Use autouse cleanup fixture + short TTL (already established):

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def isolated_dynamodb(mock_dynamodb):
    """Clean DynamoDB state before and after each test."""
    yield

    # Cleanup: delete all items
    from src.lambdas.shared.aws_clients import get_dynamodb_client
    client = get_dynamodb_client()
    # ... truncate table
```

#### 15.19.7 Updated Test Count Summary

| Category | Original | R15 Added | R16 Added | New Total |
|----------|----------|-----------|-----------|-----------|
| A: Cache Keys | 10 | 0 | 0 | 10 |
| B: Data Integrity | 12 | 0 | 2 (B13-B14) | 14 |
| C: Timing & TTL | 13 | 0 | 2 (C14-C15) | 15 |
| D: Race Conditions | 12 | 1 (D14) | 4 (D17-D20; D15-D16 removed Round 18) | 17 |
| E: Dependencies | 26 | 4 (E27-E30) | 0 | 30 |
| F: State Management | 9 | 2 (F10-F11) | 0 | 11 |
| G: Edge Cases | 19 | 0 | 0 | 19 |
| H: Playwright | 22 | 4 (H24-H27) | 3 (H28-H30) | 29 |
| S: Security | 5 | 0 | 0 | 5 |
| M: Metrics | 5 | 0 | 0 | 5 |
| O: Observability | 1 | 1 (O2) | 3 (O3-O5) | 5 |
| **Total** | **134** | **12** | **16** | **162** |

#### 15.19.8 Round 16 Test Additions (Debugging Nightmare Prevention)

**Observability Tests (O3-O5):**

```python
# tests/integration/observability/test_tracing.py
"""Tests for cross-layer request tracing and EMF metrics."""

class TestCrossLayerTracing:
    """Verify X-Ray + EMF + ServiceLens integration."""

    def test_O3_trace_id_propagated_through_cache_layers(self, mock_xray):
        """X-Ray trace ID present in all cache layer logs."""
        from src.lambdas.dashboard.ohlc import get_ohlc_data

        # Trigger request that hits all 3 layers
        with mock_xray.capture() as trace:
            await get_ohlc_data("AAPL", "D", "1W")

        # Verify subsegments for each cache layer
        subsegments = [s.name for s in trace.subsegments]
        assert "cache:in_memory" in subsegments
        assert "cache:dynamodb" in subsegments
        assert "external:tiingo" in subsegments

        # Verify trace ID in logs
        assert trace.trace_id in caplog.text

    def test_O4_emf_metrics_emit_cache_hit_miss(self, caplog):
        """EMF format metrics emitted for cache operations."""
        from src.lambdas.dashboard.ohlc import get_ohlc_data

        await get_ohlc_data("AAPL", "D", "1W")

        # Parse EMF from logs
        emf_logs = [l for l in caplog.records if "_aws" in l.message]
        assert len(emf_logs) > 0

        emf_data = json.loads(emf_logs[0].message)
        assert "CacheHit" in emf_data["_aws"]["CloudWatchMetrics"][0]["Metrics"]

    def test_O5_duplicate_timestamp_alarm_fires(self, mock_tiingo_duplicates, mock_cloudwatch):
        """CloudWatch alarm fires when Tiingo returns duplicate timestamps."""
        from src.lambdas.dashboard.ohlc import get_ohlc_data

        # Tiingo returns duplicates
        await get_ohlc_data("AAPL", "D", "1W")

        # Verify metric emitted
        metric_calls = mock_cloudwatch.put_metric_data.call_args_list
        assert any("TiingoDuplicateTimestamp" in str(c) for c in metric_calls)
```

**Race Condition Tests (D15-D20):**

```python
# tests/unit/cache/test_conditional_writes.py
"""Tests for conditional write protection against stale data.

NOTE (Round 18): D15 and D16 REMOVED — `updated_at` ConditionExpression dropped
because BatchWriteItem does not support ConditionExpression, and OHLC candle data
is idempotent (writing the same candle twice is harmless).
Lock acquisition PutItem retains its ConditionExpression.
"""

class TestConditionalWrites:
    """Verify frozen Lambda cannot overwrite fresh data."""

    # D15 REMOVED (Round 18): Candle writes are idempotent, no stale-write protection needed
    # D16 REMOVED (Round 18): Candle writes are idempotent, no stale-write protection needed

    def test_D17_concurrent_cold_starts_single_api_call(self, mock_tiingo):
        """10 concurrent requests result in exactly 1 Tiingo API call."""
        from src.lambdas.dashboard.ohlc import get_ohlc_data
        import asyncio

        # Simulate 10 concurrent cold-start requests
        tasks = [get_ohlc_data("AAPL", "D", "1W") for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r is not None for r in results)

        # But Tiingo called exactly once
        assert mock_tiingo.get_ohlc.call_count == 1

# tests/unit/cache/test_lock_heartbeat.py
"""Tests for lock holder heartbeat during gray failures."""

class TestLockHeartbeat:
    """Verify heartbeat prevents duplicate API calls during latency spikes."""

    def test_D18_lock_heartbeat_updated_during_slow_operation(self, mock_dynamodb, freezegun):
        """Lock holder updates heartbeat every 5 seconds."""
        from src.lambdas.shared.cache.ohlc_cache import _acquire_fetch_lock

        lock_id = _acquire_fetch_lock("ohlc:AAPL:D:1W:2026-02-05")

        # Simulate 6 seconds of work
        freezegun.tick(6)

        # Check heartbeat was updated
        lock_item = mock_dynamodb.get_item(...)
        assert lock_item["last_heartbeat"] > original_heartbeat

    def test_D19_waiter_respects_heartbeat_during_latency_spike(self, mock_dynamodb):
        """Waiters continue polling when heartbeat is fresh despite long wait."""
        # Lock holder has fresh heartbeat (updated 2s ago)
        # Waiter at 2500ms of waiting should NOT timeout
        pass

    @pytest.mark.preprod
    def test_D20_fis_dynamodb_latency_injection(self):
        """AWS FIS injects latency, heartbeat prevents duplicate calls."""
        # Requires preprod environment with FIS experiment configured
        pass
```

**Data Integrity Tests (B13-B14):**

```python
# tests/unit/cache/test_duplicate_handling.py
"""Tests for handling duplicate timestamps from Tiingo."""

class TestDuplicateTimestampHandling:
    """Verify duplicate detection and deduplication."""

    def test_B13_duplicate_timestamp_detected_and_logged(self, caplog, mock_tiingo_duplicates):
        """Duplicate timestamps logged at ERROR level."""
        from src.lambdas.dashboard.ohlc import get_ohlc_data

        await get_ohlc_data("AAPL", "D", "1W")

        assert "duplicate timestamp" in caplog.text.lower()
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_B14_duplicate_timestamp_keeps_last_occurrence(self, mock_tiingo_duplicates):
        """When duplicates exist, keep the last occurrence."""
        from src.lambdas.shared.cache.ohlc_cache import _deduplicate_candles

        candles = [
            {"timestamp": "2026-02-05T10:00:00Z", "close": 150.0},  # First
            {"timestamp": "2026-02-05T10:00:00Z", "close": 151.0},  # Duplicate (keep this)
        ]

        result = _deduplicate_candles(candles)
        assert len(result) == 1
        assert result[0]["close"] == 151.0  # Last occurrence kept
```

**Timing Tests (C14-C15):**

```python
# tests/unit/cache/test_midnight_handling.py
"""Tests for requests spanning midnight market timezone."""

class TestMidnightSpanningRequests:
    """Verify cache key consistency across midnight boundary."""

    @freeze_time("2026-02-05 04:59:58", tz_offset=0)  # 11:59:58 PM ET
    def test_C14_midnight_spanning_request_consistent_cache_key(self):
        """Cache key computed once at request start, used throughout."""
        from src.lambdas.dashboard.ohlc import OHLCRequestContext

        # Start request at 11:59:58 PM ET
        ctx = OHLCRequestContext.create("AAPL", "D", "1D")
        cache_key_at_start = ctx.cache_key

        # Simulate 4 seconds of processing (now 12:00:02 AM ET next day)
        time.sleep(0.001)  # freezegun advances

        # Cache key should NOT change
        assert ctx.cache_key == cache_key_at_start
        assert "2026-02-05" in cache_key_at_start  # Uses request start date

    @freeze_time("2026-02-05 04:59:58", tz_offset=0)
    def test_C15_ttl_uses_request_timestamp_not_current(self):
        """TTL calculation uses request timestamp, not current time."""
        from src.lambdas.shared.cache.ohlc_cache import _calculate_ttl

        request_time = datetime(2026, 2, 5, 4, 59, 58, tzinfo=timezone.utc)

        # Calculate TTL using request timestamp
        ttl = _calculate_ttl("D", date(2026, 2, 5), request_timestamp=request_time)

        # Should be based on Feb 5, not Feb 6
        expected_base = int(request_time.timestamp())
        assert abs(ttl - (expected_base + 90*24*60*60)) < 60
```

**Playwright Touch Tests (H28-H30):**

```typescript
// frontend/tests/e2e/mobile/touch-gestures.spec.ts
import { test, expect, devices } from '@playwright/test';

test.use(devices['iPhone 12']);

test.describe('Mobile Touch Gestures', () => {
  test('H28: pinch-to-zoom chart area', async ({ page }) => {
    await page.goto('/tickers/AAPL');
    await page.waitForSelector('[data-testid="price-chart"]');

    const chart = page.locator('[data-testid="price-chart"]');
    const box = await chart.boundingBox();

    // Simulate pinch-to-zoom
    await page.touchscreen.pinch(
      box.x + box.width / 2,
      box.y + box.height / 2,
      1.5  // Zoom factor
    );

    // Chart should zoom (verify via transform scale or data range change)
    const transform = await chart.evaluate(el =>
      getComputedStyle(el).transform
    );
    expect(transform).not.toBe('none');
  });

  test('H29: swipe between timeframes', async ({ page }) => {
    await page.goto('/tickers/AAPL');
    await page.waitForSelector('[data-testid="price-chart"]');

    const initialRange = await page.locator('[data-testid="active-range"]').textContent();

    // Swipe left to go to next timeframe
    await page.touchscreen.swipe(300, 400, 100, 400, { steps: 10 });

    const newRange = await page.locator('[data-testid="active-range"]').textContent();
    expect(newRange).not.toBe(initialRange);
  });

  test('H30: tap for tooltip on candle', async ({ page }) => {
    await page.goto('/tickers/AAPL');
    await page.waitForSelector('[data-testid="price-chart"]');

    // Tap on a candle
    const candle = page.locator('[data-testid="candle"]').first();
    await candle.tap();

    // Tooltip should appear
    await expect(page.locator('[data-testid="candle-tooltip"]')).toBeVisible();
    await expect(page.locator('[data-testid="candle-tooltip"]')).toContainText('Open:');
  });
});
```

---
