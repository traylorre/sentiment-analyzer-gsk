# Feature Specification: E2E Validation Suite

**Feature Branch**: `008-e2e-validation-suite`
**Created**: 2025-11-28
**Status**: Draft
**Input**: Comprehensive end-to-end tests validating all service use-cases against preprod environment. Covers Feature 006 (Dashboard API), Feature 007 (Frontend), and all Lambda functions. Preprod-only execution via CI pipeline, isolated test data per run, synthetic data generators for external APIs, full auth flow testing, and observability validation.

## Overview

This feature delivers a comprehensive E2E test suite that validates every service use-case against the preprod environment. Tests execute exclusively in the CI pipeline (GitHub Actions) with isolated data per run, ensuring production-like validation without affecting real users or data.

**Key Principle**: Every test maps to a specific functional requirement from Features 006/007. If a use-case isn't tested, it isn't validated.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unknown to Known User Journey (Priority: P1)

A new user visits the dashboard for the first time. They have no existing account. The E2E test validates the complete journey: creating an anonymous session, configuring tickers, upgrading via magic link authentication, and verifying data persistence across the transition.

**Why this priority**: This is the core user acquisition funnel. If anonymous-to-authenticated conversion fails, the product cannot retain users. This flow touches auth, data merge, and Cognito integration.

**Independent Test**: Can be tested by executing the full anonymous→authenticated flow and asserting the user's configurations persist post-authentication.

**Acceptance Scenarios**:

1. **Given** no existing session, **When** test visits the dashboard, **Then** an anonymous session is created with valid UUID
2. **Given** an anonymous session, **When** test creates a configuration with 3 tickers, **Then** configuration is stored and retrievable
3. **Given** an anonymous user with configuration, **When** test requests magic link for a unique email, **Then** email is sent within 60 seconds (verified via SendGrid API)
4. **Given** a valid magic link token, **When** test verifies the token, **Then** tokens are returned and anonymous data merges to authenticated account
5. **Given** authenticated user, **When** test retrieves configurations, **Then** previously created anonymous configuration is present

---

### User Story 2 - OAuth Authentication Flows (Priority: P2)

An authenticated user tests the OAuth flow with Google and GitHub providers. The E2E test validates the OAuth URL generation, callback handling, token issuance, and session management.

**Why this priority**: OAuth is the primary authentication method for returning users. Failures here lock users out of their accounts.

**Independent Test**: Can be tested by validating OAuth URL structure, simulating callback with test tokens, and verifying session creation.

**Acceptance Scenarios**:

1. **Given** unauthenticated request, **When** test requests OAuth URLs, **Then** valid Cognito authorize URLs for Google and GitHub are returned
2. **Given** valid OAuth callback code, **When** test submits callback, **Then** ID/access/refresh tokens are returned
3. **Given** authenticated session, **When** test validates session, **Then** session info includes correct auth type and expiry
4. **Given** authenticated user, **When** test calls signout, **Then** session is invalidated for current device only
5. **Given** expired access token, **When** test refreshes tokens, **Then** new valid tokens are issued

---

### User Story 3 - Configuration CRUD Operations (Priority: P3)

A user manages their configurations through the full lifecycle: create, read, update, delete. The E2E test validates all CRUD operations, validation rules, and error handling.

**Why this priority**: Configuration management is the foundation of user personalization. All other features (sentiment, alerts) depend on valid configurations.

**Independent Test**: Can be tested by performing full CRUD cycle on a configuration and asserting each operation's response matches contract.

**Acceptance Scenarios**:

1. **Given** authenticated user with no configs, **When** test creates configuration with 5 valid tickers, **Then** configuration is created with validated ticker metadata
2. **Given** configuration exists, **When** test reads configuration by ID, **Then** complete configuration object is returned
3. **Given** configuration exists, **When** test updates configuration name and tickers, **Then** updated fields are persisted
4. **Given** configuration exists, **When** test deletes configuration, **Then** 204 No Content returned and config no longer retrievable
5. **Given** user has 2 configurations, **When** test attempts to create third, **Then** 409 Conflict returned with max_allowed message
6. **Given** configuration request with invalid ticker, **When** test submits, **Then** 400 Bad Request with INVALID_TICKER code

---

### User Story 4 - Sentiment and Volatility Data Retrieval (Priority: P4)

A user retrieves sentiment and volatility data for their configuration. The E2E test validates data endpoints return properly structured responses with correct data sources.

**Why this priority**: Sentiment and volatility data are the core value proposition. Users expect accurate, timely data from both Tiingo and Finnhub sources.

**Independent Test**: Can be tested by creating a configuration and retrieving sentiment/volatility data, asserting response structure matches API contract.

**Acceptance Scenarios**:

1. **Given** configuration with tickers, **When** test requests sentiment data, **Then** response includes scores from tiingo, finnhub, and our_model sources
2. **Given** configuration with tickers, **When** test requests heatmap with sources view, **Then** matrix includes cells for each ticker×source combination
3. **Given** configuration with tickers, **When** test requests heatmap with timeperiods view, **Then** matrix includes cells for today/1w/1m/3m periods
4. **Given** configuration with tickers, **When** test requests volatility data, **Then** ATR values with trend arrows are returned
5. **Given** configuration with tickers, **When** test requests correlation data, **Then** sentiment-volatility correlation with interpretation is returned

---

### User Story 5 - Alert Rule Lifecycle (Priority: P5)

An authenticated user creates, manages, and receives alerts. The E2E test validates alert creation, threshold configuration, enable/disable, and trigger detection.

**Why this priority**: Alerts drive user engagement and retention through proactive notifications. Alert failures result in missed trading opportunities.

**Independent Test**: Can be tested by creating an alert with low threshold, triggering synthetic data that crosses threshold, and verifying notification is queued.

**Acceptance Scenarios**:

1. **Given** authenticated user with configuration, **When** test creates sentiment threshold alert, **Then** alert is created with correct ticker, type, and threshold
2. **Given** alert exists, **When** test toggles alert off, **Then** alert shows is_enabled: false
3. **Given** alert exists, **When** test updates threshold value, **Then** new threshold is persisted
4. **Given** alert exists, **When** test deletes alert, **Then** 204 returned and alert no longer retrievable
5. **Given** user has 10 alerts on config, **When** test creates 11th, **Then** 409 Conflict returned
6. **Given** anonymous user, **When** test attempts to create alert, **Then** 403 Forbidden returned

---

### User Story 6 - Notification Delivery Pipeline (Priority: P6)

The system evaluates alert conditions and sends notifications. The E2E test validates the complete notification pipeline: evaluation, queuing, email delivery, and history tracking.

**Why this priority**: Notification delivery is the monetization and engagement driver. Failed notifications result in churned users.

**Independent Test**: Can be tested by triggering alert evaluation with synthetic data, verifying notification is created, and checking delivery status.

**Acceptance Scenarios**:

1. **Given** alert with threshold -0.3, **When** synthetic sentiment -0.4 is evaluated, **Then** notification is created in pending status
2. **Given** notification is pending, **When** SendGrid processes it, **Then** status updates to sent with timestamp
3. **Given** notifications exist, **When** test lists notifications, **Then** all notifications with correct metadata are returned
4. **Given** notification was sent, **When** test retrieves detail, **Then** tracking info (opened_at, clicked_at) is available
5. **Given** user has received 10 emails today, **When** 11th triggers, **Then** notification queues for next day with quota exceeded message

---

### User Story 7 - Rate Limiting Enforcement (Priority: P7)

The system enforces rate limits to prevent abuse. The E2E test validates rate limiting across all protected endpoints.

**Why this priority**: Rate limiting protects system resources and prevents credit exhaustion attacks. Without it, malicious actors can drain API quotas.

**Independent Test**: Can be tested by making rapid requests to protected endpoint until 429 response, verifying retry_after_seconds is returned.

**Acceptance Scenarios**:

1. **Given** normal request rate, **When** test makes requests within limit, **Then** all requests succeed with 2xx status
2. **Given** request rate exceeds limit, **When** test continues requests, **Then** 429 Too Many Requests returned
3. **Given** rate limited response, **When** test inspects response, **Then** retry_after_seconds field is present
4. **Given** rate limited, **When** test waits for retry period, **Then** subsequent requests succeed
5. **Given** magic link endpoint, **When** test requests 6th link for same email in 1 hour, **Then** 429 returned

---

### User Story 8 - Circuit Breaker Behavior (Priority: P8)

The system implements circuit breakers for external API resilience. The E2E test validates circuit breaker states and graceful degradation.

**Why this priority**: Circuit breakers prevent cascade failures when Tiingo/Finnhub/SendGrid are unavailable. Without them, partial outages become total outages.

**Independent Test**: Can be tested by simulating external API failures and verifying circuit opens after threshold, then testing recovery.

**Acceptance Scenarios**:

1. **Given** external API healthy, **When** test requests data, **Then** fresh data is returned with cache_status: fresh
2. **Given** external API failing, **When** 5 failures occur in 5 minutes, **Then** circuit breaker opens
3. **Given** circuit breaker open, **When** test requests data, **Then** cached/stale data returned with appropriate staleness indicator
4. **Given** circuit breaker open, **When** 60 seconds pass, **Then** circuit enters half-open state
5. **Given** circuit half-open, **When** next request succeeds, **Then** circuit closes and normal operation resumes

---

### User Story 9 - Ticker Validation and Autocomplete (Priority: P9)

The system validates ticker symbols and provides autocomplete suggestions. The E2E test validates the ticker validation endpoint and search functionality.

**Why this priority**: Invalid tickers waste API quota and confuse users. Autocomplete improves UX and reduces validation errors.

**Independent Test**: Can be tested by validating known-good tickers, known-invalid tickers, and verifying autocomplete results.

**Acceptance Scenarios**:

1. **Given** valid ticker "AAPL", **When** test validates, **Then** response shows status: valid with name and exchange
2. **Given** delisted ticker "TWTR", **When** test validates, **Then** response shows status: delisted with successor "X"
3. **Given** invalid ticker "ZZZZZ", **When** test validates, **Then** response shows status: invalid
4. **Given** partial query "AA", **When** test searches tickers, **Then** matching tickers (AAPL, AAL, etc.) returned within 200ms
5. **Given** empty query, **When** test searches tickers, **Then** empty results returned (not error)

---

### User Story 10 - Real-Time SSE Updates (Priority: P10)

The system pushes real-time updates via Server-Sent Events. The E2E test validates SSE connection, event streaming, and reconnection handling.

**Why this priority**: Real-time updates create "stickiness" and differentiate from competitors. Broken SSE means users see stale data.

**Independent Test**: Can be tested by establishing SSE connection, triggering synthetic data update, and verifying event is received.

**Acceptance Scenarios**:

1. **Given** authenticated user, **When** test connects to SSE endpoint, **Then** connection is established with 200 status
2. **Given** SSE connection active, **When** sentiment data updates, **Then** event with updated data is pushed within 5 seconds
3. **Given** SSE connection active, **When** refresh countdown completes, **Then** refresh event is pushed
4. **Given** SSE connection drops, **When** client reconnects with last-event-id, **Then** connection resumes without data loss
5. **Given** unauthenticated request, **When** test attempts SSE connection, **Then** 401 Unauthorized returned

---

### User Story 11 - CloudWatch Observability Validation (Priority: P11)

The system emits structured logs, metrics, and X-Ray traces. The E2E test validates observability signals are correctly emitted and accessible.

**Why this priority**: Observability is required for debugging production issues. Without proper instrumentation, incidents take longer to resolve.

**Independent Test**: Can be tested by triggering specific actions and querying CloudWatch for expected log entries, metrics, and trace segments.

**Acceptance Scenarios**:

1. **Given** API request made, **When** test queries CloudWatch Logs, **Then** structured log entry with request ID exists
2. **Given** authentication event, **When** test queries CloudWatch Metrics, **Then** authentication metric is incremented
3. **Given** cross-Lambda flow (ingestion→analysis→notification), **When** test queries X-Ray, **Then** complete trace with all segments exists
4. **Given** error occurs, **When** test queries CloudWatch Alarms, **Then** alarm state changes to ALARM
5. **Given** daily cost exceeds $3.33, **When** test queries cost alarm, **Then** cost alert is in ALARM state

---

### User Story 12 - Market Status and Pre-Market Estimates (Priority: P12)

The system provides market status and pre-market estimates during closed hours. The E2E test validates market status detection and estimate generation.

**Why this priority**: Pre-market data provides value when markets are closed. Without it, the dashboard is empty on weekends and holidays.

**Independent Test**: Can be tested by querying market status and pre-market estimates during various market conditions.

**Acceptance Scenarios**:

1. **Given** market open hours, **When** test queries market status, **Then** status: open with session times returned
2. **Given** market closed (weekend), **When** test queries market status, **Then** status: closed with next_open timestamp
3. **Given** market holiday, **When** test queries market status, **Then** status: closed with is_holiday: true and holiday_name
4. **Given** market closed, **When** test queries pre-market estimates, **Then** predictive estimates with confidence scores returned
5. **Given** market open, **When** test queries pre-market estimates, **Then** redirect to live sentiment endpoint suggested

---

### Edge Cases

- **Concurrent requests**: Multiple simultaneous config creations should not exceed limit
- **Token expiry during flow**: Mid-flow token expiry should trigger re-auth modal, not data loss
- **Invalid UTF-8 in responses**: Malformed external API data should not crash parsing
- **Empty ticker list**: Configuration with 0 tickers should fail validation
- **Duplicate tickers**: Same ticker twice in config should be deduplicated or rejected
- **Case sensitivity**: "aapl" and "AAPL" should resolve to same ticker
- **Network timeout**: 30s timeout should trigger graceful degradation
- **Large response payloads**: 1MB+ responses should be handled without memory issues
- **Clock skew**: Token validation should tolerate ±5 minute clock differences
- **Concurrent auth upgrades**: Same anonymous user upgrading via two methods simultaneously

---

## Requirements *(mandatory)*

### Functional Requirements

**Test Data Isolation**
- **FR-001**: Each test run MUST create isolated test data using UUID prefixes (e.g., `test-{run_id}-user@example.com`)
- **FR-002**: Test data MUST be cleaned up after test run completion (success or failure)
- **FR-003**: Tests MUST NOT read or modify data created by other test runs
- **FR-004**: Test users MUST use unique email domains (e.g., `{uuid}@test.sentiment-analyzer.local`)

**Synthetic Data Generation**
- **FR-005**: System MUST provide synthetic data generators for Tiingo news responses
- **FR-006**: System MUST provide synthetic data generators for Finnhub sentiment responses
- **FR-007**: System MUST provide synthetic OHLC data for ATR calculation
- **FR-008**: Synthetic data MUST be deterministic given same seed for reproducibility
- **FR-009**: External API calls MUST be intercepted and replaced with synthetic responses

**Authentication Testing**
- **FR-010**: Tests MUST validate anonymous session creation and validation
- **FR-011**: Tests MUST validate magic link request, delivery (via SendGrid test mode), and verification
- **FR-012**: Tests MUST validate OAuth URL generation and callback handling
- **FR-013**: Tests MUST validate token refresh flow
- **FR-014**: Tests MUST validate session extension on activity
- **FR-015**: Tests MUST validate account linking with explicit confirmation

**API Contract Validation**
- **FR-016**: Tests MUST validate all Dashboard API endpoints against documented contracts
- **FR-017**: Tests MUST validate all Auth API endpoints against documented contracts
- **FR-018**: Tests MUST validate all Notification API endpoints against documented contracts
- **FR-019**: Tests MUST validate all error response formats match documented schema
- **FR-020**: Tests MUST validate rate limit responses include retry_after_seconds

**Observability Validation**
- **FR-021**: Tests MUST verify CloudWatch log entries are created for each Lambda invocation
- **FR-022**: Tests MUST verify X-Ray traces span across Lambda-to-Lambda calls
- **FR-023**: Tests MUST verify CloudWatch metrics are emitted for key operations
- **FR-024**: Tests MUST verify CloudWatch alarms trigger for error conditions
- **FR-025**: Tests MUST verify cost metrics are tracked and alertable

**Error Handling Validation**
- **FR-026**: Tests MUST validate graceful degradation when external APIs are unavailable
- **FR-027**: Tests MUST validate circuit breaker activation after threshold failures
- **FR-028**: Tests MUST validate cached data is returned during outages
- **FR-029**: Tests MUST validate error messages are user-friendly (no stack traces)

**CI Pipeline Integration**
- **FR-030**: Tests MUST execute in GitHub Actions workflow
- **FR-031**: Tests MUST use AWS credentials from GitHub Secrets
- **FR-032**: Tests MUST target preprod environment exclusively
- **FR-033**: Tests MUST produce JUnit XML reports for CI integration
- **FR-034**: Tests MUST produce coverage reports

### Key Entities

- **TestRun**: Unique identifier for a test execution, used for data isolation
- **SyntheticTicker**: Fake ticker symbol for testing (e.g., TEST1, TEST2)
- **SyntheticUser**: Test user with unique email and predictable credentials
- **SyntheticSentiment**: Generated sentiment data with configurable scores
- **SyntheticOHLC**: Generated price data for ATR calculation
- **TestContext**: Shared state across test cases including tokens, config IDs, timestamps

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

**Coverage Metrics**
- **SC-001**: 100% of API endpoints documented in contracts have at least one E2E test
- **SC-002**: 100% of user stories from Features 006/007 have corresponding E2E validation
- **SC-003**: All authentication flows (anonymous, magic link, OAuth) have E2E coverage
- **SC-004**: All error codes documented in API contracts are tested

**Reliability Metrics**
- **SC-005**: E2E test suite passes consistently (>95% of runs) without flakiness
- **SC-006**: Individual test execution completes within 60 seconds
- **SC-007**: Full suite execution completes within 30 minutes
- **SC-008**: Test data cleanup succeeds in 100% of runs (no orphaned data)

**Observability Metrics**
- **SC-009**: CloudWatch log queries successfully find expected entries for 100% of Lambda invocations
- **SC-010**: X-Ray trace queries find complete traces for 100% of cross-Lambda flows
- **SC-011**: CloudWatch alarm state changes are detected within 5 minutes of trigger condition

**Regression Prevention**
- **SC-012**: Any API contract change that breaks E2E tests is detected before merge
- **SC-013**: Authentication flow changes are validated before deployment
- **SC-014**: Rate limit configuration changes are validated before deployment

---

## Assumptions

- Preprod environment is available and configured identically to production
- GitHub Actions has access to preprod AWS credentials via secrets
- SendGrid test mode is available for email validation without actual delivery
- Cognito test users can be programmatically created and deleted
- CloudWatch logs/metrics/traces are accessible from CI pipeline
- X-Ray traces are retained for at least 1 hour for validation
- Synthetic data generators produce realistic but distinguishable test data
- Network latency between CI runner and preprod AWS is < 500ms
- Preprod DynamoDB has sufficient capacity for test data creation/deletion
- Test runs are serialized (not concurrent) to avoid resource contention

---

## Dependencies

- Feature 006 backend API deployed to preprod
- Feature 007 frontend deployed to preprod (for full-stack tests)
- AWS Cognito user pool configured with test client
- SendGrid API in test mode with sandbox domain
- CloudWatch log groups created for all Lambdas
- X-Ray tracing enabled on all Lambdas
- GitHub Actions workflow with AWS credential access
- pytest and related testing libraries (pytest-asyncio, httpx, boto3)

---

## Out of Scope

- Chaos/fault injection testing (future work)
- Performance/load testing
- Security penetration testing
- Frontend unit tests (covered by Feature 007)
- Backend unit tests (existing coverage)
- Local environment testing (preprod only)
- Manual test execution (CI only)
- Production environment testing
