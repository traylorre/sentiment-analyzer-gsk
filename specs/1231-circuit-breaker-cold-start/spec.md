# Feature Specification: Circuit Breaker Cold Start Persistence

**Feature Branch**: `1231-circuit-breaker-cold-start`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Circuit breaker state persistence across Lambda cold starts hasn't been tested under chaos. If the state table is unreachable, does the breaker default to closed (allow traffic) or open (block)? We need to: (1) document and test the current default behavior, (2) ensure the breaker defaults to CLOSED (allow traffic) when state cannot be loaded — fail-open for data endpoints, (3) add structured logging for state transitions during cold starts.

## Adversarial Review Findings

The existing `CircuitBreakerManager.get_state()` in `src/lambdas/shared/circuit_breaker.py` **already implements fail-open behavior** (lines 360-385). When DynamoDB is unreachable, it catches the exception and returns `CircuitBreakerState.create_default(service)`, which initializes with `state="closed"`. This is correct.

**Gaps identified**:

1. **No cold-start-aware logging**: The existing warning log at line 366 does not distinguish between a cold start state load failure and a warm invocation cache-miss failure. During cold starts, the in-memory cache is always empty, so every first request hits DynamoDB. If DynamoDB fails on cold start, there is no structured indicator that this was a cold start initialization.
2. **No dedicated test coverage**: The fail-open path is exercised indirectly via mocked DynamoDB errors, but there is no test that explicitly simulates the cold start scenario (empty cache + DynamoDB unreachable) and asserts the fail-open default.
3. **No cold start metric**: The existing `SilentFailure/Count` metric fires, but there is no dimension distinguishing cold-start failures from warm-invocation failures.
4. **`save_state` fail-open is not tested under cold start**: If both load AND save fail (total DynamoDB outage), the system still functions via in-memory state, but this path has no explicit test.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Circuit Breaker Defaults to Closed on Cold Start with Unreachable State (Priority: P1)

When a Lambda cold starts and DynamoDB is unreachable (network partition, throttling, table deleted), the circuit breaker MUST default to CLOSED (allow traffic) so that data endpoints remain available. The system must not block all traffic just because it cannot load persisted state.

**Why this priority**: A DynamoDB outage that cascades into blocking all API requests is a total service failure. The circuit breaker exists to protect against external API failures, not to become a single point of failure itself.

**Independent Test**: Can be fully tested by mocking DynamoDB table to raise `ClientError` on `get_item` and asserting `get_state()` returns a closed-state default.

**Acceptance Scenarios**:

1. **Given** a Lambda cold start with empty in-memory cache, **When** DynamoDB `get_item` raises `ClientError` (table unreachable), **Then** `get_state()` returns a `CircuitBreakerState` with `state="closed"` and `can_execute()=True`
2. **Given** a Lambda cold start with empty in-memory cache, **When** DynamoDB `get_item` raises `EndpointConnectionError` (network partition), **Then** `get_state()` returns a closed-state default
3. **Given** a Lambda cold start with DynamoDB unreachable, **When** `can_execute()` is called for any service, **Then** the result is `True` (allow traffic)
4. **Given** a Lambda cold start with DynamoDB unreachable, **When** `record_failure()` is called and `save_state()` also fails, **Then** the in-memory state is preserved and the system continues operating

---

### User Story 2 - State Transitions Are Logged with Cold Start Context (Priority: P2)

When state transitions occur during a Lambda cold start, structured log entries must include a `cold_start` boolean field and a `state_source` field (one of: "cache", "dynamodb", "default_fail_open") so that operators can filter and alert on cold-start-specific failures.

**Why this priority**: Without cold start context in logs, operators cannot distinguish between a one-time cold start fallback (benign) and a persistent DynamoDB connectivity issue (critical). This is essential for chaos testing observability.

**Independent Test**: Can be tested by capturing log output and asserting structured fields are present.

**Acceptance Scenarios**:

1. **Given** a cold start where DynamoDB is unreachable, **When** `get_state()` falls back to default, **Then** the log entry includes `{"cold_start": true, "state_source": "default_fail_open", "service": "...", "state": "closed"}`
2. **Given** a cold start where DynamoDB returns state successfully, **When** `get_state()` loads from DynamoDB, **Then** the log entry includes `{"cold_start": true, "state_source": "dynamodb", "service": "...", "state": "..."}`
3. **Given** a warm invocation where cache is populated, **When** `get_state()` hits cache, **Then** the log entry includes `{"cold_start": false, "state_source": "cache"}`
4. **Given** a warm invocation where DynamoDB fails, **When** `get_state()` falls back, **Then** the log entry includes `{"cold_start": false, "state_source": "default_fail_open"}`

---

### Edge Cases

- What happens if DynamoDB is unreachable on cold start AND the Lambda receives a burst of concurrent requests?
  - Each thread will independently fall back to default closed state. Per-service locks in `_service_locks` prevent race conditions on state modification. This is correct behavior.
- What happens if DynamoDB becomes reachable after initial cold start failure?
  - Subsequent cache misses (after TTL expiry) will successfully load from DynamoDB. The in-memory default will be replaced. No manual intervention needed.
- What happens if the cold start detection mechanism is wrong (e.g., Lambda reuse with cleared cache)?
  - Cache can be cleared programmatically via `clear_cache()`. We detect "cold start" by checking if the in-memory cache is empty for the requested service, not via Lambda runtime internals. This is a conservative approximation.
- What happens if `save_state()` fails after `record_failure()` during a DynamoDB outage?
  - The in-memory state is preserved via the write-through cache update at line 401. The state is accurate within the current invocation. On next cold start, state resets to default (closed). This means failure counts are lost, but that is acceptable — fail-open is the priority.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `CircuitBreakerManager.get_state()` MUST return a `CircuitBreakerState` with `state="closed"` when DynamoDB is unreachable, regardless of whether this is a cold start or warm invocation.
- **FR-002**: `CircuitBreakerManager.get_state()` MUST log the state source ("cache", "dynamodb", "default_fail_open") as a structured field in every log entry.
- **FR-003**: `CircuitBreakerManager.get_state()` MUST log a `cold_start` boolean field indicating whether the in-memory cache was empty for the requested service (proxy for cold start detection).
- **FR-004**: `CircuitBreakerManager.save_state()` MUST NOT raise exceptions — it must catch all DynamoDB errors and log them, preserving the in-memory state.
- **FR-005**: A `ColdStartEvent` structured log event MUST be emitted on the first `get_state()` call for each service when the cache is empty, including the state source and resulting state.
- **FR-006**: The `SilentFailure/Count` CloudWatch metric MUST include a `ColdStart` dimension ("true"/"false") to enable cold-start-specific alerting.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three services (tiingo, finnhub, sendgrid) default to `state="closed"` when DynamoDB is unreachable on cold start (verified by unit tests)
- **SC-002**: Structured log entries include `state_source` and `cold_start` fields in 100% of `get_state()` calls (verified by log assertion tests)
- **SC-003**: `SilentFailure/Count` metric includes `ColdStart` dimension (verified by metric emission tests)
- **SC-004**: Zero regressions in existing circuit breaker tests (verified by running full test suite)
- **SC-005**: Cold start fail-open behavior works correctly under concurrent access (verified by thread-safety tests)

## Assumptions

1. Lambda cold start detection is approximated by checking if the in-memory cache is empty for the requested service. This is conservative — it may also fire on cache TTL expiry, but that is acceptable for logging purposes.
2. The existing `emit_metric()` utility supports additional dimensions.
3. Structured logging via `logger.info(..., extra={...})` is sufficient for log aggregation (CloudWatch Logs Insights / structured JSON logging is already configured).
4. The `save_state()` method already handles exceptions gracefully (confirmed in adversarial review, line 404-437).

## Out of Scope

- Persisting circuit breaker state to a secondary store (e.g., S3) for cross-invocation durability
- Lambda SnapStart or provisioned concurrency configuration changes
- Changes to the circuit breaker state machine logic (threshold, window, recovery timeout)
- DynamoDB table health checks or canary pings
- UI/dashboard changes for circuit breaker monitoring
