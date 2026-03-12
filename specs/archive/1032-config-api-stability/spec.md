# Feature Specification: Config API Stability

**Feature Branch**: `1032-config-api-stability`
**Created**: 2025-12-23
**Status**: Draft
**Input**: Fix intermittent 500 errors on POST /api/config - 17 E2E tests skip due to Config creation not available

## Context & Investigation Summary

17 E2E tests skip with "Config creation not available" when `POST /api/v2/configurations` returns non-201 status.

### Prior Work
- **Spec 077**: Added try/except wrapper in router endpoint (commit 7500b57)
- **PR #435**: Fixed ticker format in tests (list[str] instead of list[dict])

### Remaining Root Causes (Investigation Findings)
1. **S3 Ticker Cache Failures** - When ticker_cache.json fails to load from S3, exception not caught
2. **DynamoDB Race Conditions** - No conditional writes on `put_item()` for max-config limit
3. **No Retry Logic** - Transient failures cause immediate 500 without retry

### Current Code Paths
- **Endpoint**: `POST /api/v2/configurations` (router_v2.py:683-731)
- **Service**: `create_configuration()` (configurations.py:200-283)
- **Table**: `{env}-sentiment-users` (PK=USER#{user_id}, SK=CONFIG#{config_id})

## User Scenarios & Testing

### User Story 1 - Reliable Config Creation (Priority: P1)

As a user, I want to create a configuration and have it succeed reliably, so that I can start analyzing sentiment for my selected tickers.

**Why this priority**: Config creation is the entry point for all other features. If it fails, nothing else can be tested.

**Independent Test**: Can be fully tested by creating a config via POST /api/v2/configurations and verifying 201 response with valid config_id.

**Acceptance Scenarios**:

1. **Given** a valid user session, **When** I create a configuration with valid tickers, **Then** I receive 201 Created with config_id
2. **Given** transient S3 failure loading ticker cache, **When** I create a configuration, **Then** the system retries and succeeds (or returns informative error)
3. **Given** transient DynamoDB failure, **When** I create a configuration, **Then** the system retries and succeeds

---

### User Story 2 - Concurrent Config Creation Safety (Priority: P2)

As a user making rapid requests, I want concurrent config creation requests to not exceed my config limit, so that I don't accidentally create more configurations than allowed.

**Why this priority**: Race conditions can lead to data integrity issues (exceeding max configs) but are less common than transient failures.

**Independent Test**: Can be tested by sending 5 concurrent POST requests and verifying count never exceeds limit.

**Acceptance Scenarios**:

1. **Given** user has 1 config and max is 5, **When** 5 concurrent create requests arrive, **Then** only 4 succeed (atomic limit enforcement)
2. **Given** user at max config limit, **When** create request arrives, **Then** 409 Conflict returned (not 500)

---

### User Story 3 - Graceful Degradation (Priority: P3)

As a system operator, I want config creation to fail gracefully with informative errors, so that debugging is possible.

**Why this priority**: Better error handling improves supportability but doesn't block core functionality.

**Independent Test**: Can be tested by simulating failure conditions and verifying error response structure.

**Acceptance Scenarios**:

1. **Given** S3 is completely unavailable, **When** config creation is attempted, **Then** 503 Service Unavailable with retry-after header
2. **Given** DynamoDB returns throttling error, **When** config creation is attempted, **Then** 429 Too Many Requests

---

### Edge Cases

- What happens when user creates config with invalid ticker symbol?
  - Should return 400 Bad Request with validation error (not 500)
- What happens when DynamoDB conditional write fails (CONFLICT)?
  - Should return 409 Conflict
- What happens when Lambda memory/timeout is exhausted?
  - Should have appropriate timeout handling with graceful error

## Requirements

### Functional Requirements

- **FR-001**: System MUST return 201 Created for valid config creation requests
- **FR-002**: System MUST retry transient S3 failures (up to 3 times with exponential backoff)
- **FR-003**: System MUST retry transient DynamoDB failures (up to 3 times with exponential backoff)
- **FR-004**: System MUST enforce max-config limit atomically using DynamoDB conditional writes
- **FR-005**: System MUST return 409 Conflict when max-config limit is reached
- **FR-006**: System MUST return 400 Bad Request for invalid ticker symbols
- **FR-007**: System MUST return 503 Service Unavailable for persistent infrastructure failures
- **FR-008**: System MUST log all config creation attempts with correlation ID for debugging

### Key Entities

- **Configuration**: User's ticker watchlist with timeframe and analysis settings
- **Ticker Cache**: S3-stored cache of valid ticker symbols for validation
- **User Config Limit**: Maximum configurations per user (currently 5)

## Success Criteria

### Measurable Outcomes

- **SC-001**: Config creation returns 201 in >= 99% of valid requests (currently < 90%)
- **SC-002**: All 17 previously skipping E2E tests pass consistently
- **SC-003**: No config limit bypass via race conditions (verified by concurrent test)
- **SC-004**: Mean time to recover from transient failures < 5 seconds (with retries)
- **SC-005**: Error responses include actionable information (status code, message, retry-after where applicable)

## Files to Modify

Based on investigation:

1. `src/lambdas/dashboard/configurations.py` - Add retry logic, conditional writes
2. `src/lambdas/dashboard/router_v2.py` - Improve error response mapping
3. `src/lambdas/shared/ticker_cache.py` - Add S3 retry logic (if exists)
4. `tests/unit/dashboard/test_configurations.py` - Add unit tests for retry logic
5. `tests/integration/test_config_race_conditions.py` - New integration test for concurrency

## Affected E2E Tests

These 17 tests currently skip with "Config creation not available":

1. test_failure_injection.py (4 tests)
2. test_anonymous_restrictions.py (4 tests)
3. test_sentiment.py (2 tests)
4. test_dashboard_buffered.py (2 tests)
5. test_sse.py (1 test)
6. test_alerts.py (1 test)
7. test_auth_magic_link.py (1 test)
8. test_circuit_breaker.py (1 test)
9. test_market_status.py (1 test)
