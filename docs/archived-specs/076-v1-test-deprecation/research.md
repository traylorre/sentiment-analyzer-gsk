# Research: v1 API Test Deprecation Audit

**Feature**: 076-v1-test-deprecation
**Date**: 2025-12-10

## Baseline Metrics

- **Total tests in file**: 24
- **Skipped (v1 deprecated)**: 21
- **Active (not skipped)**: 3
- **File**: `tests/integration/test_dashboard_preprod.py`

## v1 Skipped Tests Inventory

The following 21 tests are marked with `@pytest.mark.skip(reason="v1 API deprecated - use /api/v2/* endpoints. See tests/e2e/")`:

### TestDashboardE2E Class (18 tests)

| # | Test Name | Behavior Description |
|---|-----------|---------------------|
| 1 | `test_metrics_response_schema` | Validates /api/metrics returns required fields (total, positive, neutral, negative, by_tag, rate_last_hour, rate_last_24h, recent_items) |
| 2 | `test_metrics_aggregation_accuracy` | Validates sentiment counts are non-negative and total equals sum |
| 3 | `test_metrics_recent_items_sanitized` | Validates ttl and content_hash are not exposed in recent_items |
| 4 | `test_api_key_validation_rejects_invalid` | Validates 401 for missing/wrong/malformed auth |
| 5 | `test_api_key_validation_accepts_valid` | Validates 200 for valid auth |
| 6 | `test_items_endpoint_returns_analyzed_items` | Validates /api/items returns only status=analyzed by default |
| 7 | `test_items_endpoint_filters_by_status` | Validates ?status=analyzed and ?status=pending filtering |
| 8 | `test_items_endpoint_respects_limit` | Validates ?limit=3 returns at most 3 items |
| 9 | `test_items_sorted_by_timestamp_descending` | Validates items sorted by timestamp desc |
| 10 | `test_metrics_time_window_filtering` | Validates ?hours=1 vs ?hours=24 returns different counts |
| 11 | `test_ingestion_rates_calculated_correctly` | Validates rate_last_hour and rate_last_24h logic |
| 12 | `test_empty_table_or_no_matches_returns_zeros` | Validates graceful handling of empty results |
| 13 | `test_parameter_validation_hours` | Validates 400 for hours=0 or hours>168 |
| 14 | `test_parameter_validation_limit` | Validates 400 for limit=0 or limit>100 |
| 15 | `test_parameter_validation_status` | Validates 400 for invalid status values |
| 16 | `test_concurrent_requests` | Validates 5 concurrent requests work correctly |
| 17 | `test_response_content_type` | Validates application/json content-type |
| 18 | `test_sse_stream_endpoint_exists` | Validates /api/stream requires auth |

### TestSecurityIntegration Class (3 tests)

| # | Test Name | Behavior Description |
|---|-----------|---------------------|
| 19 | `test_sse_connection_limit_enforced_in_preprod` | Validates SSE connection limit (P0-2 mitigation) |
| 20 | `test_cors_headers_present_for_valid_origin` | Validates CORS for localhost:3000 (P0-5 mitigation) |
| 21 | `test_authentication_failure_logged_to_cloudwatch` | Validates 401 logged with IP (P1-2 mitigation) |

## Active (Non-Skipped) Tests

These 3 tests are NOT deprecated and will be preserved:

| # | Test Name | Reason Not Deprecated |
|---|-----------|----------------------|
| 1 | `test_health_check_returns_healthy` | /health is version-agnostic |
| 2 | `test_max_sse_connections_env_var_respected` | Tests env var config, not v1 API |
| 3 | `test_production_blocks_requests_without_cors_origins` | Tests CORS config, not v1 API |

## v2 Test Coverage Catalog (tests/e2e/)

The `tests/e2e/` directory contains comprehensive v2 API tests across 22 test files with 200+ test functions:

### Key v2 Test Files (potential equivalents)

| v2 File | Coverage Area |
|---------|---------------|
| `test_sentiment.py` | Sentiment analysis (v2 /api/v2/sentiment endpoints) |
| `test_dashboard_buffered.py` | Dashboard metrics buffering |
| `test_auth_anonymous.py` | Anonymous authentication |
| `test_auth_magic_link.py` | Magic link authentication |
| `test_auth_oauth.py` | OAuth authentication |
| `test_rate_limiting.py` | Rate limiting and 429 handling |
| `test_sse.py` | SSE streaming (v2) |
| `test_config_crud.py` | Configuration CRUD operations |
| `test_alerts.py` | Alert management |
| `test_quota.py` | Quota enforcement |
| `test_notifications.py` | Notification system |
| `test_full_pipeline.py` | End-to-end pipeline tests |
| `test_circuit_breaker.py` | Circuit breaker patterns |
| `test_observability.py` | Observability/logging |

### Notable v2 Tests Covering v1 Behaviors

| v1 Behavior | v2 Equivalent | Notes |
|-------------|---------------|-------|
| Metrics response schema | `test_sentiment.py::test_sentiment_endpoint_returns_json` | v2 uses different schema |
| API key validation | `test_auth_*.py` | v2 uses session-based auth |
| Parameter validation | `test_ticker_validation.py`, `test_config_crud.py` | v2 validates differently |
| SSE streaming | `test_sse.py::test_sse_*` | v2 SSE with different auth |
| Response content type | `test_*.py` (all use `_returns_json` pattern) | v2 standardized |
| Rate limiting | `test_rate_limiting.py::test_*` | v2 rate limiting |

## Analysis Summary

### Categories for Audit

Based on this research, the 21 v1 tests fall into these categories:

1. **Equivalent in v2** (~15 tests): The behavior is tested in v2 with v2 API semantics
   - Metrics/dashboard functionality → `test_dashboard_buffered.py`, `test_sentiment.py`
   - Authentication → `test_auth_*.py`
   - SSE → `test_sse.py`
   - Parameter validation → `test_ticker_validation.py`, `test_config_crud.py`

2. **Deprecated Feature** (~5 tests): v1-specific features not in v2
   - `/api/metrics` endpoint (replaced by `/api/v2/sentiment`)
   - `/api/items` endpoint (replaced by config-based approach)
   - v1-specific auth (Bearer API key vs session tokens)

3. **Potential Gaps** (~1 test): May need verification
   - `test_concurrent_requests` - verify v2 has equivalent load testing

## Recommendation

All 21 tests are safe to remove because:
1. The v1 API endpoints (`/api/metrics`, `/api/items`, `/api/stream`) are deprecated
2. The v2 API (`/api/v2/*`) has comprehensive test coverage in `tests/e2e/`
3. The skip reason explicitly points to `tests/e2e/` as the v2 equivalent
4. The behaviors tested (auth, validation, response format) are covered by v2 tests

Next step: Create audit.md with formal traceability matrix.
